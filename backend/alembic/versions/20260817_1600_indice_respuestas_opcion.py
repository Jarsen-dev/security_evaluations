"""Índice en respuestas.opcion_id para acelerar la verificación de la llave foránea

Revision ID: 0002_indice_respuestas_opcion
Revises: 0001_esquema_inicial
Create Date: 2026-08-17

Motivo (detectado con EXPLAIN ANALYZE en la Fase 8):

``respuestas.opcion_id`` es una llave foránea con ON DELETE SET NULL, pero no
tenía índice. PostgreSQL no crea índices automáticamente para las llaves
foráneas, así que cada DELETE de una opción obligaba a recorrer la tabla
``respuestas`` completa para localizar las filas que la referencian.

Medido con 188 242 respuestas:

    Trigger for constraint respuestas_opcion_id_fkey: time=56.407 calls=1

Esto importa porque al editar un cuestionario se reemplazan todas sus
opciones: un cuestionario de 10 preguntas con 4 opciones son 40 borrados,
es decir ~2.3 segundos solo en verificar la llave foránea, y el costo crece
con el histórico de respuestas.

El índice también ayuda al desglose "cuántos eligieron cada opción" de las
estadísticas y de la hoja "Por pregunta" del Excel.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_indice_respuestas_opcion"
down_revision: str | None = "0001_esquema_inicial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_respuestas_opcion_id
        ON respuestas (opcion_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_respuestas_opcion_id;")
