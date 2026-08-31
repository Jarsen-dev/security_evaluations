"""Da margen al token del QR de los puntos de rondín

Revision ID: 0014_token_rondin_margen
Revises: 0013_fotos_sqp
Create Date: 2026-08-28

`token_publico` se creó como `VARCHAR(32)` y `secrets.token_urlsafe(24)`
produce exactamente 32 caracteres: cabía justo, sin un carácter de sobra.
Subir la entropía del token —lo primero que uno haría si algún día preocupa
que el QR sea la única credencial del punto— habría reventado el INSERT en
producción con un `DataError`, y no hay ningún test que lo atrapara.

Se amplía a 64 para que la longitud del token sea una decisión del servicio y
no un límite accidental de la columna. No se toca el valor de ninguna fila: los
QR ya impresos siguen sirviendo.

Idempotente: comprueba la longitud actual antes de alterar, así que
re-ejecutarla sobre una base ya migrada no hace nada.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014_token_rondin_margen"
down_revision: str | None = "0013_fotos_sqp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'puntos_rondin'
              AND column_name = 'token_publico'
              AND character_maximum_length < 64
        ) THEN
            ALTER TABLE puntos_rondin
                ALTER COLUMN token_publico TYPE VARCHAR(64);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Solo se puede estrechar si ningún token excede los 32 caracteres; si
    # alguno los pasa, se deja como está en vez de truncar credenciales vivas.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM puntos_rondin WHERE length(token_publico) > 32
        ) THEN
            ALTER TABLE puntos_rondin
                ALTER COLUMN token_publico TYPE VARCHAR(32);
        END IF;
    END $$;
    """)
