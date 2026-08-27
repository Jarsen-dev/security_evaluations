"""Catálogo: Nombre pasa a ser Código, y se agrega Unidad de medida

Revision ID: 0010_catalogo_codigo_unidad
Revises: 0009_union_estudios_rondines
Create Date: 2026-08-26

El campo que identificaba a cada insumo dejó de llamarse "Nombre" y pasó a
"Código": sigue siendo el mismo dato (único sin distinguir mayúsculas), solo
cambia su nombre de columna y el de su índice.

Se agrega ``unidad_medida``, obligatoria, con las mismas tres opciones fijas
del selector del panel (TAB, ML, PZA) — validadas en Pydantic, no con un
``CHECK``, igual que ``categoria``.

La tabla puede tener filas reales: la columna nueva se agrega con
``DEFAULT 'PZA'`` para no romper el ``NOT NULL`` sobre lo ya capturado, y el
``DEFAULT`` se retira enseguida. Ninguna fila nueva debe poder guardarse sin
que el usuario elija la unidad explícitamente — igual que pasa hoy con
``categoria``, que tampoco tiene default.

Todo con guardas para poder re-ejecutar la migración sobre una base
parcialmente migrada: ``RENAME COLUMN`` y ``RENAME INDEX`` no son idempotentes
por sí solos, así que van dentro de un ``DO $$`` que primero comprueba que el
nombre viejo todavía exista.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_catalogo_codigo_unidad"
down_revision: str | None = "0009_union_estudios_rondines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos' AND column_name = 'nombre'
        ) THEN
            ALTER TABLE insumos RENAME COLUMN nombre TO codigo;
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_class WHERE relname = 'uq_insumos_nombre'
        ) THEN
            ALTER INDEX uq_insumos_nombre RENAME TO uq_insumos_codigo;
        END IF;
    END $$;
    """)

    op.execute("""
    ALTER TABLE insumos ADD COLUMN IF NOT EXISTS unidad_medida VARCHAR(10)
        NOT NULL DEFAULT 'PZA';
    """)

    # No es idempotencia lo que se busca aquí sino no dejar el default
    # puesto: quitarlo dos veces no falla.
    op.execute("""
    ALTER TABLE insumos ALTER COLUMN unidad_medida DROP DEFAULT;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE insumos DROP COLUMN IF EXISTS unidad_medida;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM pg_class WHERE relname = 'uq_insumos_codigo'
        ) THEN
            ALTER INDEX uq_insumos_codigo RENAME TO uq_insumos_nombre;
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos' AND column_name = 'codigo'
        ) THEN
            ALTER TABLE insumos RENAME COLUMN codigo TO nombre;
        END IF;
    END $$;
    """)
