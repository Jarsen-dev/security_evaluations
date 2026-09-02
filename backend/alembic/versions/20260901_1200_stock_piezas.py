"""Inventario real: piezas por empaque y existencia separadas

Revision ID: 0016_stock_piezas
Revises: 0015_pci_mtto
Create Date: 2026-09-01

``insumos.cantidad`` cargaba con dos significados a la vez. En planta el campo
se llenaba con **el contenido de cada caja** —las pastillas de un blíster, las
piezas de un paquete—, pero el sistema lo trataba como la existencia y le
sumaba cada recepción encima. El resultado era un número que no era ninguna de
las dos cosas, y el inventario real no vivía en ninguna columna.

Aquí se separan:

- ``cantidad`` se **renombra** a ``piezas_por_empaque``, que es lo que de hecho
  se capturó ahí. Se conserva el valor: pedir que se recapture producto por
  producto sería peor.
- ``existencia`` es nueva y arranca en **0**, para todos. No se reconstruye
  sumando el histórico de recepciones a propósito: esas partidas se guardaron
  en cajas cuando el sistema las trataba como piezas, así que el total saldría
  inventado. El conteo físico se captura a mano desde el panel del catálogo.

``recepciones_items`` gana el snapshot ``piezas_por_empaque``, igual que ya
guarda ``descripcion`` y ``unidad_medida``: el documento histórico no debe
cambiar porque el proveedor cambie la presentación. Las filas anteriores
quedan en 1, que es **falso** —nadie sabe qué presentación tenían—, pero da
igual: ninguna de ellas alimenta la existencia, que empieza de cero.

``recepciones_items.cantidad`` **no** se renombra: ahí sigue guardándose lo que
teclea el operador, que son cajas. Renombrarla "por simetría" rompería el
histórico y el corpus del clasificador de remisiones.

Sobre la idempotencia hay una trampa que no tiene precedente en este proyecto:
PostgreSQL **reescribe la expresión de los CHECK** al renombrar una columna, y
les deja el mismo nombre. Después del rename, ``ck_insumos_rango`` sigue
existiendo (ya como ``piezas_por_empaque >= 0 AND ...``), así que la guarda
habitual —"si no existe el constraint, créalo"— lo daría por bueno y nunca
aplicaría la regla nueva, sin que nada falle de forma visible. Por eso el
constraint se tira con ``DROP ... IF EXISTS`` y se vuelve a crear siempre.

Una sentencia por ``execute``: asyncpg las prepara y rechaza los cuerpos con
varias; un bloque ``DO $$`` cuenta como una sola.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_stock_piezas"
down_revision: str | None = "0015_pci_mtto"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # La guarda mira las DOS columnas y no solo la vieja: si una corrida a
    # medias dejó ambas, el rename fallaría con "column already exists".
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos' AND column_name = 'cantidad'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos' AND column_name = 'piezas_por_empaque'
        ) THEN
            ALTER TABLE insumos RENAME COLUMN cantidad TO piezas_por_empaque;
        END IF;
    END $$;
    """)

    op.execute("""
    ALTER TABLE insumos ADD COLUMN IF NOT EXISTS existencia INTEGER
        NOT NULL DEFAULT 0;
    """)

    # Va DESPUÉS del rename: escrito contra `cantidad` reventaría con
    # UndefinedColumn al re-ejecutar sobre una base ya migrada. Los ceros que
    # dejó el default viejo no pueden quedarse: una caja trae al menos una
    # pieza, y con cero la recepción daría entrada a nada.
    op.execute("""
    UPDATE insumos SET piezas_por_empaque = 1 WHERE piezas_por_empaque < 1;
    """)

    # El DEFAULT viaja con la columna al renombrarla, así que `cantidad
    # DEFAULT 0` quedaría como `piezas_por_empaque DEFAULT 0`, en contra del
    # CHECK que se pone abajo: un INSERT que no nombrara la columna fallaría.
    op.execute("""
    ALTER TABLE insumos ALTER COLUMN piezas_por_empaque SET DEFAULT 1;
    """)

    op.execute("""
    ALTER TABLE insumos DROP CONSTRAINT IF EXISTS ck_insumos_rango;
    """)

    op.execute("""
    ALTER TABLE insumos ADD CONSTRAINT ck_insumos_rango CHECK (
        existencia >= 0
        AND piezas_por_empaque >= 1
        AND minimo >= 0
        AND maximo >= minimo
    );
    """)

    # El DEFAULT existe solo para no romper el NOT NULL sobre las partidas ya
    # guardadas; se retira enseguida para que ninguna fila nueva pueda
    # guardarse sin su snapshot explícito.
    op.execute("""
    ALTER TABLE recepciones_items ADD COLUMN IF NOT EXISTS piezas_por_empaque
        INTEGER NOT NULL DEFAULT 1;
    """)

    op.execute("""
    ALTER TABLE recepciones_items ALTER COLUMN piezas_por_empaque DROP DEFAULT;
    """)

    op.execute("""
    ALTER TABLE recepciones_items
        DROP CONSTRAINT IF EXISTS ck_recepcion_item_piezas;
    """)

    op.execute("""
    ALTER TABLE recepciones_items ADD CONSTRAINT ck_recepcion_item_piezas
        CHECK (piezas_por_empaque >= 1);
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE recepciones_items
        DROP CONSTRAINT IF EXISTS ck_recepcion_item_piezas;
    """)

    op.execute("""
    ALTER TABLE recepciones_items DROP COLUMN IF EXISTS piezas_por_empaque;
    """)

    op.execute("""
    ALTER TABLE insumos DROP CONSTRAINT IF EXISTS ck_insumos_rango;
    """)

    # Vuelve el nombre viejo antes de recrear el CHECK: la expresión original
    # habla de `cantidad`.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos' AND column_name = 'piezas_por_empaque'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos' AND column_name = 'cantidad'
        ) THEN
            ALTER TABLE insumos RENAME COLUMN piezas_por_empaque TO cantidad;
        END IF;
    END $$;
    """)

    op.execute("""
    ALTER TABLE insumos ALTER COLUMN cantidad SET DEFAULT 0;
    """)

    op.execute("""
    ALTER TABLE insumos DROP COLUMN IF EXISTS existencia;
    """)

    op.execute("""
    ALTER TABLE insumos ADD CONSTRAINT ck_insumos_rango CHECK (
        cantidad >= 0 AND minimo >= 0 AND maximo >= minimo
    );
    """)
