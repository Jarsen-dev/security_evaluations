"""Modelos SQLAlchemy.

Todos los modelos se importan aquí para que ``alembic/env.py`` los registre
en ``Base.metadata`` al autogenerar migraciones.
"""

from app.db.base import Base
from app.models.admin_user import AdminUser
from app.models.bitacora import Bitacora
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
from app.models.cuestionario import Cuestionario, Opcion, Pregunta
from app.models.estudio import Estudio
from app.models.insumo import Insumo
from app.models.intento import Intento, Respuesta
from app.models.meta_area import MetaArea
from app.models.rondin import EnvioReporteRondin, EscaneoRondin, PuntoRondin

__all__ = [
    "AdminUser",
    "AreaPlatica",
    "Base",
    "Bitacora",
    "Cuestionario",
    "Estudio",
    "EnvioReporteRondin",
    "EscaneoRondin",
    "FotoControl",
    "InspeccionSqp",
    "Insumo",
    "Intento",
    "MetaArea",
    "Opcion",
    "PlaticaEsh",
    "Pregunta",
    "PuntoChecklist",
    "PuntoRondin",
    "RegistroChecklist",
    "RegistroRayser",
    "Respuesta",
    "RespuestaSqp",
]
