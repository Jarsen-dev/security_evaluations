"""Schemas de las recepciones de mercancía."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import LONGITUD_DESCRIPCION, TOPE_CAJAS_RECEPCION


def _texto_opcional(valor: str | None) -> str | None:
    """Recorta espacios y deja en ``None`` lo que quede vacío."""
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


class ItemRecepcionCrear(BaseModel):
    """Una partida capturada o corregida por el operador.

    ``cantidad`` son **cajas o paquetes**: lo que dice el papel. Las piezas que
    entran al inventario las calcula el servicio multiplicando por las del
    catálogo, nunca el cliente.

    El ``codigo`` por sí solo no identifica al insumo —puede repetirse— y por
    eso viaja también el ``insumo_id`` de la descripción elegida.

    El tope no es una regla de negocio sino la defensa contra el
    desbordamiento del INTEGER: ver ``TOPE_CAJAS_RECEPCION``.
    """

    codigo: str = Field(min_length=1, max_length=150)
    cantidad: int = Field(gt=0, le=TOPE_CAJAS_RECEPCION)

    #: Cuál de las descripciones de ese código se recibió. Es obligatorio en
    #: cuanto el código ampara más de un insumo: sin él, el servicio rechaza la
    #: partida en vez de adivinar (ver ``recepcion_service._resolver_insumo``).
    insumo_id: uuid.UUID | None = None

    #: La descripción **tal como la dice el papel**, no la del catálogo. Es lo
    #: que alimenta el corpus de ejemplos del OCR: enseñarle al modelo a emitir
    #: la descripción del catálogo sería enseñarle a inventar texto que no está
    #: en la hoja, justo lo que su propio prompt le prohíbe.
    descripcion: str | None = Field(default=None, max_length=LONGITUD_DESCRIPCION)

    @field_validator("codigo")
    @classmethod
    def _limpiar_codigo(cls, valor: str) -> str:
        limpio = " ".join(valor.split())
        if not limpio:
            raise ValueError("El código del insumo es obligatorio.")
        return limpio

    _limpiar_descripcion = field_validator("descripcion")(_texto_opcional)


class RecepcionCrear(BaseModel):
    """Lo que el formulario manda al confirmar.

    ``ocr_raw`` y ``advertencias`` viajan de vuelta tal como los devolvió la
    extracción, **sin las correcciones del usuario**: es lo que después
    permite comparar qué leyó la IA contra qué corrigió la persona.
    """

    foto_id: uuid.UUID | None = None
    proveedor: str | None = Field(default=None, max_length=200)
    folio: str | None = Field(default=None, max_length=100)
    fecha: date | None = None
    tipo_documento: str = Field(default="desconocido", max_length=80)
    ocr_ok: bool = False
    ocr_raw: dict[str, Any] | None = None
    advertencias: list[str] | None = None
    items: list[ItemRecepcionCrear] = Field(min_length=1)

    #: Solo cuando el formato no se reconoció y el usuario lo bautiza.
    nuevo_formato: str | None = Field(default=None, max_length=150)

    _limpiar = field_validator("proveedor", "folio", "nuevo_formato")(
        _texto_opcional
    )


class ItemRecepcionOut(BaseModel):
    """Una partida del histórico.

    ``cantidad`` son cajas y ``piezas`` lo que sumó al inventario: se mandan
    los dos números para que el panel no tenga que multiplicar.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    descripcion: str | None = None
    unidad_medida: str
    cantidad: int
    piezas_por_empaque: int
    piezas: int


class RecepcionOut(BaseModel):
    """Una recepción tal como la consume el panel."""

    model_config = ConfigDict(from_attributes=True)

    #: Por qué no se aprendió el formato de este documento, si es que no se
    #: aprendió. La recepción se guarda igual —un fallo aprendiendo no puede
    #: deshacer una entrada de almacén—, pero callarlo dejaba al operador
    #: creyendo que su formato había quedado registrado.
    aviso: str | None = None

    id: uuid.UUID
    foto_id: uuid.UUID | None = None
    proveedor: str | None = None
    folio: str | None = None
    fecha: date | None = None
    tipo_documento: str
    ocr_ok: bool
    creado_por: str
    creado_at: datetime
    items: list[ItemRecepcionOut] = Field(default_factory=list)


class RecepcionesPaginadas(BaseModel):
    total: int
    page: int
    size: int
    items: list[RecepcionOut]


class TipoDocumento(BaseModel):
    """Un formato registrado, para el filtro del historial."""

    slug: str
    nombre: str


class ResultadoOcr(BaseModel):
    """Lo que devuelve el pipeline de extracción.

    ``ocr_ok=False`` **no es un error de la petición**: la foto ya se guardó y
    el formulario abre en captura manual. Por eso la ruta responde 200 y no un
    código de error.
    """

    foto_id: uuid.UUID
    ocr_ok: bool
    tipo_documento: str
    #: ``True`` si el formato ya está registrado; si no, se le pedirá nombre.
    tipo_conocido: bool
    #: El nombre legible del formato reconocido. `tipo_documento` es el
    #: identificador interno y no es lo que hay que enseñarle a nadie.
    tipo_nombre: str | None = None
    proveedor: str | None = None
    folio: str | None = None
    fecha: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    #: Rutas de los campos que la IA no pudo leer (``items[0].cantidad``).
    advertencias: list[str] = Field(default_factory=list)
    #: La extracción cruda, para devolverla intacta al guardar.
    ocr_raw: dict[str, Any] | None = None
    error: str | None = None


class SesionQrOut(BaseModel):
    """La sesión recién creada, para pintar el QR."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expira_en: datetime


class EstadoSesionOut(BaseModel):
    """Respuesta del polling. Deliberadamente escueta: es pública."""

    estado: str
