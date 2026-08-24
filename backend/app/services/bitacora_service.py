"""Consulta de la bitácora de actividad.

La escritura vive en ``core/bitacora.py`` (el middleware); aquí solo se lee.
"""

from dataclasses import dataclass
from datetime import date, time
from typing import Any

from sqlalchemy import Date, Time, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.bitacora import Bitacora

#: Renglones por pantalla. Fijo: la bitácora se hojea, no se configura.
TAMANO_PAGINA: int = 50


@dataclass(frozen=True)
class FiltrosBitacora:
    """Lo que se puede acotar desde la barra de filtros."""

    fecha: date | None = None
    hora_desde: time | None = None
    hora_hasta: time | None = None
    usuario: str | None = None


def _hora_local():  # type: ignore[no-untyped-def]
    """``creado_at`` convertido a la hora de la planta.

    La columna es ``TIMESTAMPTZ`` (UTC), pero quien filtra teclea la hora del
    reloj de la nave. La conversión se hace en SQL para que el índice de
    ``creado_at`` siga sirviendo al ordenar y no haya que traer filas a
    Python solo para descartarlas.
    """
    return func.timezone(settings.ZONA_HORARIA, Bitacora.creado_at)


def _condiciones(filtros: FiltrosBitacora) -> list[Any]:
    """Traduce los filtros a condiciones de SQL."""
    condiciones: list[Any] = []
    local = _hora_local()

    if filtros.fecha is not None:
        condiciones.append(cast(local, Date) == filtros.fecha)

    if filtros.hora_desde is not None:
        condiciones.append(cast(local, Time) >= filtros.hora_desde)

    if filtros.hora_hasta is not None:
        condiciones.append(cast(local, Time) <= filtros.hora_hasta)

    if filtros.usuario:
        condiciones.append(Bitacora.username == filtros.usuario)

    return condiciones


async def listar(
    db: AsyncSession, filtros: FiltrosBitacora, page: int = 1
) -> dict[str, Any]:
    """Devuelve una página de la bitácora, de lo más reciente a lo más viejo."""
    page = max(1, page)
    condiciones = _condiciones(filtros)

    # El conteo va aparte del listado: es lo que necesita el paginador y
    # traer todas las filas para contarlas sería justo lo que la regla 4
    # prohíbe.
    total = await db.scalar(select(func.count(Bitacora.id)).where(*condiciones))

    filas = await db.scalars(
        select(Bitacora)
        .where(*condiciones)
        .order_by(Bitacora.creado_at.desc(), Bitacora.id.desc())
        .offset((page - 1) * TAMANO_PAGINA)
        .limit(TAMANO_PAGINA)
    )

    return {
        "total": total or 0,
        "page": page,
        "size": TAMANO_PAGINA,
        "items": list(filas.all()),
    }


async def usuarios_registrados(db: AsyncSession) -> list[str]:
    """Nombres de usuario que aparecen en la bitácora, para el filtro.

    Sale de la bitácora y no de ``admin_users`` a propósito: quien ya fue
    eliminado sigue teniendo actividad histórica que hay que poder filtrar.
    """
    resultado = await db.scalars(
        select(Bitacora.username).distinct().order_by(Bitacora.username)
    )
    return list(resultado.all())
