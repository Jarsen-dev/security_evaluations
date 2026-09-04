"""Control de Insumos: las salidas del almacén

Revision ID: 0020_control_insumos
Revises: 0019_rondines_appsheet
Create Date: 2026-09-03

La pestaña que registra quién se llevó qué insumo y para qué área, y que baja
la existencia del catálogo. Es la primera salida del sistema: hasta ahora la
existencia solo la subían las recepciones y la corregía a mano el catálogo.

**``consumo`` y ``descontado`` son dos columnas y no una.** Lo que se usó y lo
que bajó del inventario no coinciden cuando el producto se mide a granel: usar
20 GR de un tubo de 60 no agota ningún envase, y el inventario cuenta envases.
Derivar uno del otro después obligaría a saber qué regla estaba vigente el día
de la captura.

El CHECK de ``descontado`` se escribe como una función total
(``CASE WHEN termino IS FALSE THEN 0 ELSE consumo END``) y no como la versión
ingenua ``descontado IN (0, consumo)``: aquella dejaría pasar un ``descontado``
en cero para un insumo que sí debía descontarse, que es exactamente la forma de
que el registro y el stock dejen de cuadrar sin que nada falle de forma visible.

Lo que **no** se pone aquí, a propósito: que ``termino`` solo tenga valor
cuando la unidad se consume a granel. Se podría —``unidad_medida`` está en la
misma fila— pero eso metería la lista de unidades parciales dentro de un CHECK,
y agregar una unidad nueva pasaría a exigir una migración. Esa regla vive en el
servicio, junto a las demás que la base no puede o no debe sostener.

Una sentencia por ``execute``: asyncpg las prepara y rechaza los cuerpos con
varias; un bloque ``DO $$`` cuenta como una sola.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_control_insumos"
down_revision: str | None = "0019_rondines_appsheet"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS registros_control_insumos (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fecha          DATE          NOT NULL,
        insumo_id      UUID          NULL REFERENCES insumos(id) ON DELETE SET NULL,
        codigo         VARCHAR(150)  NOT NULL,
        descripcion    VARCHAR(300)  NOT NULL,
        unidad_medida  VARCHAR(10)   NOT NULL,
        entregado_a    VARCHAR(150)  NOT NULL,
        area           VARCHAR(50)   NOT NULL,
        consumo        INTEGER       NOT NULL,
        descontado     INTEGER       NOT NULL,
        termino        BOOLEAN       NULL,
        responsable    VARCHAR(150)  NOT NULL,
        admin_id       UUID          NULL REFERENCES admin_users(id) ON DELETE SET NULL,
        creado_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_control_insumos_consumo'
        ) THEN
            ALTER TABLE registros_control_insumos
                ADD CONSTRAINT ck_control_insumos_consumo CHECK (consumo > 0);
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_control_insumos_descontado'
        ) THEN
            ALTER TABLE registros_control_insumos
                ADD CONSTRAINT ck_control_insumos_descontado CHECK (
                    descontado = CASE WHEN termino IS FALSE THEN 0 ELSE consumo END
                );
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_control_insumos_entregado'
        ) THEN
            ALTER TABLE registros_control_insumos
                ADD CONSTRAINT ck_control_insumos_entregado
                CHECK (length(btrim(entregado_a)) > 0);
        END IF;
    END $$;
    """)

    # El filtro de la pantalla y del Excel es el mes.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_control_insumos_fecha
        ON registros_control_insumos (fecha);
    """)

    # PostgreSQL no indexa las llaves foráneas solo: sin este índice, borrar un
    # insumo del catálogo recorrería la tabla entera para aplicar el SET NULL.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_control_insumos_insumo
        ON registros_control_insumos (insumo_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_control_insumos_insumo;")
    op.execute("DROP INDEX IF EXISTS ix_control_insumos_fecha;")
    op.execute("DROP TABLE IF EXISTS registros_control_insumos;")
