"""Usuarios con permisos y bitácora de actividad

Revision ID: 0004_usuarios_y_bitacora
Revises: 0003_controles_esh
Create Date: 2026-08-24

Hasta ahora ``admin_users`` guardaba solo usuario y contraseña, y cualquier
sesión válida tenía acceso total al panel. Con el sistema publicado en
internet y varias personas del departamento usándolo, hacen falta tres cosas
que esta migración habilita:

* **Identidad y estado** — ``nombre``, ``email``, ``activo``. Desactivar
  conserva el histórico de quién hizo qué, cosa que eliminar no hace.
* **Permisos** — ``es_superadmin`` y ``permisos`` (JSONB por módulo). La
  presencia de la clave del módulo es el acceso; ``editar`` cubre modificar
  y eliminar.
* **``bitacora``** — un renglón por acción que cambia datos, más los inicios
  de sesión, para poder auditarlos desde el panel.

Dos decisiones que se notan en el SQL:

``email`` queda NULLABLE con índice único PARCIAL. El administrador que ya
existe no tiene correo y la migración no debe inventarle uno; un índice único
normal sobre una columna con varios NULL sí funciona en PostgreSQL, pero el
parcial deja explícito que "sin correo" es un estado válido. El formulario de
alta sí lo exige.

El superadministrador se marca por ANTIGÜEDAD, no por nombre: buscar el
usuario llamado ``admin`` fallaría en silencio si alguien lo renombró, y el
sistema quedaría sin quien administre.

Todo va con ``IF NOT EXISTS`` y guardas condicionales para poder
re-ejecutarla sobre una base parcialmente migrada.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_usuarios_y_bitacora"
down_revision: str | None = "0003_controles_esh"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Permisos que reciben los usuarios que ya existían: acceso total. La
# migración no debe quitarle capacidades a nadie; el superadministrador
# recorta desde el panel a partir de aquí.
PERMISOS_COMPLETOS = (
    '{"cuestionarios": {"editar": true}, '
    '"controles": {"editar": true}, '
    '"inventario": {"editar": true}}'
)


def upgrade() -> None:
    # --- Columnas nuevas de admin_users -----------------------------------
    # `nombre` entra nullable para poder rellenarlo antes de exigirlo.
    op.execute("""
    ALTER TABLE admin_users
        ADD COLUMN IF NOT EXISTS nombre         VARCHAR(120),
        ADD COLUMN IF NOT EXISTS email          VARCHAR(255),
        ADD COLUMN IF NOT EXISTS activo         BOOLEAN     NOT NULL DEFAULT true,
        ADD COLUMN IF NOT EXISTS es_superadmin  BOOLEAN     NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS permisos       JSONB       NOT NULL
                                               DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS actualizado_at TIMESTAMPTZ;
    """)

    op.execute("""
    UPDATE admin_users SET nombre = username WHERE nombre IS NULL;
    """)

    op.execute("""
    ALTER TABLE admin_users ALTER COLUMN nombre SET NOT NULL;
    """)

    # Único parcial: varias cuentas sin correo pueden convivir.
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_users_email
        ON admin_users (email) WHERE email IS NOT NULL;
    """)

    # --- Semilla del superadministrador ------------------------------------
    # El más antiguo, y solo si todavía no hay ninguno: así re-ejecutar la
    # migración no revive a alguien a quien le quitaron el rol después.
    op.execute("""
    UPDATE admin_users SET es_superadmin = true
     WHERE id = (SELECT id FROM admin_users ORDER BY created_at LIMIT 1)
       AND NOT EXISTS (SELECT 1 FROM admin_users WHERE es_superadmin);
    """)

    op.execute(f"""
    UPDATE admin_users SET permisos = '{PERMISOS_COMPLETOS}'::jsonb
     WHERE permisos = '{{}}'::jsonb;
    """)

    # --- Bitácora ----------------------------------------------------------
    op.execute("""
    CREATE TABLE IF NOT EXISTS bitacora (
        id          BIGSERIAL PRIMARY KEY,
        creado_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
        usuario_id  UUID REFERENCES admin_users (id) ON DELETE SET NULL,
        username    VARCHAR(50)  NOT NULL,
        accion      VARCHAR(60)  NOT NULL,
        modulo      VARCHAR(30)  NOT NULL,
        descripcion VARCHAR(300) NOT NULL,
        metodo      VARCHAR(10)  NOT NULL,
        ruta        VARCHAR(255) NOT NULL,
        estado      SMALLINT     NOT NULL,
        ip          VARCHAR(45)
    );
    """)

    # La pantalla lista siempre por fecha descendente y filtra por usuario.
    # PostgreSQL no indexa las llaves foráneas por su cuenta, y sin el
    # segundo índice borrar un usuario recorrería la bitácora completa para
    # aplicar el ON DELETE SET NULL.
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_bitacora_creado_at
        ON bitacora (creado_at DESC);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_bitacora_usuario_id
        ON bitacora (usuario_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bitacora;")

    op.execute("DROP INDEX IF EXISTS uq_admin_users_email;")
    op.execute("""
    ALTER TABLE admin_users
        DROP COLUMN IF EXISTS actualizado_at,
        DROP COLUMN IF EXISTS permisos,
        DROP COLUMN IF EXISTS es_superadmin,
        DROP COLUMN IF EXISTS activo,
        DROP COLUMN IF EXISTS email,
        DROP COLUMN IF EXISTS nombre;
    """)
