"""Schemas de cuestionarios, preguntas y opciones (panel de administración).

Estos schemas SÍ exponen ``es_correcta``: son de uso exclusivo del admin.
Los schemas del formulario público viven en ``app.schemas.publico`` y omiten
ese campo deliberadamente.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _sin_espacios(valor: str) -> str:
    """Recorta espacios al inicio y al final."""
    return valor.strip()


# --- Entrada ---------------------------------------------------------------


class OpcionIn(BaseModel):
    """Opción enviada por el constructor de preguntas.

    ``id`` viene solo cuando la opción ya existe: permite conservar su
    identidad al guardar y no romper las respuestas ya registradas.
    """

    id: uuid.UUID | None = None
    texto: str = Field(min_length=1, max_length=500)
    es_correcta: bool = False

    _limpiar_texto = field_validator("texto")(_sin_espacios)


class PreguntaIn(BaseModel):
    """Pregunta enviada por el constructor."""

    id: uuid.UUID | None = None
    texto: str = Field(min_length=1, max_length=2000)
    puntos: int = Field(default=1, ge=1, le=100)
    opciones: list[OpcionIn] = Field(default_factory=list)

    _limpiar_texto = field_validator("texto")(_sin_espacios)


class CuestionarioCrear(BaseModel):
    """Cuerpo de ``POST /api/cuestionarios``."""

    nombre: str = Field(min_length=1, max_length=200)
    descripcion: str | None = Field(default=None, max_length=2000)
    permitir_multiples_intentos: bool = False
    preguntas: list[PreguntaIn] = Field(default_factory=list)

    _limpiar_nombre = field_validator("nombre")(_sin_espacios)


class CuestionarioActualizar(BaseModel):
    """Cuerpo de ``PUT /api/cuestionarios/{id}``.

    Todos los campos son opcionales: se actualiza solo lo que venga. Si
    ``preguntas`` es ``None`` no se toca el cuestionario; si viene una lista,
    reemplaza el conjunto reconciliando por ``id`` para no perder las
    respuestas de las preguntas que no cambiaron.
    """

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    descripcion: str | None = Field(default=None, max_length=2000)
    activo: bool | None = None
    permitir_multiples_intentos: bool | None = None
    preguntas: list[PreguntaIn] | None = None

    @field_validator("nombre")
    @classmethod
    def _limpiar_nombre(cls, valor: str | None) -> str | None:
        return valor.strip() if valor is not None else None


class OrdenPregunta(BaseModel):
    """Elemento de ``PUT /api/cuestionarios/{id}/preguntas/orden``."""

    id: uuid.UUID
    orden: int = Field(ge=0)


class ReordenarPreguntas(BaseModel):
    """Cuerpo del reordenamiento en lote."""

    preguntas: list[OrdenPregunta] = Field(min_length=1)


# --- Salida ----------------------------------------------------------------


class OpcionOut(BaseModel):
    """Opción vista por el administrador, con la respuesta correcta."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    orden: int
    texto: str
    es_correcta: bool


class PreguntaOut(BaseModel):
    """Pregunta con sus opciones."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    orden: int
    texto: str
    puntos: int
    opciones: list[OpcionOut]


class CuestionarioOut(BaseModel):
    """Detalle completo de un cuestionario."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    descripcion: str | None
    token_publico: str
    activo: bool
    permitir_multiples_intentos: bool
    created_at: datetime
    updated_at: datetime
    preguntas: list[PreguntaOut]


class ErrorImportacion(BaseModel):
    """Problema detectado en una fila del Excel."""

    fila: int
    mensaje: str


class ResultadoImportacionOut(BaseModel):
    """Reporte de la importación desde Excel.

    Además del conteo y los errores que pide la especificación, incluye las
    preguntas parseadas: el frontend las agrega al constructor sin guardarlas
    todavía, para que el usuario pueda revisarlas antes de confirmar.
    """

    importadas: int
    errores: list[ErrorImportacion]
    preguntas: list[PreguntaIn]


class CuestionarioResumen(BaseModel):
    """Fila del listado: incluye los conteos que muestra cada tarjeta."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    descripcion: str | None
    token_publico: str
    activo: bool
    permitir_multiples_intentos: bool
    created_at: datetime
    updated_at: datetime
    total_preguntas: int
    total_respuestas: int
