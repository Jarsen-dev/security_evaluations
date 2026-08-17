"""Clase base declarativa de SQLAlchemy.

Los modelos concretos se agregan en la Fase 2. Todos deben heredar de ``Base``
e importarse en ``app/models/__init__.py`` para que Alembic los detecte al
autogenerar migraciones.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Convención de nombres explícita: sin ella, PostgreSQL asigna nombres
# automáticos a índices y constraints y las migraciones idempotentes
# (que consultan por nombre en information_schema) se vuelven frágiles.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa común a todos los modelos del proyecto."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
