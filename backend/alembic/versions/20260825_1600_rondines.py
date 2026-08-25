"""Rondines de seguridad: puntos de control y escaneos

Revision ID: 0008_rondines
Revises: 0007_catalogo_insumos
Create Date: 2026-08-25

El seguimiento de rondines vivía en una app aparte de Streamlit que leía un
Google Sheets. Esta migración trae los datos al sistema: los códigos QR de los
puntos los genera y los recibe el propio backend, sin intermediarios.

Tres tablas:

* ``puntos_rondin`` — el catálogo editable de puntos de control. Cada uno lleva
  su ``token_publico``, que es lo que viaja en el QR pegado en el punto.
* ``escaneos_rondin`` — una fila por visita. ``punto_numero`` va desnormalizado
  para que el histórico siga diciendo qué se visitó aunque el punto se borre y
  el FK quede en NULL.
* ``envios_reporte_rondin`` — el candado del reporte automático. En producción
  uvicorn corre con cuatro workers y la tarea programada vive en todos: sin
  esta tabla saldrían cuatro correos por cambio de turno. El primero que gana
  el INSERT envía; los demás chocan con la llave primaria y se callan. Va en la
  base, y no en memoria, para que también sobreviva a un reinicio dentro de la
  ventana de envío.

Todo con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base parcialmente
migrada. Una sentencia por ``execute``: asyncpg las prepara y rechaza los
cuerpos con varias.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_rondines"
down_revision: str | None = "0007_catalogo_insumos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS puntos_rondin (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        numero         INTEGER      NOT NULL,
        nombre         VARCHAR(150) NOT NULL,
        ubicacion      VARCHAR(150),
        token_publico  VARCHAR(32)  NOT NULL,
        activo         BOOLEAN      NOT NULL DEFAULT true,
        creado_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
        actualizado_at TIMESTAMPTZ
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_puntos_rondin_numero'
        ) THEN
            ALTER TABLE puntos_rondin
                ADD CONSTRAINT uq_puntos_rondin_numero UNIQUE (numero);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_puntos_rondin_token'
        ) THEN
            ALTER TABLE puntos_rondin
                ADD CONSTRAINT uq_puntos_rondin_token UNIQUE (token_publico);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS escaneos_rondin (
        id           BIGSERIAL PRIMARY KEY,
        punto_id     UUID REFERENCES puntos_rondin (id) ON DELETE SET NULL,
        punto_numero INTEGER     NOT NULL,
        escaneado_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        ip           INET
    );
    """)

    # El tablero filtra cada consulta por el rango del turno.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_escaneos_rondin_escaneado_at
        ON escaneos_rondin (escaneado_at);
    """)

    # PostgreSQL no indexa las llaves foráneas por su cuenta, y sin esto
    # desactivar o borrar un punto recorrería la tabla de escaneos completa
    # para aplicar el ON DELETE SET NULL.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_escaneos_rondin_punto_id
        ON escaneos_rondin (punto_id);
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS envios_reporte_rondin (
        clave      VARCHAR(40) PRIMARY KEY,
        enviado_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS envios_reporte_rondin;")
    op.execute("DROP TABLE IF EXISTS escaneos_rondin;")
    op.execute("DROP TABLE IF EXISTS puntos_rondin;")
