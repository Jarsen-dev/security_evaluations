"""Estudios y capacitaciones con vigencia

Revision ID: 0007_estudios
Revises: 0006_union_admin_controles
Create Date: 2026-08-26

La hoja DETALLE del archivo de estudios entra al sistema como una tabla propia.
No cuelga de los controles ESH: aquellos son un histórico de inspecciones que
no se toca, y cada renglón de aquí es un documento vivo que cambia de estatus
varias veces al año.

Dos ``CHECK`` sostienen desde la base lo que también valida el servicio: la
fecha de vencimiento existe exactamente cuando el vencimiento está "en curso",
y el link solo acompaña a un estudio ya terminado.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_estudios"
down_revision: str | None = "0006_union_admin_controles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Una sentencia por `execute`: asyncpg las prepara y rechaza los cuerpos
    # con varias ("cannot insert multiple commands into a prepared statement").
    op.execute("""
    CREATE TABLE IF NOT EXISTS estudios (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        despacho          VARCHAR(150) NOT NULL,
        estudio           TEXT         NOT NULL,
        estudio_ko        TEXT,
        vigencia          VARCHAR(20)  NOT NULL,
        prioridad         VARCHAR(10)  NOT NULL,
        tipo              VARCHAR(10)  NOT NULL,
        estatus           VARCHAR(10)  NOT NULL,
        vencimiento       VARCHAR(10)  NOT NULL,
        fecha_vencimiento DATE,
        aprobado          VARCHAR(10)  NOT NULL,
        pagado            VARCHAR(10)  NOT NULL,
        link              VARCHAR(500),
        responsable       VARCHAR(150) NOT NULL,
        admin_id          UUID REFERENCES admin_users(id) ON DELETE SET NULL,
        creado_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at    TIMESTAMPTZ,
        CONSTRAINT ck_estudio_fecha_de_vencimiento
            CHECK ((vencimiento = 'en_curso') = (fecha_vencimiento IS NOT NULL)),
        CONSTRAINT ck_estudio_link_solo_con_ok
            CHECK (link IS NULL OR estatus = 'ok')
    );
    """)

    # Sostiene la consulta de avisos, que filtra por fecha de vencimiento.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_estudios_vencimiento "
        "ON estudios (fecha_vencimiento);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS estudios;")
