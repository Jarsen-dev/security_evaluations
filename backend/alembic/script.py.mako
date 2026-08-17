"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Recordatorio del proyecto: las migraciones deben ser idempotentes.
Usa bloques DO $$ ... END $$ con IF NOT EXISTS / IF EXISTS para que la
migración pueda re-ejecutarse sobre una base parcialmente migrada, y deja
siempre un downgrade() funcional.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
