"""La captura de rondines pasa a AppSheet

Revision ID: 0019_rondines_appsheet
Revises: 0018_sellar_formato
Create Date: 2026-09-03

Los guardias ya registran su recorrido en una app de AppSheet con 44 puntos
fijos en planta, y esa app queda como fuente de verdad de la captura. Este
sistema deja de capturar y pasa a consumir: un Bot de AppSheet empuja cada
escaneo al webhook, y dos comandos de CLI cargan el catálogo y el histórico.

Tres grupos de cambios:

1. `escaneos_rondin` gana la procedencia. `origen_id` guarda el `ID_Registro`
   de AppSheet (`UNIQUEID()`) con un UNIQUE, que es lo único que hace inocuos
   los reintentos del Bot. `recibido_at` guarda el reloj del servidor, porque
   `escaneado_at` ahora la dicta el cuerpo de la petición: AppSheet captura sin
   señal y sincroniza horas después, así que sin las dos no hay forma de
   distinguir una sincronización tardía de una hora fabricada.

2. Los campos que AppSheet sí trae y aquí no existían: GPS, comentario, correo
   del guardia y la ruta de la foto en su almacenamiento. El GPS se guarda como
   evidencia y NO para verificar presencia: medido contra las coordenadas de
   referencia, la mediana del error son 94 m y los puntos de la planta están
   más juntos que eso.

3. `puntos_rondin` pierde `token_publico`. Ya no hay QR propio que autenticar
   —las etiquetas de la pared son de AppSheet— y dejar una credencial muerta
   `NOT NULL UNIQUE` obligaría al importador a acuñar tokens que nada consume.
   Gana `ref_lat`/`ref_lon`, que vienen de `Ubicación_Referencia`.

Idempotente: cada paso comprueba el catálogo del sistema antes de actuar, así
que re-ejecutarla sobre una base a medio migrar no falla.

El `downgrade()` recrea `token_publico` **nullable y sin UNIQUE**: es una bajada
con pérdida y no puede ser otra cosa, porque los tokens no se pueden
reconstruir. Tampoco hacen falta: sin la página `/p/[token]` no los lee nadie.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_rondines_appsheet"
down_revision: str | None = "0018_sellar_formato"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Una sentencia por llamada: asyncpg las prepara y PostgreSQL rechaza varias
#: en un mismo `execute`. Lo único que puede llevar más de una es un `DO $$`.
COLUMNAS_ESCANEO = (
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS "
    "origen VARCHAR(20) NOT NULL DEFAULT 'appsheet'",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS origen_id VARCHAR(64)",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS "
    "recibido_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS gps_lat NUMERIC(9,6)",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS gps_lon NUMERIC(9,6)",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS comentario VARCHAR(300)",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS email_guardia VARCHAR(200)",
    "ALTER TABLE escaneos_rondin ADD COLUMN IF NOT EXISTS foto_ruta VARCHAR(200)",
)

COLUMNAS_PUNTO = (
    "ALTER TABLE puntos_rondin ADD COLUMN IF NOT EXISTS ref_lat NUMERIC(9,6)",
    "ALTER TABLE puntos_rondin ADD COLUMN IF NOT EXISTS ref_lon NUMERIC(9,6)",
)


def upgrade() -> None:
    for sentencia in COLUMNAS_ESCANEO + COLUMNAS_PUNTO:
        op.execute(sentencia)

    # UNIQUE pelado y no índice parcial: `ON CONFLICT (origen_id) DO NOTHING`
    # infiere el índice, y con un parcial habría que repetir el WHERE en la
    # cláusula de inferencia o el upsert falla en ejecución. Un UNIQUE de
    # PostgreSQL ya admite tantos NULL como quieras, así que una corrección
    # manual sin `origen_id` no choca contra nada.
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_escaneos_rondin_origen_id'
        ) THEN
            ALTER TABLE escaneos_rondin
                ADD CONSTRAINT uq_escaneos_rondin_origen_id UNIQUE (origen_id);
        END IF;
    END $$;
    """)

    # `token_publico` se va en un solo bloque para que soltar el UNIQUE y la
    # columna sean la misma unidad: dejar el constraint sin la columna es
    # imposible, pero al revés sí, y un fallo a medias dejaría la tabla rara.
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'puntos_rondin' AND column_name = 'token_publico'
        ) THEN
            ALTER TABLE puntos_rondin DROP CONSTRAINT IF EXISTS uq_puntos_rondin_token;
            ALTER TABLE puntos_rondin DROP COLUMN token_publico;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # Nullable y sin UNIQUE a propósito: los tokens no se pueden reconstruir y
    # ya no los lee nadie. Recrear la columna NOT NULL fallaría con filas.
    op.execute("""
    ALTER TABLE puntos_rondin ADD COLUMN IF NOT EXISTS token_publico VARCHAR(64)
    """)

    op.execute("""
    ALTER TABLE escaneos_rondin DROP CONSTRAINT IF EXISTS uq_escaneos_rondin_origen_id
    """)

    for columna in (
        "origen",
        "origen_id",
        "recibido_at",
        "gps_lat",
        "gps_lon",
        "comentario",
        "email_guardia",
        "foto_ruta",
    ):
        op.execute(f"ALTER TABLE escaneos_rondin DROP COLUMN IF EXISTS {columna}")

    for columna in ("ref_lat", "ref_lon"):
        op.execute(f"ALTER TABLE puntos_rondin DROP COLUMN IF EXISTS {columna}")
