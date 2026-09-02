"""Recepciones de mercancía por foto de la remisión.

Las imágenes viven en la base y no en el disco: el backend no tiene ningún
volumen escribible, así que un archivo escrito moriría con el contenedor. Es
la misma decisión que ya tomaron las evidencias de los controles ESH.

Quién capturó cada documento se guarda **desnormalizado** en ``creado_por``,
además del FK: borrar un usuario pone el FK en NULL y el histórico quedaría
anónimo justo cuando más importa.
"""

import uuid
from datetime import date, datetime
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

#: Estados de una sesión de captura por QR. El orden es el del ciclo de vida.
ESTADO_PENDIENTE: Final[str] = "pendiente"
ESTADO_SUBIDA: Final[str] = "subida"
ESTADO_USADA: Final[str] = "usada"

#: Clases de ejemplo de una plantilla.
CLASE_CURADO: Final[str] = "curado"
CLASE_AUTO: Final[str] = "auto"


class FotoRecepcion(Base):
    """La foto de la hoja física, guardada siempre y antes de leerla.

    Es una tabla aparte porque una sola hoja puede traer varias remisiones
    impresas juntas: todas comparten la misma evidencia en vez de duplicar
    cientos de kilobytes por documento.
    """

    __tablename__ = "recepciones_fotos"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    imagen: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PlantillaRecepcion(Base):
    """Un formato de documento que el clasificador aprendió a reconocer."""

    __tablename__ = "recepciones_plantillas"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    creado_por: Mapped[str] = mapped_column(String(50), nullable=False)
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ejemplos: Mapped[list["EjemploPlantillaRecepcion"]] = relationship(
        back_populates="plantilla",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EjemploPlantillaRecepcion(Base):
    """Un ejemplo etiquetado de un formato.

    ``texto_ocr`` es el texto ya leído de la imagen. Guardarlo evita volver a
    pasar Tesseract por cada ejemplo en cada clasificación, que es lo que hace
    viable comparar contra todo el corpus en cada foto nueva.

    ``clase`` separa dos poblaciones con reglas distintas: los **curados** los
    captura una persona al registrar el formato y no se borran nunca solos;
    los **auto** los aprende el sistema al confirmar un guardado y rotan FIFO.
    """

    __tablename__ = "recepciones_plantilla_ejemplos"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    plantilla_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recepciones_plantillas.id", ondelete="CASCADE"),
        nullable=False,
    )
    clase: Mapped[str] = mapped_column(String(10), nullable=False)
    indice: Mapped[int] = mapped_column(Integer, nullable=False)
    imagen: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    texto_ocr: Mapped[str] = mapped_column(Text, nullable=False)
    json_esperado: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plantilla: Mapped[PlantillaRecepcion] = relationship(back_populates="ejemplos")

    @property
    def es_curado(self) -> bool:
        return self.clase == CLASE_CURADO


class Recepcion(Base):
    """Un documento de recepción capturado.

    ``ocr_raw`` guarda la extracción **original, sin las correcciones del
    usuario**: permite auditar qué leyó la IA contra qué corrigió la persona.
    ``advertencias`` guarda qué campos venían en null al momento de extraer.
    """

    __tablename__ = "recepciones"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    foto_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recepciones_fotos.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lo que dice el papel, no lo que dice el sistema: `proveedor` es texto
    # libre y no una llave foránea a propósito. El flujo no sabe nada de
    # órdenes de compra.
    proveedor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    folio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fecha: Mapped[date | None] = mapped_column(Date, nullable=True)

    tipo_documento: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=text("'desconocido'")
    )
    ocr_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    ocr_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    advertencias: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    creado_por: Mapped[str] = mapped_column(String(50), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list["ItemRecepcion"]] = relationship(
        back_populates="recepcion",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ItemRecepcion(Base):
    """Una partida del documento.

    ``descripcion``, ``unidad_medida`` y ``piezas_por_empaque`` son **snapshot
    del catálogo al momento de guardar**, no un join: si mañana cambia el
    catálogo, el documento histórico sigue diciendo lo que se recibió el día
    que se recibió. Por eso ``insumo_id`` puede quedar en NULL sin que el
    renglón pierda sentido.

    ``cantidad`` son **cajas o paquetes**, que es lo que el operador lee del
    papel y teclea. Lo que entró al inventario son
    ``cantidad * piezas_por_empaque`` piezas.
    """

    __tablename__ = "recepciones_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    recepcion_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recepciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    insumo_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("insumos.id", ondelete="SET NULL"),
        nullable=True,
    )
    codigo: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    unidad_medida: Mapped[str] = mapped_column(String(10), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    piezas_por_empaque: Mapped[int] = mapped_column(Integer, nullable=False)

    recepcion: Mapped[Recepcion] = relationship(back_populates="items")

    @property
    def piezas(self) -> int:
        """Lo que esta partida sumó al inventario."""
        return self.cantidad * self.piezas_por_empaque


class SesionQrRecepcion(Base):
    """Handoff entre el celular y la PC, sin Redis.

    Lo que la protege son tres cosas **a la vez**: el id no es adivinable,
    expira en minutos y solo se puede usar una vez. Ninguna de las tres sobra:
    los dos endpoints que la consultan son públicos.
    """

    __tablename__ = "recepciones_qr_sesiones"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    estado: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'pendiente'")
    )
    foto_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recepciones_fotos.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_por: Mapped[str] = mapped_column(String(50), nullable=False)
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expira_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
