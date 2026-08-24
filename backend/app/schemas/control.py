"""Schemas de los controles ESH (panel de administración).

Estos endpoints exigen sesión: nada de aquí se sirve sin autenticación. Los
schemas del formulario público siguen viviendo aparte, en
``app.schemas.publico`` (ver regla 1 del CLAUDE.md).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import AREAS_VALIDAS
from app.core.controles_catalogo import VALORES_SQP


def _sin_espacios(valor: str) -> str:
    """Recorta espacios al inicio y al final."""
    return valor.strip()


def _texto_opcional(valor: str | None) -> str | None:
    """Recorta espacios y convierte el texto vacío en ``None``."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


# --- Rayser ----------------------------------------------------------------


class LecturaManometro(BaseModel):
    """Una lectura ya clasificada por el servidor."""

    valor: Decimal = Field(description="Presión en psi.")
    semaforo: str = Field(description="'verde', 'rojo' o 'naranja'.")


class RegistroRayserOut(BaseModel):
    """Registro diario tal como lo consume la tabla del panel.

    No incluye la foto: una lista de 31 días con las imágenes embebidas pesaría
    varios megabytes. La evidencia se pide aparte, por
    ``GET /api/controles/rayser/{id}/foto``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    manometros: list[LecturaManometro]
    observaciones: str | None
    tiene_foto: bool
    fuera_de_rango: bool
    responsable: str
    creado_at: datetime


class RangoRayser(BaseModel):
    """Rango de operación que el frontend usa para pintar el semáforo en vivo."""

    minimo: Decimal
    maximo: Decimal
    normal: Decimal
    manometros: int


# El registro de Rayser llega como multipart (trae la foto), así que sus
# campos se declaran con `Form(...)` en la ruta y no hay schema de entrada:
# Pydantic no valida cuerpos multipart campo por campo.


# --- Inspección de SQP -----------------------------------------------------


class PuntoSqpOut(BaseModel):
    """Punto del formato de inspección, servido desde el catálogo del backend."""

    orden: int
    codigo: str
    seccion: str
    texto: str


class CatalogoSqp(BaseModel):
    """Respuesta de ``GET /api/controles/sqp/catalogo``."""

    secciones: list[str]
    puntos: list[PuntoSqpOut]
    renglones_sustancias: int = Field(
        description="Cuántas sustancias caben en la tabla de la hoja impresa."
    )


class RespuestaSqpIn(BaseModel):
    """Respuesta a un punto de la inspección."""

    orden: int = Field(ge=0)
    valor: str = Field(description="'si', 'no' o 'na'.")
    observaciones: str | None = Field(default=None, max_length=2000)

    _limpiar_observaciones = field_validator("observaciones")(_texto_opcional)

    @field_validator("valor")
    @classmethod
    def _validar_valor(cls, valor: str) -> str:
        normalizado = valor.strip().lower()
        if normalizado not in VALORES_SQP:
            raise ValueError("La respuesta debe ser SI, NO o N/A.")
        return normalizado

    @model_validator(mode="after")
    def _exigir_observaciones_en_no(self) -> "RespuestaSqpIn":
        """Un "NO" sin explicación no le sirve a nadie que lea el reporte."""
        if self.valor == "no" and not self.observaciones:
            raise ValueError(
                "Cada punto contestado con NO necesita observaciones."
            )
        return self


class InspeccionSqpCrear(BaseModel):
    """Cuerpo de ``POST /api/controles/sqp``."""

    fecha: date
    area: str = Field(max_length=30)
    encargado: str = Field(min_length=1, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    sustancias: str | None = Field(default=None, max_length=4000)
    respuestas: list[RespuestaSqpIn]

    _limpiar_encargado = field_validator("encargado")(_sin_espacios)
    _limpiar_cargo = field_validator("cargo")(_texto_opcional)
    _limpiar_sustancias = field_validator("sustancias")(_texto_opcional)

    @field_validator("area")
    @classmethod
    def _validar_area(cls, valor: str) -> str:
        limpio = valor.strip()
        if limpio not in AREAS_VALIDAS:
            raise ValueError("El área seleccionada no existe en el catálogo.")
        return limpio


class RespuestaSqpOut(BaseModel):
    """Respuesta guardada, con el texto del punto ya resuelto."""

    orden: int
    codigo: str
    seccion: str
    texto: str
    valor: str
    observaciones: str | None


class InspeccionSqpResumen(BaseModel):
    """Fila del historial de inspecciones."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    area: str
    area_label: str
    encargado: str
    responsable: str
    total_no: int = Field(description="Cuántos puntos salieron como NO.")
    creado_at: datetime


class InspeccionSqpDetalle(InspeccionSqpResumen):
    """Inspección completa, con sus respuestas y el listado de sustancias."""

    cargo: str | None
    sustancias: list[str]
    respuestas: list[RespuestaSqpOut]
