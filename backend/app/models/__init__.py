"""Modelos SQLAlchemy.

Todos los modelos se importan aquí para que ``alembic/env.py`` los registre
en ``Base.metadata`` al autogenerar migraciones.
"""

from app.db.base import Base
from app.models.admin_user import AdminUser
from app.models.cuestionario import Cuestionario, Opcion, Pregunta
from app.models.intento import Intento, Respuesta
from app.models.meta_area import MetaArea

__all__ = [
    "AdminUser",
    "Base",
    "Cuestionario",
    "Intento",
    "MetaArea",
    "Opcion",
    "Pregunta",
    "Respuesta",
]
