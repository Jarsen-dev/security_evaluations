"""Esquema inicial: admins, cuestionarios, preguntas, opciones, intentos, respuestas y metas

Revision ID: 0001_esquema_inicial
Revises:
Create Date: 2026-08-15

Migración escrita a mano (no autogenerada) para cumplir la regla del
proyecto: debe poder re-ejecutarse sobre una base parcialmente migrada sin
fallar. Todo va con IF NOT EXISTS o dentro de bloques DO $$ que consultan el
catálogo antes de crear.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_esquema_inicial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # gen_random_uuid() es nativa desde PostgreSQL 13; no hace falta pgcrypto.

    # --- admin_users -------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username      VARCHAR(50)  NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
        last_login_at TIMESTAMPTZ  NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_admin_users_username'
        ) THEN
            ALTER TABLE admin_users
                ADD CONSTRAINT uq_admin_users_username UNIQUE (username);
        END IF;
    END $$;
    """)

    # --- cuestionarios -----------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS cuestionarios (
        id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        nombre                      VARCHAR(200) NOT NULL,
        descripcion                 TEXT NULL,
        token_publico               VARCHAR(32)  NOT NULL,
        activo                      BOOLEAN      NOT NULL DEFAULT true,
        permitir_multiples_intentos BOOLEAN      NOT NULL DEFAULT false,
        created_at                  TIMESTAMPTZ  NOT NULL DEFAULT now(),
        updated_at                  TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_cuestionarios_token_publico'
        ) THEN
            ALTER TABLE cuestionarios
                ADD CONSTRAINT uq_cuestionarios_token_publico UNIQUE (token_publico);
        END IF;
    END $$;
    """)

    # --- preguntas ---------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS preguntas (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cuestionario_id UUID        NOT NULL
            REFERENCES cuestionarios(id) ON DELETE CASCADE,
        orden           INTEGER     NOT NULL,
        texto           TEXT        NOT NULL,
        puntos          INTEGER     NOT NULL DEFAULT 1,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    # DEFERRABLE INITIALLY DEFERRED: al reordenar preguntas en lote se pasa
    # por estados con órdenes duplicados; la restricción solo debe evaluarse
    # al hacer COMMIT.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_preguntas_cuestionario_orden'
        ) THEN
            ALTER TABLE preguntas
                ADD CONSTRAINT uq_preguntas_cuestionario_orden
                UNIQUE (cuestionario_id, orden)
                DEFERRABLE INITIALLY DEFERRED;
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_preguntas_cuestionario_id
        ON preguntas (cuestionario_id);
    """)

    # --- opciones ----------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS opciones (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pregunta_id UUID    NOT NULL REFERENCES preguntas(id) ON DELETE CASCADE,
        orden       INTEGER NOT NULL,
        texto       TEXT    NOT NULL,
        es_correcta BOOLEAN NOT NULL DEFAULT false
    );
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_opciones_pregunta_id ON opciones (pregunta_id);
    """)

    # --- intentos ----------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS intentos (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cuestionario_id UUID         NOT NULL
            REFERENCES cuestionarios(id) ON DELETE CASCADE,
        nombre          VARCHAR(150) NOT NULL,
        numero_empleado VARCHAR(30)  NOT NULL,
        area            VARCHAR(30)  NOT NULL,
        iniciado_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
        finalizado_at   TIMESTAMPTZ  NULL,
        total_preguntas INTEGER      NOT NULL DEFAULT 0,
        correctas       INTEGER      NOT NULL DEFAULT 0,
        puntaje         NUMERIC(5,2) NULL,
        ip_origen       INET         NULL,
        user_agent      TEXT         NULL
    );
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_intentos_cuestionario_area
        ON intentos (cuestionario_id, area);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_intentos_cuestionario_finalizado
        ON intentos (cuestionario_id, finalizado_at);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_intentos_numero_empleado
        ON intentos (numero_empleado);
    """)

    # Regla de intento único: un empleado no puede tener dos intentos
    # FINALIZADOS del mismo cuestionario. El índice existe siempre; la
    # bandera permitir_multiples_intentos se valida en la capa de servicio,
    # que devuelve 409 con un mensaje claro antes de llegar aquí. El índice
    # es la red de seguridad ante dos envíos concurrentes.
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_intento_unico
        ON intentos (cuestionario_id, numero_empleado)
        WHERE finalizado_at IS NOT NULL;
    """)

    # --- respuestas --------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS respuestas (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        intento_id    UUID        NOT NULL REFERENCES intentos(id)  ON DELETE CASCADE,
        pregunta_id   UUID        NOT NULL REFERENCES preguntas(id) ON DELETE CASCADE,
        opcion_id     UUID        NULL     REFERENCES opciones(id)  ON DELETE SET NULL,
        es_correcta   BOOLEAN     NOT NULL DEFAULT false,
        respondido_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    # Soporta el upsert del autoguardado: ON CONFLICT (intento_id, pregunta_id).
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_respuestas_intento_pregunta'
        ) THEN
            ALTER TABLE respuestas
                ADD CONSTRAINT uq_respuestas_intento_pregunta
                UNIQUE (intento_id, pregunta_id);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_respuestas_pregunta_correcta
        ON respuestas (pregunta_id, es_correcta);
    """)

    # --- metas_area --------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS metas_area (
        area      VARCHAR(30) PRIMARY KEY,
        headcount INTEGER NOT NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_metas_area_headcount_no_negativo'
        ) THEN
            ALTER TABLE metas_area
                ADD CONSTRAINT ck_metas_area_headcount_no_negativo
                CHECK (headcount >= 0);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Orden inverso al de creación. CASCADE cubre las llaves foráneas por si
    # una tabla intermedia ya fue eliminada a mano.
    op.execute("DROP TABLE IF EXISTS metas_area CASCADE;")
    op.execute("DROP TABLE IF EXISTS respuestas CASCADE;")
    op.execute("DROP TABLE IF EXISTS intentos CASCADE;")
    op.execute("DROP TABLE IF EXISTS opciones CASCADE;")
    op.execute("DROP TABLE IF EXISTS preguntas CASCADE;")
    op.execute("DROP TABLE IF EXISTS cuestionarios CASCADE;")
    op.execute("DROP TABLE IF EXISTS admin_users CASCADE;")
