"""Recepciones por foto: documentos, partidas, plantillas de OCR y sesiones QR

Revision ID: 0011_recepciones
Revises: 0010_catalogo_codigo_unidad
Create Date: 2026-08-26

El almacén recibe la remisión del proveedor en papel. Esta migración crea lo
necesario para fotografiarla, extraer sus datos con OCR + IA, corregirlos y
dar entrada al inventario.

Cuatro decisiones que se notan en el SQL:

**Las imágenes van a la base, no al disco.** El backend no tiene ningún
volumen escribible (``docker-compose.yml`` no le monta ninguno y ``static/``
solo trae el logo), así que cualquier archivo escrito moriría con el
contenedor. Es la misma razón por la que las evidencias de los controles ESH
viven en ``controles_fotos.imagen``; aquí se repite el patrón, y de paso el
respaldo de la base se lleva las fotos consigo.

**La foto es una tabla aparte.** Una sola hoja física puede traer varias
remisiones impresas juntas, y todas comparten la misma evidencia. Con la
imagen dentro de ``recepciones`` habría que duplicar cientos de kilobytes por
documento.

**``descripcion`` y ``unidad_medida`` de cada partida son SNAPSHOT, no join.**
Si mañana cambia el catálogo, el documento histórico no cambia: dice lo que se
recibió el día que se recibió. Por eso ``insumo_id`` puede quedar en NULL sin
que el renglón pierda sentido.

**Las plantillas del clasificador también viven aquí.** El proyecto original
las guardaba en disco como ``ejemplo_N.jpg`` + ``.json`` + ``.txt``; el ``.txt``
era el texto OCR cacheado y había que regenerarlo de forma perezosa cuando
faltaba. Como columna de una fila, ese problema desaparece.

Todo con ``IF NOT EXISTS`` para poder re-ejecutarla sobre una base
parcialmente migrada. Una sentencia por ``execute``: asyncpg las prepara y
rechaza los cuerpos con varias.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_recepciones"
down_revision: str | None = "0010_catalogo_codigo_unidad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- La evidencia ------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS recepciones_fotos (
        id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        imagen    BYTEA        NOT NULL,
        tipo      VARCHAR(60)  NOT NULL,
        creado_at TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    # --- Los formatos de documento que el clasificador reconoce ------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS recepciones_plantillas (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        slug       VARCHAR(80)  NOT NULL UNIQUE,
        nombre     VARCHAR(150) NOT NULL,
        creado_por VARCHAR(50)  NOT NULL,
        creado_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    # `clase` separa los ejemplos que capturó una persona al registrar el
    # formato (curados, máximo 2, nunca se borran solos) de los que el sistema
    # aprendió al confirmar un guardado (auto, máximo 4, rotación FIFO).
    op.execute("""
    CREATE TABLE IF NOT EXISTS recepciones_plantilla_ejemplos (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        plantilla_id  UUID        NOT NULL
                      REFERENCES recepciones_plantillas(id) ON DELETE CASCADE,
        clase         VARCHAR(10) NOT NULL,
        indice        INTEGER     NOT NULL,
        imagen        BYTEA       NOT NULL,
        tipo          VARCHAR(60) NOT NULL,
        texto_ocr     TEXT        NOT NULL,
        json_esperado JSONB       NOT NULL,
        creado_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_ejemplo_clase'
        ) THEN
            ALTER TABLE recepciones_plantilla_ejemplos
                ADD CONSTRAINT ck_ejemplo_clase
                CHECK (clase IN ('curado', 'auto'));
        END IF;
    END $$;
    """)

    # Un solo ejemplo por (plantilla, clase, índice): es lo que sostiene la
    # rotación FIFO sin huecos duplicados.
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_ejemplo_plantilla_clase_indice
        ON recepciones_plantilla_ejemplos (plantilla_id, clase, indice);
    """)

    # PostgreSQL no indexa las llaves foráneas solo, y borrar una plantilla
    # con CASCADE recorrería la tabla entera sin esto.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_ejemplo_plantilla_id
        ON recepciones_plantilla_ejemplos (plantilla_id);
    """)

    # --- El documento ------------------------------------------------------
    # `creado_por` va desnormalizado por la misma razón que `username` en la
    # bitácora y `responsable` en los controles: borrar un usuario pondría el
    # FK en NULL y el histórico quedaría anónimo justo cuando más importa.
    op.execute("""
    CREATE TABLE IF NOT EXISTS recepciones (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        foto_id        UUID         REFERENCES recepciones_fotos(id) ON DELETE SET NULL,
        proveedor      VARCHAR(200),
        folio          VARCHAR(100),
        fecha          DATE,
        tipo_documento VARCHAR(80)  NOT NULL DEFAULT 'desconocido',
        ocr_ok         BOOLEAN      NOT NULL DEFAULT false,
        ocr_raw        JSONB,
        advertencias   JSONB,
        creado_por     VARCHAR(50)  NOT NULL,
        admin_id       UUID         REFERENCES admin_users(id) ON DELETE SET NULL,
        creado_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
    );
    """)

    # El listado ordena y filtra por fecha de captura en cada carga.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_recepciones_creado_at
        ON recepciones (creado_at DESC);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_recepciones_foto_id ON recepciones (foto_id);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_recepciones_admin_id ON recepciones (admin_id);
    """)

    # --- Las partidas ------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS recepciones_items (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        recepcion_id  UUID         NOT NULL
                      REFERENCES recepciones(id) ON DELETE CASCADE,
        insumo_id     UUID         REFERENCES insumos(id) ON DELETE SET NULL,
        codigo        VARCHAR(150) NOT NULL,
        descripcion   TEXT,
        unidad_medida VARCHAR(10)  NOT NULL,
        cantidad      INTEGER      NOT NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_recepcion_item_cantidad'
        ) THEN
            ALTER TABLE recepciones_items
                ADD CONSTRAINT ck_recepcion_item_cantidad CHECK (cantidad > 0);
        END IF;
    END $$;
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_recepciones_items_recepcion_id
        ON recepciones_items (recepcion_id);
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_recepciones_items_insumo_id
        ON recepciones_items (insumo_id);
    """)

    # --- El handoff celular <-> PC -----------------------------------------
    # Sin Redis: la sesión vive en Postgres y se limpia de forma perezosa al
    # crear una nueva. Lo que la protege son tres cosas A LA VEZ: el id no es
    # adivinable, expira en minutos y solo se puede usar una vez
    # (pendiente -> subida -> usada).
    op.execute("""
    CREATE TABLE IF NOT EXISTS recepciones_qr_sesiones (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        estado     VARCHAR(10)  NOT NULL DEFAULT 'pendiente',
        foto_id    UUID         REFERENCES recepciones_fotos(id) ON DELETE SET NULL,
        creado_por VARCHAR(50)  NOT NULL,
        creado_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
        expira_en  TIMESTAMPTZ  NOT NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_qr_sesion_estado'
        ) THEN
            ALTER TABLE recepciones_qr_sesiones
                ADD CONSTRAINT ck_qr_sesion_estado
                CHECK (estado IN ('pendiente', 'subida', 'usada'));
        END IF;
    END $$;
    """)

    # La limpieza perezosa barre por fecha de expiración.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_qr_sesiones_expira_en
        ON recepciones_qr_sesiones (expira_en);
    """)


def downgrade() -> None:
    # En orden inverso a las dependencias: primero lo que apunta a otras.
    op.execute("DROP TABLE IF EXISTS recepciones_qr_sesiones;")
    op.execute("DROP TABLE IF EXISTS recepciones_items;")
    op.execute("DROP TABLE IF EXISTS recepciones;")
    op.execute("DROP TABLE IF EXISTS recepciones_plantilla_ejemplos;")
    op.execute("DROP TABLE IF EXISTS recepciones_plantillas;")
    op.execute("DROP TABLE IF EXISTS recepciones_fotos;")
