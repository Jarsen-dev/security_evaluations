"""Intentos de respuesta y sus respuestas individuales."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Intento(Base):
    """Un llenado del cuestionario por parte de un empleado.

    Nombre, número de empleado y área son campos de identidad del
    respondiente, no preguntas: no se califican, siempre existen, y viven
    aquí para poder agrupar estadísticas por área con índices eficientes.
    """

    __tablename__ = "intentos"
    __table_args__ = (
        Index("ix_intentos_cuestionario_area", "cuestionario_id", "area"),
        Index("ix_intentos_cuestionario_finalizado", "cuestionario_id", "finalizado_at"),
        Index("ix_intentos_numero_empleado", "numero_empleado"),
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

    # --- Identidad del respondiente ---------------------------------------
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    numero_empleado: Mapped[str] = mapped_column(String(30), nullable=False)
    area: Mapped[str] = mapped_column(String(30), nullable=False)

    # --- Ciclo de vida -----------------------------------------------------
    iniciado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # NULL = intento en progreso o abandonado. Solo los finalizados cuentan
    # para estadísticas y para la regla de intento único.
    finalizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Resultado ---------------------------------------------------------
    total_preguntas: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    correctas: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    puntaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # --- Trazabilidad ------------------------------------------------------
    ip_origen: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    respuestas: Mapped[list["Respuesta"]] = relationship(
        back_populates="intento",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Intento {self.numero_empleado} ({self.area})>"


class Respuesta(Base):
    """Respuesta de un intento a una pregunta concreta."""

    __tablename__ = "respuestas"
    __table_args__ = (
        # Permite el upsert del autoguardado: ON CONFLICT (intento_id, pregunta_id).
        UniqueConstraint(
            "intento_id", "pregunta_id", name="uq_respuestas_intento_pregunta"
        ),
        # Sostiene la estadística de "preguntas más falladas".
        Index("ix_respuestas_pregunta_correcta", "pregunta_id", "es_correcta"),
        # PostgreSQL no indexa las llaves foráneas por su cuenta: sin este
        # índice, borrar una opción recorre la tabla completa para verificar
        # el ON DELETE SET NULL. Al editar un cuestionario se reemplazan
        # todas sus opciones, así que el costo se multiplica.
        Index("ix_respuestas_opcion_id", "opcion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    intento_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("intentos.id", ondelete="CASCADE"),
        nullable=False,
    )
    pregunta_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("preguntas.id", ondelete="CASCADE"),
        nullable=False,
    )
    opcion_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("opciones.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Siempre calculado en el servidor contra opciones.es_correcta:
    # el cliente nunca informa si acertó.
    es_correcta: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    respondido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    intento: Mapped["Intento"] = relationship(back_populates="respuestas")

    def __repr__(self) -> str:
        return f"<Respuesta intento={self.intento_id} pregunta={self.pregunta_id}>"
