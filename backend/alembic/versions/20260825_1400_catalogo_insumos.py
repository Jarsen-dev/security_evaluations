"""Catálogo de insumos de seguridad

Revision ID: 0007_catalogo_insumos
Revises: 0006_union_admin_controles
Create Date: 2026-08-25

El departamento llevaba en un Excel el catálogo de sus insumos de seguridad:
medicamentos del botiquín, EPP, señalización y extintores. Esta migración crea
la tabla que los recibe.

Es un catálogo, no un almacén. ``cantidad`` se captura a mano tras el conteo y
es una columna propia, no un valor derivado: más adelante se construirá encima
un sistema de recepciones y salidas, y ese día la tabla de movimientos
referenciará ``insumos.id`` sin obligar a migrar lo ya capturado.

Dos decisiones que se notan en el SQL:

El índice único va sobre ``lower(nombre)``, no sobre ``nombre``. El nombre es
lo que identifica a un insumo, y sin bajar la caja "Guantes de nitrilo" y
"guantes de nitrilo" serían dos renglones distintos que la importación
duplicaría en cada carga.

El ``CHECK`` exige ``maximo >= minimo`` porque un rango invertido rompe el
semáforo en silencio: todo saldría a la vez bajo el mínimo y sobre el máximo.
Los schemas de Pydantic aplican la misma regla para que el usuario vea un 422
legible en vez de un 500 de la base.

Todo se escribe con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base
parcialmente migrada. Una sentencia por ``execute``: asyncpg las prepara y
rechaza los cuerpos con varias.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_catalogo_insumos"
down_revision: str | None = "0006_union_admin_controles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS insumos (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        nombre         VARCHAR(150) NOT NULL,
        descripcion    TEXT,
        categoria      VARCHAR(30)  NOT NULL,
        proveedor      VARCHAR(150),
        ubicacion      VARCHAR(150),
        cantidad       INTEGER      NOT NULL DEFAULT 0,
        minimo         INTEGER      NOT NULL DEFAULT 0,
        maximo         INTEGER      NOT NULL DEFAULT 0,
        creado_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at TIMESTAMPTZ
    );
    """)

    # El nombre identifica al insumo, sin distinguir mayúsculas.
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_insumos_nombre
        ON insumos (lower(nombre));
    """)

    # El listado filtra por categoría en cada carga de la pantalla.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_insumos_categoria ON insumos (categoria);
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_insumos_rango'
        ) THEN
            ALTER TABLE insumos ADD CONSTRAINT ck_insumos_rango CHECK (
                cantidad >= 0 AND minimo >= 0 AND maximo >= minimo
            );
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS insumos;")
