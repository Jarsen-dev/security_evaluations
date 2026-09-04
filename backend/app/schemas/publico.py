"""Schemas del formulario público.

REGLA CRÍTICA DEL PROYECTO: ningún schema de este módulo puede exponer
``es_correcta``. El formulario se sirve sin autenticación; si la respuesta
correcta viajara al navegador, cualquiera la vería abriendo las herramientas
de desarrollo. Por eso existe ``OpcionPublica`` en lugar de reutilizar
``OpcionOut`` del panel de administración.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import AREAS_VALIDAS


class OpcionPublica(BaseModel):
    """Opción sin revelar si es la correcta."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    orden: int
    texto: str
    # Deliberadamente NO se declara `es_correcta`.


class PreguntaPublica(BaseModel):
    """Pregunta con sus opciones, sin la respuesta correcta."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    orden: int
    texto: str
    opciones: list[OpcionPublica]


class CuestionarioPublico(BaseModel):
    """Lo que ve quien abre la liga pública.

    No incluye el id interno del cuestionario ni banderas de administración.
    """

    nombre: str
    descripcion: str | None
    total_preguntas: int
    preguntas: list[PreguntaPublica]


class IniciarIntentoIn(BaseModel):
    """Datos de identidad que se piden antes de empezar."""

    nombre: str = Field(min_length=2, max_length=150)
    numero_empleado: str = Field(min_length=1, max_length=30)
    area: str = Field(max_length=30)

    @field_validator("nombre", "numero_empleado")
    @classmethod
    def _limpiar(cls, valor: str) -> str:
        return valor.strip()

    @field_validator("area")
    @classmethod
    def _validar_area(cls, valor: str) -> str:
        """Rechaza áreas fuera del catálogo.

        Se valida contra la constante del backend y no contra lo que mande el
        cliente: el `<select>` del navegador se puede manipular.
        """
        limpio = valor.strip()
        if limpio not in AREAS_VALIDAS:
            raise ValueError("El área seleccionada no es válida.")
        return limpio


class IntentoIniciado(BaseModel):
    """Respuesta al crear el intento."""

    intento_id: uuid.UUID
    nombre: str
    total_preguntas: int


class GuardarRespuestaIn(BaseModel):
    """Cuerpo del autoguardado."""

    pregunta_id: uuid.UUID
    opcion_id: uuid.UUID


class RespuestaGuardada(BaseModel):
    """Confirmación del autoguardado.

    NO informa si la respuesta fue correcta: eso convertiría el formulario en
    un detector de respuestas a base de prueba y error.
    """

    pregunta_id: uuid.UUID
    opcion_id: uuid.UUID
    guardado: bool = True


class EstadoIntento(BaseModel):
    """Estado de un intento en curso, para restaurarlo tras recargar."""

    intento_id: uuid.UUID
    nombre: str
    numero_empleado: str
    area: str
    finalizado: bool
    # pregunta_id -> opcion_id de lo ya contestado. Sin marcas de acierto.
    respuestas: dict[uuid.UUID, uuid.UUID]


class ResultadoIntento(BaseModel):
    """Resultado que se muestra en la pantalla de gracias."""

    intento_id: uuid.UUID
    nombre: str
    total_preguntas: int
    correctas: int
    puntaje: Decimal
    aprobado: bool
    umbral_aprobacion: int
    finalizado_at: datetime

