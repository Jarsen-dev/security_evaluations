"""Recepciones de mercancía: guardado, existencias y sesiones de captura.

Confirmar una recepción hace dos cosas indivisibles: deja el documento con sus
partidas y **suma la existencia** de cada insumo del catálogo. Las partidas
son, de hecho, el rastro de esa entrada: dicen qué código, cuánto y de qué
documento vino.

Lo que se captura son cajas o paquetes —es lo que dice la remisión— y lo que
entra al inventario son piezas: la conversión la hace este servicio con las
``piezas_por_empaque`` del catálogo, que además quedan guardadas en la partida
para que el documento histórico no cambie si mañana cambia la presentación.
"""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.models.insumo import Insumo
from app.models.recepcion import (
    ESTADO_PENDIENTE,
    ESTADO_SUBIDA,
    ESTADO_USADA,
    FotoRecepcion,
    ItemRecepcion,
    Recepcion,
    SesionQrRecepcion,
)
from app.schemas.recepcion import ItemRecepcionCrear, RecepcionCrear
from app.services import insumo_service

logger = logging.getLogger(__name__)

#: Renglones por página del historial. Fijo, como el resto del proyecto.
TAMANO_PAGINA: int = 50

NO_EXISTE = "La recepción no existe."
FOTO_NO_EXISTE = "La foto no existe o ya se borró."
SIN_PARTIDAS = "La recepción necesita al menos una partida."

# Mensaje idéntico para sesión inexistente, expirada o ya usada: distinguirlas
# permitiría sondear identificadores desde los endpoints públicos.
SESION_NO_DISPONIBLE = (
    "Esta sesión de captura ya no está disponible. Vuelve a generar el código "
    "QR desde la computadora."
)


# --- Fotos -----------------------------------------------------------------

#: Formatos que acepta la cámara de un celular y que Tesseract puede leer.
TIPOS_FOTO = frozenset({"image/jpeg", "image/png", "image/webp"})


def validar_foto(contenido: bytes, tipo: str | None) -> str:
    """Comprueba tipo y tamaño de la foto. Devuelve el tipo MIME limpio.

    Vive en el servicio y no en la ruta porque la misma comprobación la
    necesitan dos routers: el del panel y el público que recibe la foto del
    celular.
    """
    if not contenido:
        raise ErrorDeNegocio("El archivo llegó vacío.")

    normalizado = (tipo or "").split(";")[0].strip().lower()
    if normalizado not in TIPOS_FOTO:
        raise ErrorDeNegocio("La foto debe ser una imagen JPG, PNG o WebP.")

    if len(contenido) > settings.RECEPCIONES_MAX_BYTES_FOTO:
        tope = settings.RECEPCIONES_MAX_BYTES_FOTO // (1024 * 1024)
        raise ErrorDeNegocio(f"La foto no debe pesar más de {tope} MB.")

    return normalizado


async def guardar_foto(
    db: AsyncSession, *, imagen: bytes, tipo_mime: str
) -> FotoRecepcion:
    """Guarda la evidencia. Se llama **antes** de intentar leerla.

    Si la extracción falla después, la foto ya está: el operador captura a
    mano y no se perdió el viaje al almacén.
    """
    foto = FotoRecepcion(imagen=imagen, tipo=tipo_mime)
    db.add(foto)
    await db.flush()
    return foto


async def obtener_foto(db: AsyncSession, foto_id: uuid.UUID) -> FotoRecepcion:
    foto = await db.get(FotoRecepcion, foto_id)
    if foto is None:
        raise RecursoNoEncontrado(FOTO_NO_EXISTE)
    return foto


# --- Guardado --------------------------------------------------------------


def _codigos_faltantes(
    datos: RecepcionCrear, encontrados: dict[str, list[Insumo]]
) -> list[str]:
    """Códigos del documento que no están en el catálogo, en orden de captura."""
    faltantes: list[str] = []
    for item in datos.items:
        clave = item.codigo.lower()
        if clave not in encontrados and item.codigo not in faltantes:
            faltantes.append(item.codigo)
    return faltantes


def _resolver_insumo(item: ItemRecepcionCrear, candidatos: list[Insumo]) -> Insumo:
    """Decide a qué insumo entra la partida.

    Un mismo código ampara varios productos, así que el código no basta: quien
    captura elige la descripción y manda su ``insumo_id``.

    El id se busca **entre los candidatos de ese código**, no por sí solo. Si
    se resolviera a secas, un cliente podría mandar un código y el id de otro
    insumo cualquiera: la partida se guardaría con el snapshot del otro y el
    código tecleado se ignoraría en silencio.

    Sin id y con varios candidatos se rechaza en vez de elegir. Eso cubre
    también la carrera: entre que la IA leyó la remisión y el operador guarda,
    alguien pudo dar de alta una segunda descripción para ese código, y una
    partida que era inequívoca dejó de serlo.
    """
    if item.insumo_id is not None:
        for insumo in candidatos:
            if insumo.id == item.insumo_id:
                return insumo
        raise ErrorDeNegocio(
            f"La descripción elegida ya no corresponde al código "
            f"«{item.codigo}». Vuelve a elegirla."
        )

    if len(candidatos) == 1:
        return candidatos[0]

    raise ErrorDeNegocio(
        f"El código «{item.codigo}» tiene varias descripciones. Elige cuál de "
        f"ellas recibiste.",
        [insumo.descripcion for insumo in candidatos],
    )


async def crear(
    db: AsyncSession,
    datos: RecepcionCrear,
    *,
    creado_por: str,
    admin_id: uuid.UUID,
) -> Recepcion:
    """Guarda el documento y da entrada al inventario.

    Valida **todos** los códigos de una sola consulta y, si falta alguno,
    falla con la lista completa: hacer que el usuario descubra los faltantes
    de uno en uno sería una tortura con una remisión de veinte partidas.

    Qué insumo recibe cada partida lo decide ``_resolver_insumo()``: el código
    puede amparar varios productos y el desempate viaja en el ``insumo_id``.
    """
    if not datos.items:
        raise ErrorDeNegocio(SIN_PARTIDAS)

    catalogo = await insumo_service.mapa_por_codigo(
        db, {item.codigo.lower() for item in datos.items}
    )

    faltantes = _codigos_faltantes(datos, catalogo)
    if faltantes:
        raise ErrorDeNegocio(
            "Hay códigos que no están en el catálogo. Agrégalos primero en "
            "la pestaña de Catálogo.",
            [f"Código no registrado: {codigo}" for codigo in faltantes],
        )

    recepcion = Recepcion(
        foto_id=datos.foto_id,
        proveedor=datos.proveedor,
        folio=datos.folio,
        fecha=datos.fecha,
        tipo_documento=datos.tipo_documento,
        ocr_ok=datos.ocr_ok,
        ocr_raw=datos.ocr_raw,
        advertencias=datos.advertencias,
        creado_por=creado_por,
        admin_id=admin_id,
    )
    db.add(recepcion)
    await db.flush()

    # La misma clave puede venir en dos renglones de la misma hoja; se suman
    # antes de tocar la existencia para no aplicar dos incrementos sueltos.
    por_insumo: dict[uuid.UUID, int] = defaultdict(int)

    for item in datos.items:
        insumo = _resolver_insumo(item, catalogo[item.codigo.lower()])
        # Lo que el operador teclea son CAJAS; al inventario entran piezas. La
        # conversión se hace aquí y con el dato del catálogo: el cliente manda
        # lo que dice el papel y nunca el total.
        piezas = item.cantidad * insumo.piezas_por_empaque
        db.add(
            ItemRecepcion(
                recepcion_id=recepcion.id,
                insumo_id=insumo.id,
                # Snapshot: el documento histórico no cambia si cambia el catálogo.
                codigo=insumo.codigo,
                descripcion=insumo.descripcion,
                unidad_medida=insumo.unidad_medida,
                cantidad=item.cantidad,
                piezas_por_empaque=insumo.piezas_por_empaque,
            )
        )
        por_insumo[insumo.id] += piezas

    # El incremento se hace en SQL, no leyendo-modificando-escribiendo: con
    # cuatro workers de uvicorn dos recepciones simultáneas del mismo insumo
    # se pisarían y una de las dos entradas se perdería en silencio.
    for insumo_id, piezas in por_insumo.items():
        await db.execute(
            update(Insumo)
            .where(Insumo.id == insumo_id)
            .values(
                existencia=Insumo.existencia + piezas,
                actualizado_at=datetime.now(UTC),
            )
        )

    await db.commit()
    await db.refresh(recepcion)
    return recepcion


# --- Consulta --------------------------------------------------------------


async def obtener(db: AsyncSession, recepcion_id: uuid.UUID) -> Recepcion:
    recepcion = await db.get(Recepcion, recepcion_id)
    if recepcion is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return recepcion


async def listar(
    db: AsyncSession,
    *,
    busqueda: str | None = None,
    tipo_documento: str | None = None,
    page: int = 1,
) -> dict[str, object]:
    """Página del historial, de la captura más reciente hacia atrás."""
    page = max(1, page)
    condiciones = []

    if busqueda and busqueda.strip():
        patron = f"%{busqueda.strip().translate(insumo_service.COMODINES_LIKE)}%"
        condiciones.append(
            func.coalesce(Recepcion.proveedor, "").ilike(patron, escape="\\")
            | func.coalesce(Recepcion.folio, "").ilike(patron, escape="\\")
        )

    if tipo_documento:
        condiciones.append(Recepcion.tipo_documento == tipo_documento)

    total = await db.scalar(
        select(func.count(Recepcion.id)).where(*condiciones)
    )
    filas = await db.scalars(
        select(Recepcion)
        .where(*condiciones)
        .order_by(Recepcion.creado_at.desc())
        .offset((page - 1) * TAMANO_PAGINA)
        .limit(TAMANO_PAGINA)
    )

    return {
        "total": total or 0,
        "page": page,
        "size": TAMANO_PAGINA,
        "items": list(filas.all()),
    }


# --- Sesiones de captura por QR --------------------------------------------


async def crear_sesion(db: AsyncSession, *, creado_por: str) -> SesionQrRecepcion:
    """Abre una sesión para que el celular mande la foto.

    De paso barre las que ya vencieron: sin cron ni tarea de fondo, la
    limpieza se paga en la operación que crea la siguiente.
    """
    await db.execute(
        delete(SesionQrRecepcion).where(
            SesionQrRecepcion.expira_en < datetime.now(UTC)
        )
    )

    sesion = SesionQrRecepcion(
        creado_por=creado_por,
        expira_en=datetime.now(UTC)
        + timedelta(minutes=settings.RECEPCIONES_MINUTOS_SESION_QR),
    )
    db.add(sesion)
    await db.commit()
    await db.refresh(sesion)
    return sesion


async def _sesion_viva(
    db: AsyncSession, sesion_id: uuid.UUID, *, estados: set[str]
) -> SesionQrRecepcion:
    """Sesión que existe, no ha vencido y está en uno de los estados dados."""
    sesion = await db.get(SesionQrRecepcion, sesion_id)

    if (
        sesion is None
        or sesion.estado not in estados
        or sesion.expira_en < datetime.now(UTC)
    ):
        raise ConflictoDeNegocio(SESION_NO_DISPONIBLE)

    return sesion


async def estado_sesion(db: AsyncSession, sesion_id: uuid.UUID) -> str:
    """Estado para el polling de la PC. No revela nada más."""
    sesion = await _sesion_viva(
        db, sesion_id, estados={ESTADO_PENDIENTE, ESTADO_SUBIDA, ESTADO_USADA}
    )
    return sesion.estado


async def adjuntar_foto_a_sesion(
    db: AsyncSession, sesion_id: uuid.UUID, *, imagen: bytes, tipo_mime: str
) -> None:
    """Recibe la foto del celular. Solo una vez por sesión."""
    sesion = await _sesion_viva(db, sesion_id, estados={ESTADO_PENDIENTE})

    foto = await guardar_foto(db, imagen=imagen, tipo_mime=tipo_mime)
    sesion.foto_id = foto.id
    sesion.estado = ESTADO_SUBIDA
    await db.commit()


async def consumir_sesion(
    db: AsyncSession, sesion_id: uuid.UUID
) -> FotoRecepcion:
    """Toma la foto que subió el celular y quema la sesión.

    Pasar a ``usada`` aquí, y no al subir, es lo que permite que la PC
    descubra la foto por polling antes de que la sesión deje de servir.
    """
    sesion = await _sesion_viva(db, sesion_id, estados={ESTADO_SUBIDA})

    if sesion.foto_id is None:
        raise ConflictoDeNegocio(SESION_NO_DISPONIBLE)

    foto = await obtener_foto(db, sesion.foto_id)
    sesion.estado = ESTADO_USADA
    await db.commit()
    return foto
