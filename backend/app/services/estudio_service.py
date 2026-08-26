"""Lógica de negocio de los estudios y capacitaciones.

Igual que el resto de la capa de servicio: no importa FastAPI y lanza las
excepciones de ``app.core.errors``.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RecursoNoEncontrado
from app.core.estudios_catalogo import sumar_un_mes
from app.models.admin_user import AdminUser
from app.models.estudio import Estudio
from app.schemas.estudio import AvisosOut, AvisoVencimiento, EstudioCrear

# Campos que el formulario captura. Se listan una vez porque el alta y la
# edición escriben exactamente los mismos: si se agrega uno al schema y se
# olvida aquí, la edición dejaría de guardarlo en silencio.
CAMPOS: tuple[str, ...] = (
    "despacho",
    "estudio",
    "estudio_ko",
    "vigencia",
    "prioridad",
    "tipo",
    "estatus",
    "vencimiento",
    "fecha_vencimiento",
    "aprobado",
    "pagado",
    "link",
)


def _volcar(estudio: Estudio, datos: EstudioCrear) -> None:
    """Copia los campos capturados al modelo."""
    for campo in CAMPOS:
        setattr(estudio, campo, getattr(datos, campo))


async def listar_estudios(db: AsyncSession) -> list[Estudio]:
    """Todos los estudios, en el orden en que se capturaron.

    Es el orden de la hoja original, donde la numeración consecutiva agrupa
    los estudios por despacho tal como se fueron dando de alta.
    """
    filas = await db.scalars(select(Estudio).order_by(Estudio.creado_at))
    return list(filas)


async def obtener_estudio(db: AsyncSession, estudio_id: uuid.UUID) -> Estudio:
    """Un estudio por su identificador."""
    estudio = await db.get(Estudio, estudio_id)
    if estudio is None:
        raise RecursoNoEncontrado("El estudio no existe.")
    return estudio


async def crear_estudio(
    db: AsyncSession, datos: EstudioCrear, admin: AdminUser
) -> Estudio:
    """Da de alta un estudio.

    El schema ya dejó coherentes la fecha de vencimiento y el link; aquí solo
    se agrega quién lo capturó.
    """
    estudio = Estudio(
        responsable=admin.nombre or admin.username,
        admin_id=admin.id,
    )
    _volcar(estudio, datos)

    db.add(estudio)
    await db.commit()
    await db.refresh(estudio)

    return estudio


async def actualizar_estudio(
    db: AsyncSession, estudio_id: uuid.UUID, datos: EstudioCrear
) -> Estudio:
    """Reemplaza lo capturado de un estudio.

    No se toca ``responsable``: sigue siendo quien lo dio de alta. Quién hizo
    el cambio queda en la bitácora, que es donde se audita.
    """
    estudio = await obtener_estudio(db, estudio_id)

    _volcar(estudio, datos)
    estudio.actualizado_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(estudio)

    return estudio


async def eliminar_estudio(db: AsyncSession, estudio_id: uuid.UUID) -> str:
    """Borra un estudio y devuelve su nombre, para la bitácora."""
    estudio = await obtener_estudio(db, estudio_id)
    nombre = estudio.estudio

    await db.delete(estudio)
    await db.commit()

    return nombre


async def avisos_vencimiento(db: AsyncSession, hoy: date | None = None) -> AvisosOut:
    """Estudios que vencen dentro de un mes y los que ya vencieron.

    Un estudio "en curso" cuya fecha ya pasó **no** se cambia solo a vencido:
    el dato capturado se respeta y el estado se deduce de la fecha. Cambiar el
    registro por detrás sería peor que mostrarlo como está.

    El filtro va en SQL y solo se traen las cuatro columnas que dibuja la
    campana: la tabla crece con los años y ninguna consulta del encabezado
    debe recorrerla entera.
    """
    dia = hoy or date.today()
    limite = sumar_un_mes(dia)

    filas = await db.execute(
        select(
            Estudio.id,
            Estudio.estudio,
            Estudio.despacho,
            Estudio.fecha_vencimiento,
        )
        .where(Estudio.fecha_vencimiento.is_not(None))
        .where(Estudio.fecha_vencimiento <= limite)
        .order_by(Estudio.fecha_vencimiento)
    )

    avisos: list[AvisoVencimiento] = []
    for identificador, nombre, despacho, vence in filas:
        # `vence` nunca es None aquí: lo garantiza el WHERE.
        dias = (vence - dia).days
        avisos.append(
            AvisoVencimiento(
                id=identificador,
                estudio=nombre,
                despacho=despacho,
                fecha_vencimiento=vence,
                dias=dias,
                vencido=dias < 0,
            )
        )

    return AvisosOut(
        total=len(avisos),
        vencidos=sum(1 for aviso in avisos if aviso.vencido),
        avisos=avisos,
    )
