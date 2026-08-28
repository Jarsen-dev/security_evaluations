"""Evidencia fotográfica en la inspección de SQP

Revision ID: 0013_fotos_sqp
Revises: 0012_cierres_hallazgo
Create Date: 2026-08-28

Los controles de lista de verificación exigen foto en cada punto inconforme
desde el principio; SQP era el único que no, y sus hallazgos quedaban con la
observación escrita y nada que la respaldara. Esta migración le da la misma
capacidad.

Las fotos siguen viviendo en ``controles_fotos``, como todas las del proyecto:
solo se suma la quinta llave foránea posible y se rehace el ``CHECK`` de "un
solo dueño". El endpoint que las sirve no cambia.

Todo con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base
parcialmente migrada. Una sentencia por ``execute``: asyncpg las prepara y
rechaza los cuerpos con varias.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_fotos_sqp"
down_revision: str | None = "0012_cierres_hallazgo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE controles_fotos
        ADD COLUMN IF NOT EXISTS respuesta_id UUID NULL
        REFERENCES inspecciones_sqp_respuestas(id) ON DELETE CASCADE;
    """)

    op.execute("""
    ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;
    """)

    op.execute("""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (
            num_nonnulls(punto_id, platica_id, rayser_id, cierre_id, respuesta_id) = 1
        );
    """)

    # PostgreSQL no indexa las llaves foráneas solo, y borrar una inspección
    # recorrería la tabla entera de fotos sin este índice.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_controles_fotos_respuesta
        ON controles_fotos (respuesta_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_controles_fotos_respuesta;")

    op.execute("""
    ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;
    """)

    op.execute("ALTER TABLE controles_fotos DROP COLUMN IF EXISTS respuesta_id;")

    op.execute("""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (num_nonnulls(punto_id, platica_id, rayser_id, cierre_id) = 1);
    """)
