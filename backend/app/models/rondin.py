"""Rondines de seguridad: puntos de control y sus escaneos."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PuntoRondin(Base):
    """Un punto de control de la planta, con su código QR.

    El ``token_publico`` es lo que viaja en el QR pegado en el punto, y es la
    única credencial del escaneo: quien lo tenga puede registrar una visita.
    Mismo trato que la liga de un cuestionario (ver SEGURIDAD.md).

    Retirar un punto se hace con ``activo = False``, no borrándolo: los
    escaneos históricos siguen apuntando aquí y el porcentaje de cumplimiento
    de los turnos pasados no debe cambiar.
    """

    __tablename__ = "puntos_rondin"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    #: Lo que el guardia ve impreso en la etiqueta.
    numero: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    ubicacion: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # 64 y no 32: `token_urlsafe(24)` da exactamente 32 caracteres, así que la
    # columna cabía justo y subir la entropía del token habría reventado el
    # INSERT. Ver la migración 0014.
    token_publico: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<PuntoRondin {self.numero} {self.nombre}>"


class EscaneoRondin(Base):
    """Una visita registrada a un punto de control.

    No identifica al guardia, igual que el panel de Streamlit que sustituye:
    un escaneo dice "el punto 12 fue visitado a las 14:32". Si algún día hace
    falta saber quién, se agrega la columna sin migrar lo capturado.

    La hora la pone el servidor y no el celular: el reloj de un teléfono
    cualquiera decidiría a qué rondín pertenece la visita.
    """

    __tablename__ = "escaneos_rondin"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    punto_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("puntos_rondin.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Desnormalizado a propósito, igual que `responsable` en los controles ESH
    # y `username` en la bitácora: borrar un punto pone el FK en NULL y el
    # histórico quedaría sin decir qué se visitó.
    punto_numero: Mapped[int] = mapped_column(Integer, nullable=False)

    escaneado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)

    def __repr__(self) -> str:
        return f"<EscaneoRondin punto={self.punto_numero} {self.escaneado_at}>"


class EnvioReporteRondin(Base):
    """Candado del reporte automático del cambio de turno.

    En producción uvicorn corre con cuatro workers, y la tarea programada vive
    en todos: sin este candado saldrían cuatro correos idénticos. El primer
    worker que gana el ``INSERT`` de la clave del turno manda el reporte; los
    demás reciben ``IntegrityError`` y se callan.

    Va en una tabla y no en memoria para que también sobreviva a un reinicio
    del contenedor dentro de la ventana de envío.
    """

    __tablename__ = "envios_reporte_rondin"

    #: ``AAAA-MM-DD:turno`` — un turno, un correo.
    clave: Mapped[str] = mapped_column(String(40), primary_key=True)
    enviado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<EnvioReporteRondin {self.clave}>"
