"""Lógica de negocio de los controles ESH.

Igual que el resto de la capa de servicio: no importa FastAPI y lanza las
excepciones de ``app.core.errors``. Los conteos se resuelven en SQL, nunca
recorriendo registros en Python.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import etiqueta_area
from app.core.controles_catalogo import (
    AREAS_PLATICAS,
    MAX_FOTOS,
    PUNTOS_SQP,
    RAYSER_TOPE,
    TOTAL_PUNTOS_SQP,
    DefinicionChecklist,
    fuera_de_rango,
    semaforo,
)
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.models.admin_user import AdminUser
from app.models.control import (
    AreaPlatica,
    FotoControl,
    InspeccionSqp,
    PlaticaEsh,
    PuntoChecklist,
    RegistroChecklist,
    RegistroRayser,
    RespuestaSqp,
)
from app.schemas.control import ChecklistCrear, InspeccionSqpCrear, PlaticaCrear
from app.services.rondin_service import TURNO_DIA, ahora_local, turno_actual

# Tipos de imagen aceptados como evidencia y tope de tamaño. El celular de
# planta sube fotos de varios MB; el frontend las reescala antes de enviarlas,
# pero el servidor no puede confiar en eso.
TIPOS_FOTO: frozenset[str] = frozenset({"image/jpeg", "image/png"})
MAX_BYTES_FOTO = 2 * 1024 * 1024

MENSAJE_EVIDENCIA = (
    "Una lectura fuera del rango normal necesita foto de evidencia y "
    "observaciones."
)

ETIQUETAS_AREA_PLATICA: dict[str, str] = {
    area.clave: area.etiqueta for area in AREAS_PLATICAS
}


@dataclass
class Evidencia:
    """Una foto lista para la hoja de evidencias del Excel."""

    fecha: date
    # Qué punto la explica; ``None`` cuando el control no tiene puntos.
    detalle: str | None
    responsable: str
    imagen: bytes


def _construir_fotos(fotos: list[tuple[bytes, str]]) -> list[FotoControl]:
    """Arma las filas de ``controles_fotos`` conservando el orden de captura."""
    return [
        FotoControl(imagen=contenido, tipo=tipo, orden=orden)
        for orden, (contenido, tipo) in enumerate(fotos)
    ]


async def _ids_de_fotos(
    db: AsyncSession, columna, propietarios: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Identificadores de las fotos de cada propietario, sin traer las imágenes.

    Una consulta aparte y solo de identificadores: un mes de evidencias son
    decenas de megabytes y el listado del panel se pide en cada carga.
    """
    if not propietarios:
        return {}

    filas = await db.execute(
        select(FotoControl.id, columna)
        .where(columna.in_(propietarios))
        .order_by(FotoControl.orden)
    )

    agrupadas: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for foto_id, propietario in filas.all():
        agrupadas[propietario].append(foto_id)

    return agrupadas


async def obtener_foto(db: AsyncSession, foto_id: uuid.UUID) -> FotoControl:
    """Una foto de evidencia, venga del control que venga."""
    foto = await db.get(FotoControl, foto_id)
    if foto is None:
        raise RecursoNoEncontrado("La foto no existe.")
    return foto


def validar_cantidad_fotos(total: int, etiqueta: str) -> None:
    """Aplica el tope de fotos por punto o por plática."""
    if total > MAX_FOTOS:
        raise ErrorDeNegocio(
            f"{etiqueta}: no se pueden subir más de {MAX_FOTOS} fotos."
        )


# --- Rayser ----------------------------------------------------------------


def convertir_lectura(valor: str, etiqueta: str) -> Decimal:
    """Convierte a Decimal el valor que llegó como texto en el multipart.

    Un cuerpo multipart no pasa por la validación de tipos de Pydantic, así que
    la conversión y el rango se comprueban aquí, con el mensaje ya en español.
    """
    try:
        lectura = Decimal(valor.strip().replace(",", "."))
    except (InvalidOperation, AttributeError) as exc:
        raise ErrorDeNegocio(f"{etiqueta}: se esperaba un número.") from exc

    if not lectura.is_finite():
        raise ErrorDeNegocio(f"{etiqueta}: se esperaba un número.")

    if lectura < 0 or lectura > RAYSER_TOPE:
        raise ErrorDeNegocio(
            f"{etiqueta}: la lectura debe estar entre 0 y {RAYSER_TOPE:g} psi."
        )

    # La columna es NUMERIC(5,1): más decimales los rechazaría la base con un
    # error críptico.
    return lectura.quantize(Decimal("0.1"))


def validar_foto(contenido: bytes, tipo: str | None) -> str:
    """Comprueba el tipo y el tamaño de la evidencia. Devuelve el tipo limpio."""
    normalizado = (tipo or "").split(";")[0].strip().lower()
    if normalizado not in TIPOS_FOTO:
        raise ErrorDeNegocio("La evidencia debe ser una imagen JPG o PNG.")

    if len(contenido) > MAX_BYTES_FOTO:
        raise ErrorDeNegocio("La foto de evidencia no debe pesar más de 2 MB.")

    if not contenido:
        raise ErrorDeNegocio("El archivo de evidencia llegó vacío.")

    return normalizado


async def registrar_rayser(
    db: AsyncSession,
    *,
    fecha: date,
    lecturas: list[Decimal],
    observaciones: str | None,
    fotos: list[tuple[bytes, str]],
    admin: AdminUser,
) -> RegistroRayser:
    """Guarda la lectura del día.

    Una fila por fecha, igual que el formato en papel: un segundo registro del
    mismo día es un error de captura, no una lectura nueva.
    """
    if fuera_de_rango(lecturas) and (not observaciones or not fotos):
        raise ErrorDeNegocio(MENSAJE_EVIDENCIA)

    registro = RegistroRayser(
        fecha=fecha,
        manometro_1=lecturas[0],
        manometro_2=lecturas[1],
        manometro_3=lecturas[2],
        manometro_4=lecturas[3],
        observaciones=observaciones,
        responsable=admin.username,
        admin_id=admin.id,
        fotos=_construir_fotos(fotos),
    )
    db.add(registro)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # uq_rayser_fecha. Se comprueba aquí y no con un SELECT previo porque
        # dos capturas simultáneas pasarían ambas la comprobación.
        raise ConflictoDeNegocio(
            f"Ya existe el registro del {fecha:%d/%m/%Y}. "
            "Elimínalo si necesitas corregirlo."
        ) from exc

    return await obtener_rayser(db, registro.id)


def describir_lecturas(lecturas: list[Decimal]) -> list[dict]:
    """Clasifica cada lectura con su semáforo.

    Se hace en el servidor para que la tabla del panel y el Excel pinten
    exactamente los mismos colores; el frontend repite la regla solo para el
    formulario en vivo, antes de guardar.
    """
    return [{"valor": lectura, "semaforo": semaforo(lectura)} for lectura in lecturas]


async def listar_rayser(db: AsyncSession, desde: date, hasta: date) -> list[dict]:
    """Registros del periodo, del más reciente al más antiguo.

    Deliberadamente sin la columna ``foto``: la lista de un mes con las
    imágenes embebidas pesaría varios megabytes. La evidencia se pide por
    separado con ``obtener_rayser``.
    """
    if desde > hasta:
        raise ErrorDeNegocio("La fecha inicial no puede ser mayor que la final.")

    filas = await db.execute(
        select(
            RegistroRayser.id,
            RegistroRayser.fecha,
            RegistroRayser.manometro_1,
            RegistroRayser.manometro_2,
            RegistroRayser.manometro_3,
            RegistroRayser.manometro_4,
            RegistroRayser.observaciones,
            RegistroRayser.responsable,
            RegistroRayser.creado_at,
        )
        .where(RegistroRayser.fecha >= desde, RegistroRayser.fecha <= hasta)
        .order_by(RegistroRayser.fecha.desc())
    )

    registros = list(filas.all())
    fotos = await _ids_de_fotos(db, FotoControl.rayser_id, [f.id for f in registros])

    salida: list[dict] = []
    for fila in registros:
        lecturas = [
            fila.manometro_1,
            fila.manometro_2,
            fila.manometro_3,
            fila.manometro_4,
        ]
        salida.append(
            {
                "id": fila.id,
                "fecha": fila.fecha,
                "manometros": describir_lecturas(lecturas),
                "observaciones": fila.observaciones,
                "fotos": fotos.get(fila.id, []),
                "fuera_de_rango": fuera_de_rango(lecturas),
                "responsable": fila.responsable,
                "creado_at": fila.creado_at,
            }
        )

    return salida


async def obtener_rayser(db: AsyncSession, registro_id: uuid.UUID) -> RegistroRayser:
    """Registro completo, con los identificadores de sus fotos."""
    registro = await db.scalar(
        select(RegistroRayser)
        .where(RegistroRayser.id == registro_id)
        .options(selectinload(RegistroRayser.fotos).load_only(FotoControl.orden))
    )

    if registro is None:
        raise RecursoNoEncontrado("El registro no existe.")

    return registro


async def eliminar_rayser(db: AsyncSession, registro_id: uuid.UUID) -> date:
    """Borra un registro mal capturado para poder recapturar el día.

    Devuelve la fecha que quedó libre: después del ``DELETE`` ya no hay de
    dónde leerla, y la bitácora necesita decir qué día se borró.
    """
    registro = await obtener_rayser(db, registro_id)
    fecha = registro.fecha
    await db.delete(registro)
    await db.commit()
    return fecha


async def evidencias_rayser(
    db: AsyncSession, desde: date, hasta: date
) -> list[Evidencia]:
    """Fotos del periodo, para la hoja de evidencias del Excel.

    Consulta aparte de los listados a propósito: la tabla del panel se pide
    muchas veces y no debe arrastrar las imágenes.
    """
    filas = await db.execute(
        select(
            RegistroRayser.fecha,
            RegistroRayser.responsable,
            FotoControl.imagen,
        )
        .join(FotoControl, FotoControl.rayser_id == RegistroRayser.id)
        .where(RegistroRayser.fecha >= desde, RegistroRayser.fecha <= hasta)
        .order_by(RegistroRayser.fecha, FotoControl.orden)
    )

    return [
        Evidencia(fecha=fila.fecha, detalle=None, responsable=fila.responsable, imagen=fila.imagen)
        for fila in filas.all()
    ]


# --- Inspección de SQP -----------------------------------------------------


async def registrar_sqp(
    db: AsyncSession, datos: InspeccionSqpCrear, admin: AdminUser
) -> InspeccionSqp:
    """Guarda una inspección completa.

    Se exige el formato entero: una inspección a medias no se puede comparar
    con las anteriores ni sirve como evidencia ante una auditoría.
    """
    ordenes = [respuesta.orden for respuesta in datos.respuestas]

    if sorted(ordenes) != list(range(TOTAL_PUNTOS_SQP)):
        raise ErrorDeNegocio(
            f"Hay que contestar los {TOTAL_PUNTOS_SQP} puntos de la inspección, "
            "una sola vez cada uno."
        )

    inspeccion = InspeccionSqp(
        fecha=datos.fecha,
        area=datos.area,
        encargado=datos.encargado,
        cargo=datos.cargo,
        sustancias=datos.sustancias,
        responsable=admin.username,
        admin_id=admin.id,
        respuestas=[
            RespuestaSqp(
                orden=respuesta.orden,
                codigo=PUNTOS_SQP[respuesta.orden].codigo,
                valor=respuesta.valor,
                observaciones=respuesta.observaciones,
            )
            for respuesta in sorted(datos.respuestas, key=lambda r: r.orden)
        ],
    )

    db.add(inspeccion)
    await db.commit()

    return await obtener_sqp(db, inspeccion.id)


async def obtener_sqp(db: AsyncSession, inspeccion_id: uuid.UUID) -> InspeccionSqp:
    """Inspección con sus respuestas cargadas."""
    inspeccion = await db.scalar(
        select(InspeccionSqp)
        .where(InspeccionSqp.id == inspeccion_id)
        .options(selectinload(InspeccionSqp.respuestas))
    )

    if inspeccion is None:
        raise RecursoNoEncontrado("La inspección no existe.")

    return inspeccion


async def listar_sqp(
    db: AsyncSession, desde: date | None, hasta: date | None, area: str | None
) -> list[dict]:
    """Historial de inspecciones con su conteo de hallazgos.

    El conteo de "NO" se hace con COUNT ... FILTER en la misma consulta: traer
    las respuestas de cada inspección para contarlas en Python multiplicaría
    las consultas sin ganar nada.
    """
    total_no = func.count(RespuestaSqp.id).filter(RespuestaSqp.valor == "no")

    consulta = (
        select(
            InspeccionSqp.id,
            InspeccionSqp.fecha,
            InspeccionSqp.area,
            InspeccionSqp.encargado,
            InspeccionSqp.responsable,
            InspeccionSqp.creado_at,
            total_no.label("total_no"),
        )
        .outerjoin(RespuestaSqp, RespuestaSqp.inspeccion_id == InspeccionSqp.id)
        .group_by(InspeccionSqp.id)
        .order_by(InspeccionSqp.fecha.desc(), InspeccionSqp.creado_at.desc())
    )

    if desde is not None:
        consulta = consulta.where(InspeccionSqp.fecha >= desde)
    if hasta is not None:
        consulta = consulta.where(InspeccionSqp.fecha <= hasta)
    if area:
        consulta = consulta.where(InspeccionSqp.area == area)

    filas = await db.execute(consulta)

    return [
        {
            "id": fila.id,
            "fecha": fila.fecha,
            "area": fila.area,
            "area_label": etiqueta_area(fila.area),
            "encargado": fila.encargado,
            "responsable": fila.responsable,
            "total_no": fila.total_no,
            "creado_at": fila.creado_at,
        }
        for fila in filas.all()
    ]


def separar_sustancias(texto: str | None) -> list[str]:
    """Convierte el campo libre en la lista de sustancias, una por renglón."""
    if not texto:
        return []
    return [linea.strip() for linea in texto.splitlines() if linea.strip()]


# --- Listas de verificación (OK / NO OK) -----------------------------------


def _validar_campos(
    campos: tuple, valores: dict[str, str], contexto: str
) -> dict[str, str]:
    """Comprueba un grupo de campos del formato contra el catálogo.

    Devuelve solo los campos que el catálogo declara: lo que llegue de más se
    descarta en vez de guardarse, para que el histórico no acumule claves que
    nadie sabe leer.
    """
    limpios: dict[str, str] = {}

    for campo in campos:
        valor = (valores.get(campo.clave) or "").strip()

        if not valor:
            if campo.obligatorio:
                raise ErrorDeNegocio(f"{contexto}{campo.etiqueta}: falta capturarlo.")
            continue

        if campo.tipo == "opcion" and valor not in campo.opciones:
            opciones = " o ".join(campo.opciones)
            raise ErrorDeNegocio(
                f"{contexto}{campo.etiqueta}: elige una opción válida ({opciones})."
            )

        if campo.tipo == "numero":
            try:
                Decimal(valor.replace(",", "."))
            except InvalidOperation as exc:
                raise ErrorDeNegocio(
                    f"{contexto}{campo.etiqueta}: se esperaba un número."
                ) from exc

        limpios[campo.clave] = valor

    return limpios


def _valor_automatico(tipo: Literal["turno", "hora"], momento: datetime) -> str:
    """Lo que vale un campo que el operador ya no captura.

    `momento` ya viene en hora de la planta (`rondin_service.ahora_local`),
    así que formatear la hora aquí no repite la trampa de `sin_zona()`.
    """
    if tipo == "turno":
        return "Día" if turno_actual(momento) == TURNO_DIA else "Noche"
    return f"{momento:%H:%M}"


def _discriminador(
    definicion: DefinicionChecklist, encabezado: dict[str, str]
) -> str:
    """Lo que distingue dos inspecciones del mismo día.

    Sale de los campos que el catálogo marca como identificadores: el turno en
    silos, el tablero y el turno en tableros. En los controles de rejilla la
    lista está vacía y el discriminador queda en blanco, así que la
    restricción de unicidad significa "una hoja por día".
    """
    return "|".join(
        encabezado.get(clave, "").lower() for clave in definicion.clave_unicidad
    )


def _descripcion_registro(
    definicion: DefinicionChecklist, fecha: date, encabezado: dict[str, str]
) -> str:
    """Cómo se nombra una inspección en los mensajes de error."""
    partes = [
        encabezado[clave] for clave in definicion.clave_unicidad if encabezado.get(clave)
    ]
    detalle = f" ({', '.join(partes)})" if partes else ""
    return f"{fecha:%d/%m/%Y}{detalle}"


async def registrar_checklist(
    db: AsyncSession,
    *,
    definicion: DefinicionChecklist,
    datos: ChecklistCrear,
    fotos_por_punto: dict[int, list[tuple[bytes, str]]],
    admin: AdminUser,
) -> RegistroChecklist:
    """Guarda el recorrido del día.

    Se exige el formato completo: una hoja a medias no sirve como evidencia de
    que el recorrido se hizo. Cada punto en NO OK necesita observaciones (lo
    valida el schema) y al menos una foto.
    """
    ordenes = [punto.orden for punto in datos.puntos]
    total = len(definicion.puntos)

    if sorted(ordenes) != list(range(total)):
        raise ErrorDeNegocio(
            f"Hay que contestar los {total} puntos del control, una sola vez "
            "cada uno."
        )

    # Turno y hora de inspección ya no los captura el operador: se calculan
    # aquí, con la hora del servidor, y se inyectan antes de validar. Lo que
    # mande el frontend para esos campos se ignora.
    momento = ahora_local()
    valores_encabezado = dict(datos.encabezado)
    for campo in definicion.encabezado:
        if campo.automatico:
            valores_encabezado[campo.clave] = _valor_automatico(campo.automatico, momento)

    encabezado = _validar_campos(definicion.encabezado, valores_encabezado, "")
    hay_hallazgos = any(punto.valor == "no_ok" for punto in datos.puntos)

    secciones: dict[str, dict[str, str]] = {}
    for seccion in definicion.secciones:
        # El bloque de acción ante anomalía solo se exige cuando algo salió
        # mal; en un recorrido limpio ni siquiera se muestra.
        if seccion.solo_con_hallazgos and not hay_hallazgos:
            continue

        secciones[seccion.clave] = _validar_campos(
            seccion.campos, datos.secciones.get(seccion.clave, {}), f"{seccion.titulo} — "
        )

    puntos: list[PuntoChecklist] = []

    for punto in sorted(datos.puntos, key=lambda p: p.orden):
        definicion_punto = definicion.puntos[punto.orden]
        etiqueta = definicion_punto.etiqueta
        fotos = fotos_por_punto.get(punto.orden, [])

        if definicion_punto.medicion and not punto.medicion:
            raise ErrorDeNegocio(
                f"{etiqueta}: falta la medición en {definicion_punto.medicion}."
            )

        if punto.medicion and not definicion_punto.medicion:
            raise ErrorDeNegocio(f"{etiqueta}: este punto no lleva medición.")

        if punto.medicion:
            try:
                Decimal(punto.medicion.replace(",", "."))
            except InvalidOperation as exc:
                raise ErrorDeNegocio(
                    f"{etiqueta}: la medición debe ser un número."
                ) from exc

        if punto.valor == "no_ok" and not fotos:
            raise ErrorDeNegocio(
                f"{etiqueta}: un punto marcado como NO OK necesita al menos "
                "una foto de evidencia."
            )

        # Una foto sobre un punto en OK no explica nada y solo ocupa espacio.
        if punto.valor == "ok" and fotos:
            raise ErrorDeNegocio(
                f"{etiqueta}: solo los puntos marcados como NO OK llevan fotos."
            )

        validar_cantidad_fotos(len(fotos), etiqueta)

        puntos.append(
            PuntoChecklist(
                orden=punto.orden,
                clave=definicion_punto.clave,
                valor=punto.valor,
                observaciones=punto.observaciones,
                medicion=punto.medicion,
                fotos=_construir_fotos(fotos),
            )
        )

    registro = RegistroChecklist(
        control=definicion.clave,
        fecha=datos.fecha,
        discriminador=_discriminador(definicion, encabezado),
        encabezado=encabezado,
        secciones=secciones,
        responsable=admin.username,
        admin_id=admin.id,
        puntos=puntos,
    )
    db.add(registro)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # uq_checklist_control_fecha. Se comprueba aquí y no con un SELECT
        # previo porque dos capturas simultáneas pasarían ambas la prueba.
        raise ConflictoDeNegocio(
            f"Ya existe el registro del "
            f"{_descripcion_registro(definicion, datos.fecha, encabezado)}. "
            "Elimínalo si necesitas corregirlo."
        ) from exc

    return registro


async def listar_checklist(
    db: AsyncSession, definicion: DefinicionChecklist, desde: date, hasta: date
) -> list[dict]:
    """Registros del periodo, del más reciente al más antiguo.

    Las etiquetas de cada punto se resuelven desde el catálogo, no desde la
    base: corregir una redacción no debe obligar a tocar el histórico.
    """
    if desde > hasta:
        raise ErrorDeNegocio("La fecha inicial no puede ser mayor que la final.")

    registros = list(
        await db.scalars(
            select(RegistroChecklist)
            .where(
                RegistroChecklist.control == definicion.clave,
                RegistroChecklist.fecha >= desde,
                RegistroChecklist.fecha <= hasta,
            )
            .options(selectinload(RegistroChecklist.puntos))
            .order_by(RegistroChecklist.fecha.desc())
        )
    )

    puntos = [punto for registro in registros for punto in registro.puntos]
    fotos = await _ids_de_fotos(db, FotoControl.punto_id, [p.id for p in puntos])

    return [
        {
            "id": registro.id,
            "fecha": registro.fecha,
            "responsable": registro.responsable,
            "creado_at": registro.creado_at,
            "hay_hallazgos": any(p.valor == "no_ok" for p in registro.puntos),
            "encabezado": registro.encabezado,
            "secciones": registro.secciones,
            "puntos": [
                _describir_punto(definicion, punto, fotos.get(punto.id, []))
                for punto in registro.puntos
            ],
        }
        for registro in registros
    ]


def _describir_punto(
    definicion: DefinicionChecklist, punto: PuntoChecklist, fotos: list[uuid.UUID]
) -> dict:
    """Un punto guardado con lo que aporta el catálogo."""
    del_catalogo = (
        definicion.puntos[punto.orden]
        if 0 <= punto.orden < len(definicion.puntos)
        else None
    )

    return {
        "orden": punto.orden,
        "clave": punto.clave,
        "etiqueta": _etiqueta_punto(definicion, punto),
        "etiqueta_ko": del_catalogo.etiqueta_ko if del_catalogo else None,
        "categoria": del_catalogo.categoria if del_catalogo else None,
        "valor": punto.valor,
        "observaciones": punto.observaciones,
        "medicion": punto.medicion,
        "fotos": fotos,
    }


def _etiqueta_punto(definicion: DefinicionChecklist, punto: PuntoChecklist) -> str:
    """Texto del punto según el catálogo.

    Si el catálogo cambió y el punto guardado ya no existe, se muestra su clave
    en lugar de fallar: el histórico tiene que poder leerse igual.
    """
    if 0 <= punto.orden < len(definicion.puntos):
        return definicion.puntos[punto.orden].etiqueta
    return punto.clave


async def obtener_checklist(
    db: AsyncSession, definicion: DefinicionChecklist, registro_id: uuid.UUID
) -> dict:
    """Una inspección suelta, para el Excel por formato."""
    registro = await db.scalar(
        select(RegistroChecklist)
        .where(RegistroChecklist.id == registro_id)
        .options(selectinload(RegistroChecklist.puntos))
    )

    # Se comprueba el control además del id: una liga de otra pestaña no debe
    # poder leer el registro de esta.
    if registro is None or registro.control != definicion.clave:
        raise RecursoNoEncontrado("El registro no existe.")

    fotos = await _ids_de_fotos(
        db, FotoControl.punto_id, [punto.id for punto in registro.puntos]
    )

    return {
        "id": registro.id,
        "fecha": registro.fecha,
        "responsable": registro.responsable,
        "creado_at": registro.creado_at,
        "hay_hallazgos": any(p.valor == "no_ok" for p in registro.puntos),
        "encabezado": registro.encabezado,
        "secciones": registro.secciones,
        "puntos": [
            _describir_punto(definicion, punto, fotos.get(punto.id, []))
            for punto in registro.puntos
        ],
    }


async def evidencias_registro(
    db: AsyncSession, definicion: DefinicionChecklist, registro_id: uuid.UUID
) -> list[Evidencia]:
    """Fotos de una sola inspección, para su hoja de evidencias."""
    filas = await db.execute(
        select(
            RegistroChecklist.fecha,
            RegistroChecklist.responsable,
            PuntoChecklist.clave,
            FotoControl.imagen,
        )
        .join(PuntoChecklist, PuntoChecklist.registro_id == RegistroChecklist.id)
        .join(FotoControl, FotoControl.punto_id == PuntoChecklist.id)
        .where(
            RegistroChecklist.id == registro_id,
            RegistroChecklist.control == definicion.clave,
        )
        .order_by(PuntoChecklist.orden, FotoControl.orden)
    )

    etiquetas = {punto.clave: punto.etiqueta for punto in definicion.puntos}

    return [
        Evidencia(
            fecha=fila.fecha,
            detalle=etiquetas.get(fila.clave, fila.clave),
            responsable=fila.responsable,
            imagen=fila.imagen,
        )
        for fila in filas.all()
    ]


async def eliminar_checklist(
    db: AsyncSession, definicion: DefinicionChecklist, registro_id: uuid.UUID
) -> None:
    """Borra un registro mal capturado para poder recapturar el día."""
    registro = await db.get(RegistroChecklist, registro_id)

    # Se comprueba el control además del id: una liga de otra pestaña no debe
    # poder borrar el registro de esta.
    if registro is None or registro.control != definicion.clave:
        raise RecursoNoEncontrado("El registro no existe.")

    await db.delete(registro)
    await db.commit()


async def evidencias_checklist(
    db: AsyncSession, definicion: DefinicionChecklist, desde: date, hasta: date
) -> list[Evidencia]:
    """Fotos del periodo, para la hoja de evidencias del Excel."""
    filas = await db.execute(
        select(
            RegistroChecklist.fecha,
            RegistroChecklist.responsable,
            PuntoChecklist.orden,
            PuntoChecklist.clave,
            FotoControl.imagen,
        )
        .join(PuntoChecklist, PuntoChecklist.registro_id == RegistroChecklist.id)
        .join(FotoControl, FotoControl.punto_id == PuntoChecklist.id)
        .where(
            RegistroChecklist.control == definicion.clave,
            RegistroChecklist.fecha >= desde,
            RegistroChecklist.fecha <= hasta,
        )
        .order_by(RegistroChecklist.fecha, PuntoChecklist.orden, FotoControl.orden)
    )

    etiquetas = {punto.clave: punto.etiqueta for punto in definicion.puntos}

    return [
        Evidencia(
            fecha=fila.fecha,
            detalle=etiquetas.get(fila.clave, fila.clave),
            responsable=fila.responsable,
            imagen=fila.imagen,
        )
        for fila in filas.all()
    ]


# --- Pláticas diarias de seguridad -----------------------------------------


async def registrar_platica(
    db: AsyncSession,
    *,
    datos: PlaticaCrear,
    fotos: list[tuple[bytes, str]],
    admin: AdminUser,
) -> PlaticaEsh:
    """Guarda una plática impartida.

    La foto es obligatoria: es lo único que prueba ante una auditoría que la
    plática se dio. No hay unicidad por fecha, así que un mismo día admite
    varias pláticas con distinto tema.
    """
    if not fotos:
        raise ErrorDeNegocio("La plática necesita al menos una foto de evidencia.")

    validar_cantidad_fotos(len(fotos), "Evidencia de la plática")

    platica = PlaticaEsh(
        fecha=datos.fecha,
        tema=datos.tema,
        responsable=admin.username,
        admin_id=admin.id,
        areas=[AreaPlatica(clave=clave) for clave in datos.areas],
        fotos=_construir_fotos(fotos),
    )
    db.add(platica)
    await db.commit()

    return platica


async def listar_platicas(db: AsyncSession, desde: date, hasta: date) -> list[dict]:
    """Pláticas del periodo, de la más reciente a la más antigua."""
    if desde > hasta:
        raise ErrorDeNegocio("La fecha inicial no puede ser mayor que la final.")

    platicas = list(
        await db.scalars(
            select(PlaticaEsh)
            .where(PlaticaEsh.fecha >= desde, PlaticaEsh.fecha <= hasta)
            .options(selectinload(PlaticaEsh.areas))
            .order_by(PlaticaEsh.fecha.desc(), PlaticaEsh.creado_at.desc())
        )
    )

    fotos = await _ids_de_fotos(
        db, FotoControl.platica_id, [platica.id for platica in platicas]
    )

    return [
        {
            "id": platica.id,
            "fecha": platica.fecha,
            "tema": platica.tema,
            "responsable": platica.responsable,
            "creado_at": platica.creado_at,
            "areas": [
                {
                    "clave": area.clave,
                    "etiqueta": ETIQUETAS_AREA_PLATICA.get(area.clave, area.clave),
                }
                # El orden lo fija el catálogo, no el de captura: así las
                # columnas del Excel y las etiquetas del panel coinciden.
                for area in sorted(
                    platica.areas,
                    key=lambda a: _orden_area(a.clave),
                )
            ],
            "fotos": fotos.get(platica.id, []),
        }
        for platica in platicas
    ]


def _orden_area(clave: str) -> int:
    """Posición del área dentro del catálogo."""
    for indice, area in enumerate(AREAS_PLATICAS):
        if area.clave == clave:
            return indice
    return len(AREAS_PLATICAS)


async def eliminar_platica(db: AsyncSession, platica_id: uuid.UUID) -> None:
    """Borra una plática mal capturada."""
    platica = await db.get(PlaticaEsh, platica_id)
    if platica is None:
        raise RecursoNoEncontrado("La plática no existe.")

    await db.delete(platica)
    await db.commit()


async def evidencias_platicas(
    db: AsyncSession, desde: date, hasta: date
) -> list[Evidencia]:
    """Fotos del periodo, para la hoja de evidencias del Excel."""
    filas = await db.execute(
        select(
            PlaticaEsh.fecha,
            PlaticaEsh.tema,
            PlaticaEsh.responsable,
            FotoControl.imagen,
        )
        .join(FotoControl, FotoControl.platica_id == PlaticaEsh.id)
        .where(PlaticaEsh.fecha >= desde, PlaticaEsh.fecha <= hasta)
        .order_by(PlaticaEsh.fecha, PlaticaEsh.creado_at, FotoControl.orden)
    )

    return [
        Evidencia(
            fecha=fila.fecha,
            detalle=fila.tema,
            responsable=fila.responsable,
            imagen=fila.imagen,
        )
        for fila in filas.all()
    ]
