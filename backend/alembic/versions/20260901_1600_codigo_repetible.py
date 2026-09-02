"""El código deja de identificar al insumo: ahora es código + descripción

Revision ID: 0017_codigo_repetible
Revises: 0016_stock_piezas
Create Date: 2026-09-01

En planta un mismo código de proveedor ampara varios productos distintos —la
misma clave con presentaciones o contenidos diferentes—, y el índice único
sobre ``lower(codigo)`` lo impedía: había que inventar códigos falsos para dar
de alta lo que en el papel viene con el mismo. Lo que distingue a dos insumos
pasa a ser la pareja **código + descripción**, y esa pareja es la que no se
puede repetir.

Por eso la descripción deja de ser opcional. Tres cosas la sostienen: el
``NOT NULL``, un ``CHECK`` de que no venga en blanco —sin él, dos insumos con
descripción vacía pasarían el ``NOT NULL`` y volverían a ser indistinguibles—
y el índice único compuesto.

``lower(codigo)`` va primero en el índice a propósito: sigue siendo la columna
guía para la búsqueda por igualdad de ``mapa_por_codigo()`` y para el
``ORDER BY`` del catálogo.

El acotado a ``VARCHAR(300)`` no es un capricho de dominio, es lo que hace
indexable la columna: una entrada de btree no pasa de ~2704 bytes, y una
descripción de las 2000 que admitía el schema haría fallar el ``INSERT`` con
``54000 program_limit_exceeded``, que **no es un ``IntegrityError``** y saldría
como 500 en vez del 409 en español. Las descripciones reales de la base miden
entre 15 y 40 caracteres. El ``USING left(...)`` recorta lo que no quepa: sin
él la migración fallaría en una base con descripciones largas, y quedarse a
medias es peor que perder el sobrante de un texto que nadie escribió tan largo.

El ``downgrade()`` **aborta con motivo** si para entonces ya hay códigos
repetidos: degradar el índice a no-único dejaría un esquema que no es el de
``0016`` sin que nadie se entere.

Una sentencia por ``execute``: asyncpg las prepara y rechaza los cuerpos con
varias; un bloque ``DO $$`` cuenta como una sola.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_codigo_repetible"
down_revision: str | None = "0016_stock_piezas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Hoy no toca ninguna fila; está para que la migración sea honesta sobre
    # cualquier base. El código es el único respaldo razonable: inventar un
    # "Sin descripción" metería en la base un texto que nadie capturó.
    op.execute("""
    UPDATE insumos SET descripcion = codigo
    WHERE descripcion IS NULL OR btrim(descripcion) = '';
    """)

    # La guarda evita reescribir la tabla entera en cada re-ejecución.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'insumos'
              AND column_name = 'descripcion'
              AND character_maximum_length = 300
        ) THEN
            ALTER TABLE insumos
                ALTER COLUMN descripcion TYPE VARCHAR(300)
                USING left(descripcion, 300);
        END IF;
    END $$;
    """)

    op.execute("""
    ALTER TABLE insumos ALTER COLUMN descripcion SET NOT NULL;
    """)

    op.execute("""
    ALTER TABLE insumos DROP CONSTRAINT IF EXISTS ck_insumos_descripcion;
    """)

    op.execute("""
    ALTER TABLE insumos ADD CONSTRAINT ck_insumos_descripcion
        CHECK (btrim(descripcion) <> '');
    """)

    # El viejo se tira ANTES de crear el nuevo: mientras siga puesto, sigue
    # rechazando el segundo insumo con el mismo código.
    op.execute("""
    DROP INDEX IF EXISTS uq_insumos_codigo;
    """)

    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_insumos_codigo_descripcion
        ON insumos (lower(codigo), lower(descripcion));
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS uq_insumos_codigo_descripcion;
    """)

    # Volver atrás con códigos repetidos es imposible sin decidir cuál de los
    # insumos se queda, y eso no lo puede decidir una migración.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM insumos GROUP BY lower(codigo) HAVING count(*) > 1
        ) THEN
            RAISE EXCEPTION 'Hay códigos repetidos en insumos'
                USING HINT = 'Consolida o renombra los duplicados antes de '
                             'bajar de la revisión 0017.';
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_insumos_codigo
        ON insumos (lower(codigo));
    """)

    op.execute("""
    ALTER TABLE insumos DROP CONSTRAINT IF EXISTS ck_insumos_descripcion;
    """)

    op.execute("""
    ALTER TABLE insumos ALTER COLUMN descripcion DROP NOT NULL;
    """)
