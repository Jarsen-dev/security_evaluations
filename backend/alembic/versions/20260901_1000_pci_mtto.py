"""Control mensual del mantenimiento al sistema contra incendios (PCI MTTO)

Revision ID: 0015_pci_mtto
Revises: 0014_token_rondin_margen
Create Date: 2026-09-01

El mantenimiento del sistema contra incendios se hace una vez al mes y hasta
ahora no quedaba registrado en ninguna parte: se acordaba de palabra y se
comprobaba a posteriori, cuando ya no había forma de saber si el mes pasado se
hizo. Esta tabla es ese registro, y su rasgo distintivo es que **el sistema la
llena solo cuando nadie contesta**: si un mes cierra sin respuesta, una tarea
periódica levanta la fila con ``realizado = false`` y el motivo en blanco, y el
panel persigue al responsable hasta que lo explique.

No cuelga de ``registros_checklist`` porque no comparte casi nada con las hojas
de lista de verificación: aquellas son diarias, tienen N puntos y solo admiten
fotos; esta es mensual, tiene una sola pregunta y guarda además un **documento**
—el reporte del proveedor—, que es algo que el sistema no sabía hacer en ningún
otro sitio.

Las fotos sí siguen viviendo en ``controles_fotos``, como todas las del
proyecto: solo se suma la sexta llave foránea posible y se rehace el ``CHECK``
de "un solo dueño". El endpoint que las sirve no cambia.

Todo con ``IF NOT EXISTS`` y bloques ``DO $$`` que comprueban el catálogo antes
de tocar nada, para poder re-ejecutarla sobre una base parcialmente migrada.
Una sentencia por ``execute``: asyncpg las prepara y rechaza los cuerpos con
varias; un bloque ``DO $$`` cuenta como una sola.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_pci_mtto"
down_revision: str | None = "0014_token_rondin_margen"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # La tabla va primero: `controles_fotos` la referencia justo después.
    op.execute("""
    CREATE TABLE IF NOT EXISTS registros_pci_mtto (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        anio            INTEGER      NOT NULL,
        mes             INTEGER      NOT NULL,
        fecha           DATE         NULL,
        realizado       BOOLEAN      NOT NULL,
        motivo          TEXT         NULL,
        automatico      BOOLEAN      NOT NULL DEFAULT false,
        reporte         BYTEA        NULL,
        reporte_nombre  VARCHAR(255) NULL,
        reporte_tipo    VARCHAR(120) NULL,
        reporte_tamano  INTEGER      NULL,
        responsable     VARCHAR(150) NOT NULL,
        admin_id        UUID NULL REFERENCES admin_users(id) ON DELETE SET NULL,
        creado_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at  TIMESTAMPTZ  NULL
    );
    """)

    # Un registro por mes. Es además el candado de la tarea automática: con
    # cuatro workers de uvicorn los cuatro calculan los mismos meses por cerrar,
    # y este UNIQUE hace que solo el primero consiga el INSERT.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_pci_anio_mes'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT uq_pci_anio_mes UNIQUE (anio, mes);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pci_mes'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT ck_pci_mes CHECK (mes BETWEEN 1 AND 12);
        END IF;
    END $$;
    """)

    # Un "sí" siempre trae su reporte y su fecha real.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pci_si_lleva_reporte'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT ck_pci_si_lleva_reporte
                CHECK (NOT realizado OR reporte IS NOT NULL);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pci_si_lleva_fecha'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT ck_pci_si_lleva_fecha
                CHECK (NOT realizado OR fecha IS NOT NULL);
        END IF;
    END $$;
    """)

    # Los tres campos del documento van juntos o no va ninguno: un BYTEA sin
    # nombre ni tipo no se puede servir de vuelta.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pci_reporte_completo'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT ck_pci_reporte_completo
                CHECK (num_nonnulls(reporte, reporte_nombre, reporte_tipo) IN (0, 3));
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pci_motivo_util'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT ck_pci_motivo_util
                CHECK (motivo IS NULL OR length(btrim(motivo)) > 0);
        END IF;
    END $$;
    """)

    # El CHECK que sostiene la regla de negocio, y el motivo de que exista la
    # columna `automatico`. El ingenuo —"si NO, entonces motivo"— rompería la
    # tarea periódica, que crea la fila precisamente sin motivo. Este se lee:
    # un registro MANUAL con MTTO=NO y sin motivo es imposible en la base; el
    # único hueco sin motivo lo abre el cierre automático, y es justo el que el
    # panel reclama.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pci_motivo_obligatorio'
        ) THEN
            ALTER TABLE registros_pci_mtto
                ADD CONSTRAINT ck_pci_motivo_obligatorio
                CHECK (realizado OR motivo IS NOT NULL OR automatico);
        END IF;
    END $$;
    """)

    # No se crea índice por `anio`: el único filtro de la pestaña es
    # `WHERE anio = ?`, que ya usa el prefijo izquierdo de `uq_pci_anio_mes`.

    op.execute("""
    ALTER TABLE controles_fotos
        ADD COLUMN IF NOT EXISTS pci_id UUID NULL
        REFERENCES registros_pci_mtto(id) ON DELETE CASCADE;
    """)

    op.execute("""
    ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;
    """)

    op.execute("""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (
            num_nonnulls(punto_id, platica_id, rayser_id, cierre_id,
                         respuesta_id, pci_id) = 1
        );
    """)

    # PostgreSQL no indexa las llaves foráneas solo, y borrar un registro
    # recorrería la tabla entera de fotos sin este índice.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_controles_fotos_pci
        ON controles_fotos (pci_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_controles_fotos_pci;")

    op.execute("""
    ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;
    """)

    op.execute("ALTER TABLE controles_fotos DROP COLUMN IF EXISTS pci_id;")

    # El CHECK vuelve a las cinco llaves de antes de esta migración.
    op.execute("""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (
            num_nonnulls(punto_id, platica_id, rayser_id, cierre_id, respuesta_id) = 1
        );
    """)

    op.execute("DROP TABLE IF EXISTS registros_pci_mtto;")
