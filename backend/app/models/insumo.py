"""Catálogo de insumos de seguridad."""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    and_,
    func,
    not_,
    or_,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement

from app.db.base import Base

#: Estados del semáforo de existencias, del peor al mejor surtido.
ESTADO_SIN_TOPES: Final[str] = "sin_topes"
ESTADO_BAJO: Final[str] = "bajo"
ESTADO_MEDIO: Final[str] = "medio"
ESTADO_NORMAL: Final[str] = "normal"
ESTADO_EXCEDIDO: Final[str] = "excedido"

#: Los cinco, para el select de la pantalla y para validar el filtro.
ESTADOS_INSUMO: Final[tuple[str, ...]] = (
    ESTADO_BAJO,
    ESTADO_MEDIO,
    ESTADO_NORMAL,
    ESTADO_EXCEDIDO,
    ESTADO_SIN_TOPES,
)
ESTADOS_FILTRABLES: Final[frozenset[str]] = frozenset(ESTADOS_INSUMO)

#: Cortes del semáforo, en PORCENTAJE del máximo de inventario.
#:
#: Van como enteros y se comparan multiplicando cruzado (``existencia * 100 <=
#: maximo * 35``) en lugar de dividir por 0.35: un flotante decide mal el color
#: justo en la frontera —con máximo 20, ``0.35 * 20`` puede dar
#: ``7.000000000000001``— y ahí la tabla y el filtro dejarían de coincidir.
CORTE_BAJO: Final[int] = 35
CORTE_MEDIO: Final[int] = 75


def estado_insumo(existencia: int, minimo: int, maximo: int) -> str:
    """Clasifica la existencia contra sus topes de inventario.

    Se calcula en el servidor, igual que la semaforización de los manómetros
    de Rayser: el frontend repite la regla solo para pintar el formulario
    mientras se teclea, pero lo que se muestra en la tabla y lo que decide el
    filtro sale de aquí.

    Un insumo sin máximo capturado no se semaforiza: se devuelve
    ``sin_topes`` y la pantalla muestra un guion. Es la misma distinción que
    hacen las metas por área —"no sabemos cuántos son" no es lo mismo que
    "no hay existencia"—, y sin ella un catálogo recién importado saldría
    entero en verde, porque cualquier cantidad alcanza el 75 % de cero.

    El orden de las ramas es el contrato: ``EXPRESIONES_ESTADO`` lo repite en
    SQL y ``tests/test_catalogo.py`` compara las dos, rama por rama.
    """
    if maximo <= 0:
        return ESTADO_SIN_TOPES
    if existencia > maximo:
        return ESTADO_EXCEDIDO
    # El mínimo capturado manda aunque el porcentaje no lo alcance: es el punto
    # en el que hay que resurtir, y por eso pinta rojo aunque sea el 60 % del
    # máximo.
    if existencia < minimo or existencia * 100 <= maximo * CORTE_BAJO:
        return ESTADO_BAJO
    if existencia * 100 <= maximo * CORTE_MEDIO:
        return ESTADO_MEDIO
    return ESTADO_NORMAL


class Insumo(Base):
    """Un renglón del catálogo de insumos de seguridad.

    Dos números que se confunden fácil y significan cosas distintas:

    - ``piezas_por_empaque`` es el contenido de una caja o paquete —las
      pastillas de un blíster, las piezas de un paquete de guantes—. Es un dato
      del producto, no del almacén, y solo cambia si el proveedor cambia la
      presentación.
    - ``existencia`` es el inventario real, en piezas sueltas. Lo suma cada
      recepción confirmada (``recepcion_service``: se capturan cajas y entra
      ``cajas × piezas_por_empaque``) y se corrige a mano tras el conteo
      físico.

    ``minimo`` y ``maximo`` están en piezas, la misma unidad que la existencia.

    Dos insumos pueden compartir ``codigo``; lo que no puede repetirse es la
    pareja código + descripción.

    Quién dio de alta o modificó cada insumo no se guarda aquí: la bitácora
    ya lo registra con nombre, fecha y detalle.
    """

    __tablename__ = "insumos"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # El código NO identifica al insumo: un mismo código de proveedor ampara
    # varios productos y lo que los distingue es la descripción. El índice
    # único de la migración es sobre `(lower(codigo), lower(descripcion))`, sin
    # distinguir mayúsculas: si no, "GN-100" y "gn-100" serían dos insumos y la
    # importación los duplicaría.
    codigo: Mapped[str] = mapped_column(String(150), nullable=False)
    # Obligatoria, y acotada a 300 porque entra al índice: una entrada de btree
    # no pasa de ~2704 bytes.
    descripcion: Mapped[str] = mapped_column(String(300), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    unidad_medida: Mapped[str] = mapped_column(String(10), nullable=False)
    proveedor: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Nunca cero: un producto trae al menos una pieza por empaque, y con cero
    # cualquier recepción daría entrada a nada.
    piezas_por_empaque: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    existencia: Mapped[int] = mapped_column(
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
        """Semáforo de la existencia contra sus topes."""
        return estado_insumo(self.existencia, self.minimo, self.maximo)

    def __repr__(self) -> str:
        return f"<Insumo {self.codigo}>"


# --- El mismo semáforo, en SQL -------------------------------------------
#
# El filtro por estado tiene que resolverse en la base: clasificar en Python
# rompería el conteo y la paginación de `insumo_service.listar()`. Las
# condiciones se arman aquí, pegadas a `estado_insumo()`, para que la regla no
# viva en dos archivos y se pueda contrastar en una prueba.
#
# Cada rama repite `maximo > 0` y niega las anteriores: sin eso, `medio`
# recogería filas que en Python ya salieron `bajo` y el filtro mostraría un
# color distinto al de la columna.

_CON_TOPES: ColumnElement[bool] = Insumo.maximo > 0
_EXCEDIDO: ColumnElement[bool] = Insumo.existencia > Insumo.maximo
_BAJO: ColumnElement[bool] = or_(
    Insumo.existencia < Insumo.minimo,
    Insumo.existencia * 100 <= Insumo.maximo * CORTE_BAJO,
)
_MEDIO: ColumnElement[bool] = Insumo.existencia * 100 <= Insumo.maximo * CORTE_MEDIO

EXPRESIONES_ESTADO: Final[dict[str, ColumnElement[bool]]] = {
    ESTADO_SIN_TOPES: Insumo.maximo <= 0,
    ESTADO_EXCEDIDO: and_(_CON_TOPES, _EXCEDIDO),
    ESTADO_BAJO: and_(_CON_TOPES, not_(_EXCEDIDO), _BAJO),
    ESTADO_MEDIO: and_(_CON_TOPES, not_(_EXCEDIDO), not_(_BAJO), _MEDIO),
    ESTADO_NORMAL: and_(_CON_TOPES, not_(_EXCEDIDO), not_(_BAJO), not_(_MEDIO)),
}
