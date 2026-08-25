"""Controles de lista de verificación, pláticas ESH y fotos unificadas

Revision ID: 0005_controles_checklist
Revises: 0004_usuarios_y_bitacora
Create Date: 2026-08-24

Se habilitan cuatro controles más del libro de inspecciones:

* ``registros_checklist`` y ``registros_checklist_puntos`` — las tres hojas de
  OK / NO OK (almacén de residuos peligrosos, recorridos perimetrales y
  revisión de muros), que comparten forma y se distinguen por ``control``.
* ``platicas_esh`` y ``platicas_esh_areas`` — las pláticas diarias de
  seguridad, con las áreas donde se impartió cada una.

Y, sobre todo, ``controles_fotos``: un registro ahora puede llevar **varias**
fotos de evidencia. La tabla sirve a los tres orígenes con un ``CHECK`` que
obliga a que solo una llave foránea venga llena, así que las columnas ``foto``
y ``foto_tipo`` de ``registros_rayser`` se migran aquí y desaparecen.

Todo se escribe con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base
parcialmente migrada.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_controles_checklist"
down_revision: str | None = "0004_usuarios_y_bitacora"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Listas de verificación --------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS registros_checklist (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        control     VARCHAR(30)  NOT NULL,
        fecha       DATE         NOT NULL,
        responsable VARCHAR(150) NOT NULL,
        admin_id    UUID REFERENCES admin_users (id) ON DELETE SET NULL,
        creado_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    # Una hoja por día y por control, igual que el formato en papel.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_checklist_control_fecha'
        ) THEN
            ALTER TABLE registros_checklist
                ADD CONSTRAINT uq_checklist_control_fecha UNIQUE (control, fecha);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_registros_checklist_control_fecha
        ON registros_checklist (control, fecha);
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS registros_checklist_puntos (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        registro_id   UUID        NOT NULL
                      REFERENCES registros_checklist (id) ON DELETE CASCADE,
        orden         INTEGER     NOT NULL,
        clave         VARCHAR(40) NOT NULL,
        valor         VARCHAR(6)  NOT NULL,
        observaciones TEXT
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_checklist_punto_orden'
        ) THEN
            ALTER TABLE registros_checklist_puntos
                ADD CONSTRAINT uq_checklist_punto_orden UNIQUE (registro_id, orden);
        END IF;
    END $$;
    """)

    # PostgreSQL no indexa las llaves foráneas por su cuenta: sin esto, borrar
    # un registro recorre la tabla completa para aplicar el ON DELETE CASCADE.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_checklist_puntos_registro
        ON registros_checklist_puntos (registro_id);
    """)

    # --- Pláticas diarias de seguridad -------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS platicas_esh (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fecha       DATE         NOT NULL,
        tema        VARCHAR(300) NOT NULL,
        responsable VARCHAR(150) NOT NULL,
        admin_id    UUID REFERENCES admin_users (id) ON DELETE SET NULL,
        creado_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    # Sin UNIQUE sobre la fecha: en un día puede haber varias pláticas.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_platicas_esh_fecha ON platicas_esh (fecha);
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS platicas_esh_areas (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        platica_id UUID        NOT NULL
                   REFERENCES platicas_esh (id) ON DELETE CASCADE,
        clave      VARCHAR(20) NOT NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_platica_area'
        ) THEN
            ALTER TABLE platicas_esh_areas
                ADD CONSTRAINT uq_platica_area UNIQUE (platica_id, clave);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_platicas_areas_platica
        ON platicas_esh_areas (platica_id);
    """)

    # --- Fotos de evidencia, compartidas por los tres orígenes -------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS controles_fotos (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        punto_id   UUID REFERENCES registros_checklist_puntos (id) ON DELETE CASCADE,
        platica_id UUID REFERENCES platicas_esh (id) ON DELETE CASCADE,
        rayser_id  UUID REFERENCES registros_rayser (id) ON DELETE CASCADE,
        imagen     BYTEA       NOT NULL,
        tipo       VARCHAR(60) NOT NULL,
        orden      INTEGER     NOT NULL DEFAULT 0,
        creado_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_foto_un_solo_dueno'
        ) THEN
            ALTER TABLE controles_fotos
                ADD CONSTRAINT ck_foto_un_solo_dueno
                CHECK (num_nonnulls(punto_id, platica_id, rayser_id) = 1);
        END IF;
    END $$;
    """)

    for columna in ("punto_id", "platica_id", "rayser_id"):
        op.execute(f"""
        CREATE INDEX IF NOT EXISTS ix_controles_fotos_{columna.removesuffix('_id')}
            ON controles_fotos ({columna});
        """)

    # --- Rayser: su foto se muda a la tabla compartida ---------------------
    #
    # Se comprueba la columna antes de tocarla para que re-ejecutar la
    # migración sobre una base ya migrada no falle ni duplique las fotos.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'registros_rayser' AND column_name = 'foto'
        ) THEN
            INSERT INTO controles_fotos (rayser_id, imagen, tipo, orden)
            SELECT id, foto, COALESCE(foto_tipo, 'image/jpeg'), 0
            FROM registros_rayser
            WHERE foto IS NOT NULL;

            ALTER TABLE registros_rayser DROP COLUMN foto;
            ALTER TABLE registros_rayser DROP COLUMN IF EXISTS foto_tipo;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Rayser recupera sus columnas con la primera foto de cada registro; si
    # tenía varias, las demás se pierden (la estructura vieja no las admite).
    # Una sentencia por `execute`: asyncpg las prepara y rechaza los cuerpos
    # con varias ("cannot insert multiple commands into a prepared statement").
    op.execute("ALTER TABLE registros_rayser ADD COLUMN IF NOT EXISTS foto BYTEA;")
    op.execute(
        "ALTER TABLE registros_rayser ADD COLUMN IF NOT EXISTS foto_tipo VARCHAR(60);"
    )

    op.execute("""
    UPDATE registros_rayser AS r
    SET foto = f.imagen, foto_tipo = f.tipo
    FROM (
        SELECT DISTINCT ON (rayser_id) rayser_id, imagen, tipo
        FROM controles_fotos
        WHERE rayser_id IS NOT NULL
        ORDER BY rayser_id, orden
    ) AS f
    WHERE f.rayser_id = r.id;
    """)

    # Orden inverso: las fotos y los puntos dependen de sus registros.
    op.execute("DROP TABLE IF EXISTS controles_fotos;")
    op.execute("DROP TABLE IF EXISTS platicas_esh_areas;")
    op.execute("DROP TABLE IF EXISTS platicas_esh;")
    op.execute("DROP TABLE IF EXISTS registros_checklist_puntos;")
    op.execute("DROP TABLE IF EXISTS registros_checklist;")
