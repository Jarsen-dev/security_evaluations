"""Controles ESH: registros de Rayser e inspecciones de SQP

Revision ID: 0003_controles_esh
Revises: 0002_indice_respuestas_opcion
Create Date: 2026-08-24

El sistema deja de ser solo de evaluaciones y absorbe los formatos de
inspección del departamento de seguridad. Esta migración crea las tres tablas
que necesitan los dos primeros controles:

* ``registros_rayser`` — la lectura diaria de los cuatro manómetros, con la
  foto de evidencia embebida cuando alguna sale del rango normal.
* ``inspecciones_sqp`` y ``inspecciones_sqp_respuestas`` — la inspección de
  sustancias químicas peligrosas, con una fila por punto del formato.

Todo se escribe con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base
parcialmente migrada.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_controles_esh"
down_revision: str | None = "0002_indice_respuestas_opcion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS registros_rayser (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fecha         DATE          NOT NULL,
        manometro_1   NUMERIC(5, 1) NOT NULL,
        manometro_2   NUMERIC(5, 1) NOT NULL,
        manometro_3   NUMERIC(5, 1) NOT NULL,
        manometro_4   NUMERIC(5, 1) NOT NULL,
        observaciones TEXT,
        foto          BYTEA,
        foto_tipo     VARCHAR(60),
        responsable   VARCHAR(150)  NOT NULL,
        admin_id      UUID REFERENCES admin_users (id) ON DELETE SET NULL,
        creado_at     TIMESTAMPTZ   NOT NULL DEFAULT now()
    );
    """)

    # Una lectura por día, igual que el formato mensual en papel.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_rayser_fecha'
        ) THEN
            ALTER TABLE registros_rayser
                ADD CONSTRAINT uq_rayser_fecha UNIQUE (fecha);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_registros_rayser_fecha
        ON registros_rayser (fecha);
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inspecciones_sqp (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fecha       DATE         NOT NULL,
        area        VARCHAR(30)  NOT NULL,
        encargado   VARCHAR(150) NOT NULL,
        cargo       VARCHAR(100),
        sustancias  TEXT,
        responsable VARCHAR(150) NOT NULL,
        admin_id    UUID REFERENCES admin_users (id) ON DELETE SET NULL,
        creado_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_inspecciones_sqp_fecha
        ON inspecciones_sqp (fecha);
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS inspecciones_sqp_respuestas (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        inspeccion_id UUID        NOT NULL
                      REFERENCES inspecciones_sqp (id) ON DELETE CASCADE,
        orden         INTEGER     NOT NULL,
        codigo        VARCHAR(10) NOT NULL,
        valor         VARCHAR(3)  NOT NULL,
        observaciones TEXT
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_sqp_respuesta_orden'
        ) THEN
            ALTER TABLE inspecciones_sqp_respuestas
                ADD CONSTRAINT uq_sqp_respuesta_orden UNIQUE (inspeccion_id, orden);
        END IF;
    END $$;
    """)

    # PostgreSQL no indexa las llaves foráneas por su cuenta: sin esto, borrar
    # una inspección recorrería la tabla de respuestas completa para aplicar el
    # ON DELETE CASCADE.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_sqp_respuestas_inspeccion
        ON inspecciones_sqp_respuestas (inspeccion_id);
    """)


def downgrade() -> None:
    # Orden inverso: las respuestas dependen de la inspección.
    op.execute("DROP TABLE IF EXISTS inspecciones_sqp_respuestas;")
    op.execute("DROP TABLE IF EXISTS inspecciones_sqp;")
    op.execute("DROP TABLE IF EXISTS registros_rayser;")
