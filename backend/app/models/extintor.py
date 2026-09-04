"""Extintores de la planta y su revisión diaria.

Es el único control con una **ficha por aparato**: 160 extintores, cada uno con
su vencimiento, su etiqueta QR y una revisión de doce puntos al día. Por eso no
comparte `registros_checklist` con los controles de lista de verificación —
aquellos son una hoja de N puntos al día para toda la planta, y aquí son N
aparatos identificados por doce puntos cada uno—.
"""

import uuid
from datetime import date, datetime
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
    not_,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import ColumnElement

from app.core.fechas import sumar_meses
from app.db.base import Base

#: Estados del vencimiento, del más urgente al más tranquilo.
ESTADO_VENCIDO: Final[str] = "vencido"
ESTADO_CRITICO: Final[str] = "critico"
ESTADO_POR_VENCER: Final[str] = "por_vencer"
ESTADO_VIGENTE: Final[str] = "vigente"

#: Los cuatro, para el selector del filtro y para validarlo.
ESTADOS_EXTINTOR: Final[tuple[str, ...]] = (
    ESTADO_VENCIDO,
    ESTADO_CRITICO,
    ESTADO_POR_VENCER,
    ESTADO_VIGENTE,
)
ESTADOS_FILTRABLES: Final[frozenset[str]] = frozenset(ESTADOS_EXTINTOR)

#: Meses de antelación de cada aviso. Rojo a uno, amarillo a dos.
MESES_CRITICO: Final[int] = 1
MESES_POR_VENCER: Final[int] = 2


def estado_vencimiento(vencimiento: date, hoy: date) -> str:
    """Semáforo de la recarga de un extintor.

    Se calcula en el servidor, igual que el de las existencias del catálogo: el
    panel lo pinta, no lo deduce.

    Los cortes se cuentan en **meses de calendario** y no en días: "un mes
    antes" del 31 de marzo es el 28 de febrero, no el 1 de marzo. Ver
    `core/fechas.sumar_meses`.

    Un extintor cuya fecha ya pasó **no se corrige solo**: el dato capturado se
    respeta y el estado se deduce de la fecha, igual que hace Estudios.

    El orden de las ramas es el contrato: `expresiones_estado()` lo repite en
    SQL y `tests/test_extintores.py` compara las dos, rama por rama.
    """
    if vencimiento < hoy:
        return ESTADO_VENCIDO
    if vencimiento <= sumar_meses(hoy, MESES_CRITICO):
        return ESTADO_CRITICO
    if vencimiento <= sumar_meses(hoy, MESES_POR_VENCER):
        return ESTADO_POR_VENCER
    return ESTADO_VIGENTE


class Extintor(Base):
    """La ficha de un extintor.

    `folio` es lo que lo identifica en la nave: la etiqueta impresa lleva ese
    número, y sin él dos aparatos del mismo modelo en la misma área serían
    indistinguibles al pegarles el QR o al reportar un hallazgo.
    """

    __tablename__ = "extintores"
    __table_args__ = (
        UniqueConstraint("folio", name="uq_extintores_folio"),
        CheckConstraint("length(btrim(folio)) > 0", name="ck_extintores_folio"),
        # Se filtra y se ordena por el vencimiento en cada carga de la tabla y
        # en cada consulta de la campana.
        Index("ix_extintores_vencimiento", "vencimiento"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    folio: Mapped[str] = mapped_column(String(20), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    capacidad: Mapped[str] = mapped_column(String(50), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(150), nullable=False)
    vencimiento: Mapped[date] = mapped_column(Date, nullable=False)

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def estado(self, hoy: date) -> str:
        """Semáforo del vencimiento.

        Es un método y no una `@property` como en `Insumo`: aquí el resultado
        depende del día, y una propiedad sin argumento tendría que llamar a
        `date.today()` por su cuenta —que en este contenedor es UTC— y daría un
        color distinto al del filtro, que sí recibe la fecha de la planta.
        """
        return estado_vencimiento(self.vencimiento, hoy)

    def __repr__(self) -> str:
        return f"<Extintor {self.folio}>"


class RevisionExtintor(Base):
    """La revisión diaria de un extintor.

    `modelo`, `tipo` y `ubicacion` son **snapshot**: eliminar la ficha del
    extintor deja el `extintor_id` en NULL, y sin la copia el histórico y el
    Excel de los meses pasados se quedarían sin decir de qué aparato hablaban.

    `anomalias` se guarda en vez de contarse: es lo que decide si la fila ofrece
    el botón de cierre de hallazgo, y contarlo por renglón sería un JOIN más en
    cada carga de una tabla de 160.
    """

    __tablename__ = "extintores_revisiones"
    __table_args__ = (
        # Una revisión por extintor y por día. Las de las fichas eliminadas
        # llevan `extintor_id` en NULL y no chocan entre sí, que es justo lo
        # que se quiere: el histórico de varios aparatos retirados convive.
        UniqueConstraint("extintor_id", "fecha", name="uq_revision_extintor_fecha"),
        CheckConstraint("anomalias >= 0", name="ck_revision_anomalias"),
        Index("ix_extintores_revisiones_fecha", "fecha"),
        # PostgreSQL no indexa las llaves foráneas solo: sin esto, borrar una
        # ficha recorrería la tabla entera para aplicar el SET NULL.
        Index("ix_extintores_revisiones_extintor", "extintor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    extintor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("extintores.id", ondelete="SET NULL"),
        nullable=True,
    )
    folio: Mapped[str] = mapped_column(String(20), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(150), nullable=False)

    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    anomalias: Mapped[int] = mapped_column(Integer, nullable=False)

    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    puntos: Mapped[list["PuntoRevisionExtintor"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PuntoRevisionExtintor.orden",
    )

    def __repr__(self) -> str:
        return f"<RevisionExtintor {self.folio} {self.fecha}>"


class PuntoRevisionExtintor(Base):
    """Uno de los doce puntos de una revisión.

    `orden` es la posición en `PUNTOS_EXTINTOR`, y `clave` se guarda además
    como respaldo legible: si algún día la tupla creciera por en medio —que no
    debe—, el renglón viejo seguiría diciendo qué se revisó.
    """

    __tablename__ = "extintores_revisiones_puntos"
    __table_args__ = (
        UniqueConstraint("revision_id", "orden", name="uq_punto_extintor_orden"),
        CheckConstraint("valor IN ('ok', 'no_ok')", name="ck_punto_extintor_valor"),
        # La observación obligatoria en NO OK, sostenida también por la base:
        # un hallazgo sin explicar no sirve como evidencia, y el servicio no
        # puede ser la única red.
        CheckConstraint(
            "valor = 'ok' OR (observaciones IS NOT NULL "
            "AND length(btrim(observaciones)) > 0)",
            name="ck_punto_extintor_observaciones",
        ),
        Index("ix_extintores_puntos_revision", "revision_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("extintores_revisiones.id", ondelete="CASCADE"),
        nullable=False,
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    clave: Mapped[str] = mapped_column(String(40), nullable=False)
    valor: Mapped[str] = mapped_column(String(6), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    revision: Mapped[RevisionExtintor] = relationship(back_populates="puntos")

    fotos: Mapped[list["FotoControl"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="punto_extintor",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FotoControl.orden",
    )

    def __repr__(self) -> str:
        return f"<PuntoRevisionExtintor {self.clave}={self.valor}>"


# --- El mismo semáforo, en SQL ----------------------------------------------
#
# El filtro por estado tiene que resolverse en la base: clasificar en Python
# rompería el conteo y la paginación de `extintor_service.listar()` (regla 4).
#
# Es una FUNCIÓN y no un dict de módulo como `EXPRESIONES_ESTADO` del catálogo:
# aquí los cortes dependen del día, y un dict calculado al importar se quedaría
# congelado con la fecha en que arrancó el contenedor —un proceso que lleva
# semanas vivo iría clasificando cada vez peor, sin que nada fallara—.


def expresiones_estado(hoy: date) -> dict[str, ColumnElement[bool]]:
    """Las mismas cuatro ramas de `estado_vencimiento()`, en SQL.

    Cada rama niega las anteriores: sin eso, `por_vencer` recogería filas que
    en Python ya salieron `critico` y el filtro mostraría un color distinto al
    de la columna.
    """
    critico = Extintor.vencimiento <= sumar_meses(hoy, MESES_CRITICO)
    por_vencer = Extintor.vencimiento <= sumar_meses(hoy, MESES_POR_VENCER)
    vencido = Extintor.vencimiento < hoy

    return {
        ESTADO_VENCIDO: vencido,
        ESTADO_CRITICO: and_(not_(vencido), critico),
        ESTADO_POR_VENCER: and_(not_(vencido), not_(critico), por_vencer),
        ESTADO_VIGENTE: and_(not_(vencido), not_(critico), not_(por_vencer)),
    }
