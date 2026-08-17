"""Cuestionario, preguntas y opciones."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Cuestionario(Base):
    """Evaluación que responde el personal por medio de una liga pública."""

    __tablename__ = "cuestionarios"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Token aleatorio de secrets.token_urlsafe(24): es la única credencial
    # de la liga pública, por eso nunca se deriva del id ni es secuencial.
    token_publico: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # Si es false, la liga pública deja de aceptar respuestas.
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    permitir_multiples_intentos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    preguntas: Mapped[list["Pregunta"]] = relationship(
        back_populates="cuestionario",
        cascade="all, delete-orphan",
        order_by="Pregunta.orden",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Cuestionario {self.nombre!r}>"


class Pregunta(Base):
    """Pregunta de opción múltiple perteneciente a un cuestionario."""

    __tablename__ = "preguntas"
    __table_args__ = (
        # Deferrable: al reordenar en lote, los órdenes intermedios se repiten
        # y la restricción solo debe evaluarse al final de la transacción.
        UniqueConstraint(
            "cuestionario_id",
            "orden",
            name="uq_preguntas_cuestionario_orden",
            deferrable=True,
            initially="DEFERRED",
        ),
        Index("ix_preguntas_cuestionario_id", "cuestionario_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    cuestionario_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cuestionarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    puntos: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    cuestionario: Mapped["Cuestionario"] = relationship(back_populates="preguntas")
    opciones: Mapped[list["Opcion"]] = relationship(
        back_populates="pregunta",
        cascade="all, delete-orphan",
        order_by="Opcion.orden",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Pregunta {self.orden}: {self.texto[:40]!r}>"


class Opcion(Base):
    """Opción de respuesta.

    Regla de negocio (validada en la capa de servicio): cada pregunta debe
    tener mínimo 2 opciones y exactamente una con ``es_correcta = true``.
    """

    __tablename__ = "opciones"
    __table_args__ = (Index("ix_opciones_pregunta_id", "pregunta_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pregunta_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("preguntas.id", ondelete="CASCADE"),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    # CRÍTICO: este campo jamás debe serializarse en un endpoint público.
    # Los schemas públicos usan OpcionPublica, que lo omite.
    es_correcta: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    pregunta: Mapped["Pregunta"] = relationship(back_populates="opciones")

    def __repr__(self) -> str:
        return f"<Opcion {self.texto[:30]!r}>"
