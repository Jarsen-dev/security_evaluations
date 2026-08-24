"""Controles ESH: registros de presiones Rayser e inspecciones de SQP.

Cada tabla corresponde a una hoja del formato en papel que el departamento de
seguridad llenaba a mano. Se guarda el nombre del responsable además de su
``admin_id``: si algún día se borra un usuario, el histórico conserva quién
hizo cada registro en lugar de quedarse en NULL.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RegistroRayser(Base):
    """Lectura diaria de los cuatro manómetros del Rayser.

    Una fila por día, igual que el formato mensual en papel: por eso ``fecha``
    es única. La foto de evidencia vive aquí como ``bytea`` para que entre en
    el respaldo de la base junto con el registro que la explica.
    """

    __tablename__ = "registros_rayser"
    __table_args__ = (
        UniqueConstraint("fecha", name="uq_rayser_fecha"),
        Index("ix_registros_rayser_fecha", "fecha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)

    manometro_1: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    manometro_2: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    manometro_3: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    manometro_4: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)

    # Obligatorias cuando alguna lectura sale del rango normal; el servicio lo
    # exige, no la base: un registro dentro de rango puede llevar observaciones
    # opcionales.
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    foto_tipo: Mapped[str | None] = mapped_column(String(60), nullable=True)

    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def lecturas(self) -> list[Decimal]:
        """Las cuatro lecturas en orden, para clasificarlas de una pasada."""
        return [
            self.manometro_1,
            self.manometro_2,
            self.manometro_3,
            self.manometro_4,
        ]

    @property
    def tiene_foto(self) -> bool:
        """Si el registro trae evidencia fotográfica cargada."""
        return self.foto_tipo is not None

    def __repr__(self) -> str:
        return f"<RegistroRayser {self.fecha}>"


class InspeccionSqp(Base):
    """Inspección de sustancias químicas peligrosas de un área."""

    __tablename__ = "inspecciones_sqp"
    __table_args__ = (Index("ix_inspecciones_sqp_fecha", "fecha"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    area: Mapped[str] = mapped_column(String(30), nullable=False)

    # "Encargado y cargo" del encabezado del formato: es la persona a cargo del
    # área inspeccionada, distinta de quien realiza la inspección.
    encargado: Mapped[str] = mapped_column(String(150), nullable=False)
    cargo: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Listado libre de las SQP del área, una por renglón.
    sustancias: Mapped[str | None] = mapped_column(Text, nullable=True)

    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    respuestas: Mapped[list["RespuestaSqp"]] = relationship(
        back_populates="inspeccion",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RespuestaSqp.orden",
    )

    def __repr__(self) -> str:
        return f"<InspeccionSqp {self.fecha} {self.area}>"


class RespuestaSqp(Base):
    """Respuesta a un punto concreto de la inspección de SQP.

    El texto del punto no se copia aquí: vive en
    ``app/core/controles_catalogo.py`` y se resuelve por ``orden``. Guardar
    ``codigo`` sí sirve, porque es lo que el inspector busca en la hoja impresa.
    """

    __tablename__ = "inspecciones_sqp_respuestas"
    __table_args__ = (
        UniqueConstraint("inspeccion_id", "orden", name="uq_sqp_respuesta_orden"),
        Index("ix_sqp_respuestas_inspeccion", "inspeccion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    inspeccion_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("inspecciones_sqp.id", ondelete="CASCADE"),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    codigo: Mapped[str] = mapped_column(String(10), nullable=False)
    # 'si' | 'no' | 'na'
    valor: Mapped[str] = mapped_column(String(3), nullable=False)
    # Obligatoria cuando el valor es 'no'.
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    inspeccion: Mapped["InspeccionSqp"] = relationship(back_populates="respuestas")

    def __repr__(self) -> str:
        return f"<RespuestaSqp {self.codigo}={self.valor}>"
