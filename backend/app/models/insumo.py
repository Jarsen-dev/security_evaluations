"""Catálogo de insumos de seguridad."""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: Estados del semáforo de existencias.
ESTADO_BAJO: Final[str] = "bajo"
ESTADO_NORMAL: Final[str] = "normal"
ESTADO_EXCEDIDO: Final[str] = "excedido"


def estado_insumo(cantidad: int, minimo: int, maximo: int) -> str:
    """Clasifica la existencia contra su rango.

    Se calcula en el servidor, igual que la semaforización de los manómetros
    de Rayser: el frontend repite la regla solo para pintar el formulario
    mientras se teclea, pero lo que se muestra en la tabla y lo que decide el
    filtro sale de aquí.
    """
    if cantidad < minimo:
        return ESTADO_BAJO
    if cantidad > maximo:
        return ESTADO_EXCEDIDO
    return ESTADO_NORMAL


class Insumo(Base):
    """Un renglón del catálogo de insumos de seguridad.

    Es un catálogo, no un almacén: ``cantidad`` se captura a mano tras el
    conteo. Más adelante se construirá encima un sistema de recepciones y
    salidas; cuando exista, la tabla de movimientos referenciará este ``id``
    y el servicio pasará a recalcular ``cantidad``. Por eso la existencia es
    una columna propia y no un valor derivado: ese día no habrá que migrar
    las filas ya capturadas.

    Quién dio de alta o modificó cada insumo no se guarda aquí: la bitácora
    ya lo registra con nombre, fecha y detalle.
    """

    __tablename__ = "insumos"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Único sin distinguir mayúsculas (índice sobre lower(nombre) en la
    # migración): si no, "Guantes de nitrilo" y "guantes de nitrilo" serían
    # dos insumos y la importación los duplicaría.
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    proveedor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(String(150), nullable=True)

    cantidad: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    minimo: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    maximo: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def estado(self) -> str:
        """Semáforo de la existencia contra su rango."""
        return estado_insumo(self.cantidad, self.minimo, self.maximo)

    def __repr__(self) -> str:
        return f"<Insumo {self.nombre}>"
