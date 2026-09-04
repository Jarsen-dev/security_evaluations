"""Control de Extintores: fichas, revisión diaria y evidencia

Revision ID: 0021_extintores
Revises: 0020_control_insumos
Create Date: 2026-09-04

Los 160 extintores de la planta, cada uno con su ficha, su vencimiento y una
revisión de doce puntos al día.

**Por qué no comparte `registros_checklist`.** Los controles de lista de
verificación son *una hoja de N puntos al día para toda la planta*; aquí son *N
aparatos identificados por doce puntos cada uno*, y además hace falta una ficha
con modelo, capacidad, tipo, ubicación y vencimiento que aquella tabla no tiene
dónde guardar. Forzar el `discriminador` habría dejado la ficha fuera igual.

**Dos llaves se suman a tablas que ya existen**, que es la receta que estrenó
PCI MTTO en `controles_fotos`:

- `controles_fotos.punto_extintor_id` — la evidencia cuelga del PUNTO que salió
  NO OK, como en los checklist.
- `cierres_hallazgo.revision_extintor_id` — la cuarta procedencia de un cierre.

Los dos ``CHECK`` de "solo un dueño" se tiran y se rehacen **siempre**, no solo
si faltan: la guarda habitual —"si no existe, créalo"— daría por bueno el CHECK
viejo, que sigue existiendo con el mismo nombre y sin la llave nueva, y el
constraint quedaría sin aplicar la regla nueva sin que nada falle de forma
visible. Es la misma trampa que documenta la migración de `stock_piezas`.

El índice único del cierre va **PARCIAL** por el mismo motivo que los otros
tres: un UNIQUE normal sobre columna anulable dejaría pasar un solo NULL y
bloquearía todos los demás cierres.

Una sentencia por ``execute``: asyncpg las prepara y rechaza los cuerpos con
varias; un bloque ``DO $$`` cuenta como una sola.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_extintores"
down_revision: str | None = "0020_control_insumos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LLAVES_FOTO_ANTES = "punto_id, platica_id, rayser_id, cierre_id, respuesta_id, pci_id"
LLAVES_FOTO_AHORA = f"{LLAVES_FOTO_ANTES}, punto_extintor_id"

LLAVES_CIERRE_ANTES = "checklist_id, rayser_id, sqp_id"
LLAVES_CIERRE_AHORA = f"{LLAVES_CIERRE_ANTES}, revision_extintor_id"


def upgrade() -> None:
    # --- La ficha ----------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS extintores (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        folio          VARCHAR(20)  NOT NULL,
        modelo         VARCHAR(100) NOT NULL,
        capacidad      VARCHAR(50)  NOT NULL,
        tipo           VARCHAR(10)  NOT NULL,
        ubicacion      VARCHAR(150) NOT NULL,
        vencimiento    DATE         NOT NULL,
        creado_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at TIMESTAMPTZ  NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_extintores_folio'
        ) THEN
            ALTER TABLE extintores
                ADD CONSTRAINT uq_extintores_folio UNIQUE (folio);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_extintores_folio'
        ) THEN
            ALTER TABLE extintores ADD CONSTRAINT ck_extintores_folio
                CHECK (length(btrim(folio)) > 0);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_extintores_vencimiento
        ON extintores (vencimiento);
    """)

    # --- La revisión diaria ------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS extintores_revisiones (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        extintor_id    UUID         NULL REFERENCES extintores(id) ON DELETE SET NULL,
        folio          VARCHAR(20)  NOT NULL,
        modelo         VARCHAR(100) NOT NULL,
        tipo           VARCHAR(10)  NOT NULL,
        ubicacion      VARCHAR(150) NOT NULL,
        fecha          DATE         NOT NULL,
        anomalias      INTEGER      NOT NULL,
        responsable    VARCHAR(150) NOT NULL,
        admin_id       UUID         NULL REFERENCES admin_users(id) ON DELETE SET NULL,
        creado_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at TIMESTAMPTZ  NULL
    );
    """)

    # Una por extintor y por día. Los NULL de las fichas eliminadas no chocan
    # entre sí, que es justo lo que se quiere: varios aparatos retirados pueden
    # tener revisiones del mismo día.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_revision_extintor_fecha'
        ) THEN
            ALTER TABLE extintores_revisiones
                ADD CONSTRAINT uq_revision_extintor_fecha UNIQUE (extintor_id, fecha);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_revision_anomalias'
        ) THEN
            ALTER TABLE extintores_revisiones
                ADD CONSTRAINT ck_revision_anomalias CHECK (anomalias >= 0);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_extintores_revisiones_fecha
        ON extintores_revisiones (fecha);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_extintores_revisiones_extintor
        ON extintores_revisiones (extintor_id);
    """)

    # --- Los doce puntos ---------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS extintores_revisiones_puntos (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        revision_id   UUID        NOT NULL
                      REFERENCES extintores_revisiones(id) ON DELETE CASCADE,
        orden         INTEGER     NOT NULL,
        clave         VARCHAR(40) NOT NULL,
        valor         VARCHAR(6)  NOT NULL,
        observaciones TEXT        NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_punto_extintor_orden'
        ) THEN
            ALTER TABLE extintores_revisiones_puntos
                ADD CONSTRAINT uq_punto_extintor_orden UNIQUE (revision_id, orden);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_punto_extintor_valor'
        ) THEN
            ALTER TABLE extintores_revisiones_puntos
                ADD CONSTRAINT ck_punto_extintor_valor
                CHECK (valor IN ('ok', 'no_ok'));
        END IF;
    END $$;
    """)

    # Un hallazgo sin explicar no sirve como evidencia, y el servicio no puede
    # ser la única red que lo impida.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_punto_extintor_observaciones'
        ) THEN
            ALTER TABLE extintores_revisiones_puntos
                ADD CONSTRAINT ck_punto_extintor_observaciones
                CHECK (valor = 'ok' OR (observaciones IS NOT NULL
                                        AND length(btrim(observaciones)) > 0));
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_extintores_puntos_revision
        ON extintores_revisiones_puntos (revision_id);
    """)

    # --- La séptima llave de las fotos -------------------------------------
    op.execute("""
    ALTER TABLE controles_fotos
        ADD COLUMN IF NOT EXISTS punto_extintor_id UUID NULL
        REFERENCES extintores_revisiones_puntos(id) ON DELETE CASCADE;
    """)
    op.execute(
        "ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;"
    )
    op.execute(f"""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (num_nonnulls({LLAVES_FOTO_AHORA}) = 1);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_controles_fotos_punto_extintor
        ON controles_fotos (punto_extintor_id);
    """)

    # --- La cuarta llave de los cierres ------------------------------------
    op.execute("""
    ALTER TABLE cierres_hallazgo
        ADD COLUMN IF NOT EXISTS revision_extintor_id UUID NULL
        REFERENCES extintores_revisiones(id) ON DELETE CASCADE;
    """)
    op.execute(
        "ALTER TABLE cierres_hallazgo DROP CONSTRAINT IF EXISTS ck_cierre_un_solo_dueno;"
    )
    op.execute(f"""
    ALTER TABLE cierres_hallazgo ADD CONSTRAINT ck_cierre_un_solo_dueno
        CHECK (num_nonnulls({LLAVES_CIERRE_AHORA}) = 1);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_cierres_hallazgo_extintor
        ON cierres_hallazgo (revision_extintor_id);
    """)
    # Un cierre por revisión. Parcial, o el único NULL permitido bloquearía
    # todos los cierres de los demás controles.
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_cierre_extintor
        ON cierres_hallazgo (revision_extintor_id)
        WHERE revision_extintor_id IS NOT NULL;
    """)


def downgrade() -> None:
    # Los CHECK vuelven a su forma anterior ANTES de tirar las columnas, o el
    # ALTER fallaría por dependencia.
    op.execute("DROP INDEX IF EXISTS uq_cierre_extintor;")
    op.execute("DROP INDEX IF EXISTS ix_cierres_hallazgo_extintor;")
    op.execute(
        "ALTER TABLE cierres_hallazgo DROP CONSTRAINT IF EXISTS ck_cierre_un_solo_dueno;"
    )
    op.execute("ALTER TABLE cierres_hallazgo DROP COLUMN IF EXISTS revision_extintor_id;")
    op.execute(f"""
    ALTER TABLE cierres_hallazgo ADD CONSTRAINT ck_cierre_un_solo_dueno
        CHECK (num_nonnulls({LLAVES_CIERRE_ANTES}) = 1);
    """)

    op.execute("DROP INDEX IF EXISTS ix_controles_fotos_punto_extintor;")
    op.execute(
        "ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;"
    )
    op.execute("ALTER TABLE controles_fotos DROP COLUMN IF EXISTS punto_extintor_id;")
    op.execute(f"""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (num_nonnulls({LLAVES_FOTO_ANTES}) = 1);
    """)

    op.execute("DROP TABLE IF EXISTS extintores_revisiones_puntos;")
    op.execute("DROP TABLE IF EXISTS extintores_revisiones;")
    op.execute("DROP TABLE IF EXISTS extintores;")
