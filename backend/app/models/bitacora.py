"""Bitácora de actividad del panel."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bitacora(Base):
    """Un renglón por acción que modifica datos, más los inicios de sesión.

    Solo se registra lo que cambia algo (POST/PUT/PATCH/DELETE) y el acceso
    al sistema. Las lecturas quedan fuera a propósito: son la mayoría del
    tráfico y su ruido escondería justo lo que se quiere auditar. El
    formulario público también queda fuera, porque ya deja su propio rastro
    en ``intentos`` y ``respuestas``.
    """

    __tablename__ = "bitacora"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Desnormalizado a propósito, igual que `responsable` en los controles
    # ESH: eliminar un usuario pone el FK en NULL y el histórico quedaría
    # anónimo justo cuando más interesa saber quién fue.
    username: Mapped[str] = mapped_column(String(50), nullable=False)

    accion: Mapped[str] = mapped_column(String(60), nullable=False)
    modulo: Mapped[str] = mapped_column(String(30), nullable=False)
    # Ya redactada en español y lista para mostrarse: es dato capturado, no
    # interfaz, así que el panel no la traduce (ver regla 6).
    descripcion: Mapped[str] = mapped_column(String(300), nullable=False)

    metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    ruta: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def __repr__(self) -> str:
        return f"<Bitacora {self.username} {self.accion}>"
