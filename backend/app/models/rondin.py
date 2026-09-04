"""Rondines de seguridad: puntos de control y sus escaneos."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PuntoRondin(Base):
    """Un punto de control de la planta.

    El catálogo lo manda AppSheet, que es donde los guardias capturan: esta
    tabla es una copia que se refresca con ``python -m app.cli importar-puntos``.
    El ``numero`` es el ``ID_QR`` de allá, así que es la llave con la que se
    emparejan los escaneos que llegan por el webhook.

    Ya no hay ``token_publico``: el QR pegado en la pared es de AppSheet y la
    credencial de la ingesta es el secreto del webhook (ver SEGURIDAD.md).

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

    #: Coordenadas del punto según AppSheet (`Ubicación_Referencia`). Se
    #: guardan por completitud del catálogo; NO sirven para verificar que el
    #: guardia estuviera ahí: el GPS del celular trae 94 m de error mediano y
    #: los puntos de la planta están más juntos que eso (ver CLAUDE.md).
    ref_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    ref_lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

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

    No identifica al guardia: ``email_guardia`` llega de AppSheet, pero en la
    práctica es una cuenta compartida de turno (medido: 49,441 de 49,488
    escaneos con el mismo correo). Se guarda por si algún día cada guardia
    tiene la suya, no para responsabilizar a nadie.

    ``escaneado_at`` **la trae AppSheet, no el servidor**, al revés que antes:
    la app captura sin señal y sincroniza horas después, así que sellar al
    recibir mandaría media ronda al rondín equivocado. ``recibido_at`` es el
    reloj del servidor, y la diferencia entre las dos es lo único que
    distingue "llegó tarde por sincronización" de una hora fabricada.
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

    #: Procedencia de la fila: el webhook o el importador del histórico.
    origen: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'appsheet'")
    )
    #: `ID_Registro` de AppSheet (`UNIQUEID()`, 8 hex). Es la llave de
    #: idempotencia: el UNIQUE es lo único que hace inocuos los reintentos del
    #: Bot, que reintenta de verdad. NULL en una corrección hecha a mano.
    origen_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    #: Reloj del servidor. Ver el docstring de la clase.
    recibido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    #: `Ubicación_GPS` de AppSheet (`=HERE()`). Evidencia, no verificación.
    gps_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    gps_lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    comentario: Mapped[str | None] = mapped_column(String(300), nullable=True)
    email_guardia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Ruta del archivo DENTRO del almacenamiento de AppSheet. Es una
    #: referencia, no una copia: traerlo exigiría su API y aquí no se usa.
    foto_ruta: Mapped[str | None] = mapped_column(String(200), nullable=True)

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
