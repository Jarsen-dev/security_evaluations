"""Formatos por inspección: encabezado, secciones y mediciones

Revision ID: 0005_checklist_formato
Revises: 0004_controles_checklist
Create Date: 2026-08-25

Las dos hojas que faltaban del libro de inspecciones —silos EPS y tableros
eléctricos— no son rejillas mensuales como las tres anteriores, sino formatos
por inspección: traen encabezado propio (planta, turno, inspector, número de
tablero), bloques extra al pie y, en tableros, mediciones de temperatura. Y en
un mismo día se llenan varias: una por turno, o una por tablero y turno.

En vez de tablas nuevas, las que ya existen crecen:

* ``discriminador`` es lo que distingue dos inspecciones del mismo día. Vacío
  en los controles de rejilla, así que la restricción de unicidad sigue
  significando "una hoja por día" para ellos sin listar claves de control
  dentro de la base.
* ``encabezado`` y ``secciones`` guardan los campos del formato como JSONB:
  son metadatos del documento, nunca se agregan, y su forma la define y la
  valida el catálogo.
* ``medicion`` guarda la lectura de los puntos que la piden.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_checklist_formato"
down_revision: str | None = "0004_controles_checklist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Una sentencia por `execute`: asyncpg las prepara y rechaza los cuerpos
    # con varias ("cannot insert multiple commands into a prepared statement").
    op.execute(
        "ALTER TABLE registros_checklist "
        "ADD COLUMN IF NOT EXISTS discriminador VARCHAR(80) NOT NULL DEFAULT '';"
    )
    op.execute(
        "ALTER TABLE registros_checklist "
        "ADD COLUMN IF NOT EXISTS encabezado JSONB NOT NULL DEFAULT '{}'::jsonb;"
    )
    op.execute(
        "ALTER TABLE registros_checklist "
        "ADD COLUMN IF NOT EXISTS secciones JSONB NOT NULL DEFAULT '{}'::jsonb;"
    )
    op.execute(
        "ALTER TABLE registros_checklist_puntos "
        "ADD COLUMN IF NOT EXISTS medicion VARCHAR(40);"
    )

    # La restricción pasa de (control, fecha) a (control, fecha, discriminador).
    # Se comprueba antes de tocarla para poder re-ejecutar la migración sobre
    # una base ya migrada.
    op.execute("""
    DO $$
    DECLARE
        columnas text;
    BEGIN
        SELECT string_agg(a.attname, ',' ORDER BY k.ord)
        INTO columnas
        FROM pg_constraint c
        JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
        WHERE c.conname = 'uq_checklist_control_fecha';

        IF columnas IS DISTINCT FROM 'control,fecha,discriminador' THEN
            IF columnas IS NOT NULL THEN
                ALTER TABLE registros_checklist
                    DROP CONSTRAINT uq_checklist_control_fecha;
            END IF;

            ALTER TABLE registros_checklist
                ADD CONSTRAINT uq_checklist_control_fecha
                UNIQUE (control, fecha, discriminador);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Volver a "una hoja por día" solo es posible si no quedan inspecciones
    # que compartan control y fecha; si las hay, la restricción vieja no se
    # puede recrear y se avisa en vez de fallar a medias.
    op.execute("""
    DO $$
    DECLARE
        duplicados integer;
    BEGIN
        SELECT count(*) INTO duplicados FROM (
            SELECT control, fecha FROM registros_checklist
            GROUP BY control, fecha HAVING count(*) > 1
        ) AS d;

        ALTER TABLE registros_checklist
            DROP CONSTRAINT IF EXISTS uq_checklist_control_fecha;

        IF duplicados = 0 THEN
            ALTER TABLE registros_checklist
                ADD CONSTRAINT uq_checklist_control_fecha UNIQUE (control, fecha);
        ELSE
            RAISE WARNING
                'Hay % día(s) con varias inspecciones: la restricción (control, fecha) no se recreó.',
                duplicados;
        END IF;
    END $$;
    """)

    op.execute("ALTER TABLE registros_checklist_puntos DROP COLUMN IF EXISTS medicion;")
    op.execute("ALTER TABLE registros_checklist DROP COLUMN IF EXISTS secciones;")
    op.execute("ALTER TABLE registros_checklist DROP COLUMN IF EXISTS encabezado;")
    op.execute("ALTER TABLE registros_checklist DROP COLUMN IF EXISTS discriminador;")
