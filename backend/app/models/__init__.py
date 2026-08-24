"""Modelos SQLAlchemy.

Todos los modelos se importan aquí para que ``alembic/env.py`` los registre
en ``Base.metadata`` al autogenerar migraciones.
"""

from app.db.base import Base
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
from app.models.cuestionario import Cuestionario, Opcion, Pregunta
from app.models.intento import Intento, Respuesta
from app.models.meta_area import MetaArea

__all__ = [
    "AdminUser",
    "AreaPlatica",
    "Base",
    "Cuestionario",
    "FotoControl",
    "InspeccionSqp",
    "Intento",
    "MetaArea",
    "Opcion",
    "PlaticaEsh",
    "Pregunta",
    "PuntoChecklist",
    "RegistroChecklist",
    "RegistroRayser",
    "Respuesta",
    "RespuestaSqp",
]
