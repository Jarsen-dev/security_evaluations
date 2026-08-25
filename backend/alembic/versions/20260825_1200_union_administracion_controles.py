"""Une las dos ramas de migraciones: administración y controles

Revision ID: 0006_union_admin_controles
Revises: 0005_checklist_formato, 0004_usuarios_y_bitacora
Create Date: 2026-08-25

Dos trabajos avanzaron en paralelo sobre ``0003_controles_esh``: la pestaña de
administración (usuarios y bitácora) y los controles ESH (listas de
verificación, pláticas y formatos por inspección). Al juntar las dos ramas
quedaron dos cabezas, y con dos cabezas ``alembic upgrade head`` se niega a
correr.

Esta revisión no toca el esquema: solo vuelve a dejar una sola cabeza para que
el arranque del contenedor siga funcionando sin intervención manual.
"""

from collections.abc import Sequence

revision: str = "0006_union_admin_controles"
down_revision: str | tuple[str, ...] | None = (
    "0005_checklist_formato",
    "0004_usuarios_y_bitacora",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Sin cambios de esquema: las dos ramas ya hicieron lo suyo."""


def downgrade() -> None:
    """Sin cambios de esquema: deshacerla vuelve a abrir las dos ramas."""
