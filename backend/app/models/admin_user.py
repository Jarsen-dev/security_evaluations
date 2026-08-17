"""Usuario administrador del sistema."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminUser(Base):
    """Administrador con acceso al panel.

    No hay registro público: estos usuarios se crean únicamente con el
    comando ``python -m app.cli create-admin``.
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Hash bcrypt. La contraseña en claro nunca se guarda ni se registra en logs.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AdminUser {self.username}>"
