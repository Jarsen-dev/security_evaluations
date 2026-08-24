"""Lógica de negocio de los controles ESH.

Igual que el resto de la capa de servicio: no importa FastAPI y lanza las
excepciones de ``app.core.errors``. Los conteos se resuelven en SQL, nunca
recorriendo registros en Python.
"""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import etiqueta_area
from app.core.controles_catalogo import (
    PUNTOS_SQP,
    RAYSER_TOPE,
    TOTAL_PUNTOS_SQP,
    fuera_de_rango,
    semaforo,
)
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.models.admin_user import AdminUser
from app.models.control import InspeccionSqp, RegistroRayser, RespuestaSqp
from app.schemas.control import InspeccionSqpCrear

# Tipos de imagen aceptados como evidencia y tope de tamaño. El celular de
# planta sube fotos de varios MB; el frontend las reescala antes de enviarlas,
# pero el servidor no puede confiar en eso.
TIPOS_FOTO: frozenset[str] = frozenset({"image/jpeg", "image/png"})
MAX_BYTES_FOTO = 2 * 1024 * 1024

MENSAJE_EVIDENCIA = (
    "Una lectura fuera del rango normal necesita foto de evidencia y "
    "observaciones."
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
    foto: bytes | None,
    foto_tipo: str | None,
    admin: AdminUser,
) -> RegistroRayser:
    """Guarda la lectura del día.

    Una fila por fecha, igual que el formato en papel: un segundo registro del
    mismo día es un error de captura, no una lectura nueva.
    """
    if fuera_de_rango(lecturas) and (not observaciones or foto is None):
        raise ErrorDeNegocio(MENSAJE_EVIDENCIA)

    registro = RegistroRayser(
        fecha=fecha,
        manometro_1=lecturas[0],
        manometro_2=lecturas[1],
        manometro_3=lecturas[2],
        manometro_4=lecturas[3],
        observaciones=observaciones,
        foto=foto,
        foto_tipo=foto_tipo if foto is not None else None,
        responsable=admin.username,
        admin_id=admin.id,
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

    await db.refresh(registro)
    return registro


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
            RegistroRayser.foto_tipo,
            RegistroRayser.responsable,
            RegistroRayser.creado_at,
        )
        .where(RegistroRayser.fecha >= desde, RegistroRayser.fecha <= hasta)
        .order_by(RegistroRayser.fecha.desc())
    )

    registros: list[dict] = []
    for fila in filas.all():
        lecturas = [
            fila.manometro_1,
            fila.manometro_2,
            fila.manometro_3,
            fila.manometro_4,
        ]
        registros.append(
            {
                "id": fila.id,
                "fecha": fila.fecha,
                "manometros": describir_lecturas(lecturas),
                "observaciones": fila.observaciones,
                "tiene_foto": fila.foto_tipo is not None,
                "fuera_de_rango": fuera_de_rango(lecturas),
                "responsable": fila.responsable,
                "creado_at": fila.creado_at,
            }
        )

    return registros


async def obtener_rayser(db: AsyncSession, registro_id: uuid.UUID) -> RegistroRayser:
    """Registro completo, incluida la foto."""
    registro = await db.get(RegistroRayser, registro_id)
    if registro is None:
        raise RecursoNoEncontrado("El registro no existe.")
    return registro


async def eliminar_rayser(db: AsyncSession, registro_id: uuid.UUID) -> None:
    """Borra un registro mal capturado para poder recapturar el día."""
    registro = await obtener_rayser(db, registro_id)
    await db.delete(registro)
    await db.commit()


async def evidencias_rayser(
    db: AsyncSession, desde: date, hasta: date
) -> list[tuple[date, str, bytes]]:
    """Fotos del periodo, para la hoja de evidencias del Excel.

    Consulta aparte de ``listar_rayser`` a propósito: la tabla del panel se
    pide muchas veces y no debe arrastrar las imágenes.
    """
    filas = await db.execute(
        select(
            RegistroRayser.fecha,
            RegistroRayser.responsable,
            RegistroRayser.foto,
        )
        .where(
            RegistroRayser.fecha >= desde,
            RegistroRayser.fecha <= hasta,
            RegistroRayser.foto.is_not(None),
        )
        .order_by(RegistroRayser.fecha)
    )

    return [(fila.fecha, fila.responsable, fila.foto) for fila in filas.all()]


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
