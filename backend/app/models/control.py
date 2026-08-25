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
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RegistroRayser(Base):
    """Lectura diaria de los cuatro manómetros del Rayser.

    Una fila por día, igual que el formato mensual en papel: por eso ``fecha``
    es única. Las fotos de evidencia viven en ``controles_fotos``, la misma
    tabla que usan los demás controles.
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

    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    fotos: Mapped[list["FotoControl"]] = relationship(
        back_populates="rayser",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FotoControl.orden",
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


class RegistroChecklist(Base):
    """Una hoja de lista de verificación llenada.

    Todas las hojas de esta forma comparten tabla y se distinguen por
    ``control``. Sus puntos viven en ``app/core/controles_catalogo.py``, no en
    la base: cambiar la redacción de un punto no debe obligar a tocar el
    histórico.

    Hay dos formas de control y las dos caben aquí:

    * Las de **rejilla mensual** (almacén de RP's, recorridos, muro) llevan una
      hoja por día: su ``discriminador`` queda vacío.
    * Las de **formato por inspección** (silos, tableros) llevan encabezado y
      admiten varias el mismo día; su ``discriminador`` lo arma el servicio con
      los campos que las identifican (el turno, o el tablero y el turno).
    """

    __tablename__ = "registros_checklist"
    __table_args__ = (
        # Una sola restricción cubre los dos casos: con el discriminador vacío
        # equivale a "una hoja por día y control".
        UniqueConstraint(
            "control", "fecha", "discriminador", name="uq_checklist_control_fecha"
        ),
        Index("ix_registros_checklist_control_fecha", "control", "fecha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    control: Mapped[str] = mapped_column(String(30), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    # Lo que distingue dos inspecciones del mismo día ("noche", "T-12|noche").
    # Vacío en los controles que solo admiten una por día.
    discriminador: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=text("''")
    )

    # Campos del encabezado del formato y de sus bloques extra. Son metadatos
    # del documento —se muestran y se imprimen, nunca se agregan—, y su forma
    # la define y la valida el catálogo, así que no ganan nada normalizados.
    encabezado: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    secciones: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    puntos: Mapped[list["PuntoChecklist"]] = relationship(
        back_populates="registro",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PuntoChecklist.orden",
    )

    def __repr__(self) -> str:
        return f"<RegistroChecklist {self.control} {self.fecha}>"


class PuntoChecklist(Base):
    """Cómo salió un punto concreto del recorrido de ese día."""

    __tablename__ = "registros_checklist_puntos"
    __table_args__ = (
        UniqueConstraint("registro_id", "orden", name="uq_checklist_punto_orden"),
        Index("ix_checklist_puntos_registro", "registro_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    registro_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("registros_checklist.id", ondelete="CASCADE"),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    clave: Mapped[str] = mapped_column(String(40), nullable=False)
    # 'ok' | 'no_ok' (los formatos por inspección los rotulan SÍ / NO).
    valor: Mapped[str] = mapped_column(String(6), nullable=False)
    # Obligatorias cuando el valor es 'no_ok'.
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Solo en los puntos que piden una lectura ("62.5"); el catálogo dice
    # cuáles y con qué unidad.
    medicion: Mapped[str | None] = mapped_column(String(40), nullable=True)

    registro: Mapped["RegistroChecklist"] = relationship(back_populates="puntos")
    fotos: Mapped[list["FotoControl"]] = relationship(
        back_populates="punto",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FotoControl.orden",
    )

    def __repr__(self) -> str:
        return f"<PuntoChecklist {self.clave}={self.valor}>"


class PlaticaEsh(Base):
    """Una plática diaria de seguridad impartida en una o varias áreas.

    Sin restricción de unicidad por fecha: en un día puede haber más de una
    plática, cada una con su tema.
    """

    __tablename__ = "platicas_esh"
    __table_args__ = (Index("ix_platicas_esh_fecha", "fecha"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tema: Mapped[str] = mapped_column(String(300), nullable=False)

    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    areas: Mapped[list["AreaPlatica"]] = relationship(
        back_populates="platica",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fotos: Mapped[list["FotoControl"]] = relationship(
        back_populates="platica",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FotoControl.orden",
    )

    def __repr__(self) -> str:
        return f"<PlaticaEsh {self.fecha} {self.tema[:30]}>"


class AreaPlatica(Base):
    """Área donde se impartió una plática.

    Una fila por área en lugar de seis columnas booleanas: así se puede contar
    con GROUP BY cuántas pláticas recibió cada área.
    """

    __tablename__ = "platicas_esh_areas"
    __table_args__ = (
        UniqueConstraint("platica_id", "clave", name="uq_platica_area"),
        Index("ix_platicas_areas_platica", "platica_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    platica_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("platicas_esh.id", ondelete="CASCADE"),
        nullable=False,
    )
    clave: Mapped[str] = mapped_column(String(20), nullable=False)

    platica: Mapped["PlaticaEsh"] = relationship(back_populates="areas")

    def __repr__(self) -> str:
        return f"<AreaPlatica {self.clave}>"


class FotoControl(Base):
    """Evidencia fotográfica de cualquier control.

    Una sola tabla para las tres procedencias posibles, con un ``CHECK`` que
    obliga a que exactamente una llave foránea venga llena. Así hay un único
    endpoint que sirve las imágenes y una sola forma de guardarlas.

    Las imágenes viven en la base para que entren en el respaldo junto con el
    registro que explican; el servicio nunca las trae en los listados.
    """

    __tablename__ = "controles_fotos"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(punto_id, platica_id, rayser_id) = 1",
            name="ck_foto_un_solo_dueno",
        ),
        Index("ix_controles_fotos_punto", "punto_id"),
        Index("ix_controles_fotos_platica", "platica_id"),
        Index("ix_controles_fotos_rayser", "rayser_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    punto_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("registros_checklist_puntos.id", ondelete="CASCADE"),
        nullable=True,
    )
    platica_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("platicas_esh.id", ondelete="CASCADE"),
        nullable=True,
    )
    rayser_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("registros_rayser.id", ondelete="CASCADE"),
        nullable=True,
    )

    imagen: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    punto: Mapped["PuntoChecklist | None"] = relationship(back_populates="fotos")
    platica: Mapped["PlaticaEsh | None"] = relationship(back_populates="fotos")
    rayser: Mapped["RegistroRayser | None"] = relationship(back_populates="fotos")

    def __repr__(self) -> str:
        return f"<FotoControl {self.id}>"
