"""Schemas de las recepciones de mercancía."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _texto_opcional(valor: str | None) -> str | None:
    """Recorta espacios y deja en ``None`` lo que quede vacío."""
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


class ItemRecepcionCrear(BaseModel):
    """Una partida capturada o corregida por el operador."""

    codigo: str = Field(min_length=1, max_length=150)
    cantidad: int = Field(gt=0)

    @field_validator("codigo")
    @classmethod
    def _limpiar_codigo(cls, valor: str) -> str:
        limpio = " ".join(valor.split())
        if not limpio:
            raise ValueError("El código del insumo es obligatorio.")
        return limpio


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
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    descripcion: str | None = None
    unidad_medida: str
    cantidad: int


class RecepcionOut(BaseModel):
    """Una recepción tal como la consume el panel."""

    model_config = ConfigDict(from_attributes=True)

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
