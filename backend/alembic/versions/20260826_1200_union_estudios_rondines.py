"""Une las dos ramas de migraciones: estudios y rondines

Revision ID: 0009_union_estudios_rondines
Revises: 0008_rondines, 0007_estudios
Create Date: 2026-08-26

Dos trabajos avanzaron en paralelo sobre ``0006_union_admin_controles``: la
pestaña de Estudios por un lado, y las de Catálogo y Rondines por el otro. Al
juntar las dos ramas en el merge quedaron dos cabezas, y con dos cabezas
``alembic upgrade head`` se niega a correr y el contenedor no arranca.

Esta revisión no toca el esquema: solo vuelve a dejar una sola cabeza. Las
tablas de las dos ramas son independientes (``estudios`` por un lado;
``insumos``, ``puntos_rondin``, ``escaneos_rondin`` y ``envios_reporte_rondin``
por el otro), así que el orden en que Alembic camine las ramas da igual.

NO renombrar las revisiones para "arreglar" que existan dos con prefijo
``0007`` (``0007_estudios`` y ``0007_catalogo_insumos``). Alembic identifica por
la cadena completa, así que conviven sin problema; en cambio, renumerarlas deja
huérfana cualquier base cuyo ``alembic_version`` guarde el identificador viejo.
Ese fue exactamente el error que rompió el arranque con
``KeyError: '0004_controles_checklist'``.
"""

from collections.abc import Sequence

revision: str = "0009_union_estudios_rondines"
down_revision: str | tuple[str, ...] | None = (
    "0008_rondines",
    "0007_estudios",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Sin cambios de esquema: las dos ramas ya hicieron lo suyo."""


def downgrade() -> None:
    """Sin cambios de esquema: deshacerla vuelve a abrir las dos ramas."""
