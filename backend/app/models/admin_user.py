"""Usuario administrador del sistema."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminUser(Base):
    """Usuario con acceso al panel.

    No hay registro público: los usuarios los da de alta el
    superadministrador desde la pestaña de Administración, o se crean con
    ``python -m app.cli create-admin`` (la vía de rescate cuando todavía no
    existe ninguno).
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Nullable a propósito: los usuarios creados antes de que existiera la
    # gestión desde el panel no tienen correo, y la migración no debe
    # inventarles uno. El alta desde la interfaz sí lo exige.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Hash bcrypt. La contraseña en claro nunca se guarda ni se registra en logs.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Desactivar deja la cuenta en su lugar pero corta el acceso: se valida en
    # `obtener_admin_actual`, así que también invalida las sesiones abiertas.
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # Único que ve la pestaña de Administración y puede gestionar usuarios.
    es_superadmin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Permisos por módulo. La PRESENCIA de la clave es el acceso; `editar`
    # cubre modificar y eliminar:
    #     {"cuestionarios": {"editar": true}, "controles": {"editar": false}}
    # Un módulo ausente significa que el usuario no ve esa pestaña.
    permisos: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def puede(self, modulo: str, *, editar: bool = False) -> bool:
        """Indica si el usuario tiene permiso sobre un módulo.

        Única fuente de verdad de la decisión: las dependencias de la API y
        el panel se apoyan en esta regla, no la reimplementan.

        El superadministrador puede todo; para el resto, tener la clave del
        módulo basta para ver y crear, y ``editar`` se necesita para
        modificar y para eliminar.
        """
        if self.es_superadmin:
            return True

        entrada = (self.permisos or {}).get(modulo)
        if not isinstance(entrada, dict):
            return False

        return bool(entrada.get("editar")) if editar else True

    def __repr__(self) -> str:
        return f"<AdminUser {self.username}>"
