"""Sella las recepciones que estrenaron un formato y quedaron en «desconocido»

Revision ID: 0018_sellar_formato
Revises: 0017_codigo_repetible
Create Date: 2026-09-01

El formato de un documento se bautiza **después** de crear la recepción, así
que la recepción con la que se enseña un formato se guardaba con
``tipo_documento = 'desconocido'`` para siempre: el historial no la encontraba
bajo el formato que ella misma definió. El código ya no lo hace —el sellado va
en el mismo paso que el aprendizaje—, pero las filas que ya están mal hay que
repararlas.

La reparación es **deliberadamente conservadora**: solo sella una recepción
cuando su folio y su proveedor coinciden con los del ejemplo curado del
formato, ambos no nulos, y **la coincidencia es única**. Ante la duda prefiere
no tocar nada: sellar la recepción equivocada sería peor que dejarla como
desconocida.

Es idempotente por construcción: solo mira las que siguen en «desconocido».

``downgrade()`` es un **no-op a propósito** y no un descuido. Deshacerlo sería
volver a poner en «desconocido» todas las recepciones de esos formatos, y no
hay forma de distinguir las que esta migración tocó de las que se sellaron
solas después. Perder ese dato es peor que no poder revertirlo.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_sellar_formato"
down_revision: str | None = "0017_codigo_repetible"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    UPDATE recepciones AS r
    SET tipo_documento = p.slug
    FROM recepciones_plantilla_ejemplos AS e
    JOIN recepciones_plantillas AS p ON p.id = e.plantilla_id
    WHERE r.tipo_documento = 'desconocido'
      AND e.clase = 'curado'
      AND r.folio IS NOT NULL
      AND r.proveedor IS NOT NULL
      AND e.json_esperado ->> 'folio' = r.folio
      AND e.json_esperado ->> 'proveedor' = r.proveedor
      AND (
          SELECT count(*)
          FROM recepciones AS otra
          WHERE otra.tipo_documento = 'desconocido'
            AND otra.folio = r.folio
            AND otra.proveedor = r.proveedor
      ) = 1;
    """)


def downgrade() -> None:
    """No-op: ver el docstring del módulo."""
