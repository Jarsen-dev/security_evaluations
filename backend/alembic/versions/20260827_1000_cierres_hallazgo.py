"""Cierre de hallazgos: qué se hizo con cada problema detectado en un control

Revision ID: 0012_cierres_hallazgo
Revises: 0011_recepciones
Create Date: 2026-08-27

Hasta ahora un control registraba que algo salió mal —un punto inconforme con
sus observaciones y su foto— y ahí se acababa. Qué se hizo, quién lo resolvió y
a qué hora quedó cerrado no cabía en ningún lado, salvo el bloque "Acción en
caso de anomalía" del formulario de Silos EPS, que solo servía si la solución
ocurría durante la inspección misma.

Tres decisiones que se notan en el SQL:

**Tres llaves foráneas y un CHECK, no un par (control, registro_id).** Un
cierre puede colgar de una hoja de lista de verificación, de una lectura de
Rayser o de una inspección de SQP: tres tablas distintas. Un par polimórfico no
podría tener FK de verdad y dejaría cierres huérfanos al borrar la hoja. Es el
mismo patrón que ya usa ``controles_fotos`` para sus tres dueños, y con
``ON DELETE CASCADE`` borrar una hoja se lleva su cierre sin que ningún
servicio tenga que acordarse.

**Un cierre por hoja.** Los índices únicos son PARCIALES (``WHERE ... IS NOT
NULL``): un UNIQUE normal sobre una columna anulable dejaría pasar un solo NULL
por tabla y bloquearía todos los demás cierres.

**La descripción del problema NO se guarda.** Se deriva al leer, de las
observaciones de los hallazgos de la hoja. Los registros no se editan —solo se
borran—, así que no puede desincronizarse, y guardarla sería tener dos
versiones del mismo texto.

Todo con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base parcialmente
migrada. Una sentencia por ``execute``: asyncpg las prepara y rechaza los
cuerpos con varias; lo único que puede llevar varias es un bloque ``DO $$``,
que cuenta como una sola.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_cierres_hallazgo"
down_revision: str | None = "0011_recepciones"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- El cierre ---------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS cierres_hallazgo (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        checklist_id       UUID NULL
                           REFERENCES registros_checklist(id) ON DELETE CASCADE,
        rayser_id          UUID NULL
                           REFERENCES registros_rayser(id) ON DELETE CASCADE,
        sqp_id             UUID NULL
                           REFERENCES inspecciones_sqp(id) ON DELETE CASCADE,

        hora_hallazgo      VARCHAR(5)   NOT NULL,
        ubicacion          VARCHAR(200) NOT NULL,
        accion_inmediata   TEXT         NOT NULL,
        responsable_accion VARCHAR(150) NOT NULL,
        hora_cierre        VARCHAR(5)   NOT NULL,
        accion_pendiente   TEXT         NULL,

        responsable        VARCHAR(150) NOT NULL,
        admin_id           UUID NULL
                           REFERENCES admin_users(id) ON DELETE SET NULL,
        creado_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at     TIMESTAMPTZ  NULL
    );
    """)

    # Exactamente un dueño. Mismo criterio que `ck_foto_un_solo_dueno`.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_cierre_un_solo_dueno'
        ) THEN
            ALTER TABLE cierres_hallazgo ADD CONSTRAINT ck_cierre_un_solo_dueno
                CHECK (num_nonnulls(checklist_id, rayser_id, sqp_id) = 1);
        END IF;
    END $$;
    """)

    # Un cierre por hoja. Parciales a propósito: ver la nota de arriba.
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_cierre_checklist
        ON cierres_hallazgo (checklist_id) WHERE checklist_id IS NOT NULL;
    """)
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_cierre_rayser
        ON cierres_hallazgo (rayser_id) WHERE rayser_id IS NOT NULL;
    """)
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_cierre_sqp
        ON cierres_hallazgo (sqp_id) WHERE sqp_id IS NOT NULL;
    """)

    # --- Las evidencias de verificación ------------------------------------
    #
    # Van a `controles_fotos`, como todas las imágenes del proyecto. El CHECK
    # de "un solo dueño" tiene que rehacerse para admitir la cuarta llave.
    op.execute("""
    ALTER TABLE controles_fotos
        ADD COLUMN IF NOT EXISTS cierre_id UUID NULL
        REFERENCES cierres_hallazgo(id) ON DELETE CASCADE;
    """)

    op.execute("""
    ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;
    """)

    op.execute("""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (num_nonnulls(punto_id, platica_id, rayser_id, cierre_id) = 1);
    """)

    # PostgreSQL no indexa las llaves foráneas solo, y el borrado en cascada
    # de un cierre recorrería la tabla entera de fotos sin este índice.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_controles_fotos_cierre
        ON controles_fotos (cierre_id);
    """)


def downgrade() -> None:
    # Primero las fotos: su FK apunta a la tabla que se va.
    op.execute("DROP INDEX IF EXISTS ix_controles_fotos_cierre;")

    op.execute("""
    ALTER TABLE controles_fotos DROP CONSTRAINT IF EXISTS ck_foto_un_solo_dueno;
    """)

    # Las evidencias de verificación se van con la columna.
    op.execute("ALTER TABLE controles_fotos DROP COLUMN IF EXISTS cierre_id;")

    op.execute("""
    ALTER TABLE controles_fotos ADD CONSTRAINT ck_foto_un_solo_dueno
        CHECK (num_nonnulls(punto_id, platica_id, rayser_id) = 1);
    """)

    op.execute("DROP TABLE IF EXISTS cierres_hallazgo;")
