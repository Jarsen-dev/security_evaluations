"""Schemas del dashboard de estadísticas (solo administración)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ParticipacionResumen(BaseModel):
    """Respuestas recibidas contra la meta de headcount."""

    recibidas: int
    meta: int | None = Field(
        default=None,
        description="Suma del headcount configurado; None si no hay metas capturadas.",
    )
    porcentaje: float | None = Field(
        default=None, description="None cuando no hay meta: no hay denominador."
    )


class ResumenOut(BaseModel):
    """KPIs de la fila superior del dashboard."""

    total_respuestas: int
    total_en_progreso: int = Field(
        description="Intentos iniciados que nunca se finalizaron."
    )
    participacion: ParticipacionResumen
    promedio_general: float | None
    tasa_aprobacion: float | None
    aprobados: int
    umbral_aprobacion: int


class EstadisticaArea(BaseModel):
    """Fila de la gráfica y la hoja "Por área"."""

    area: str
    label: str
    intentos: int
    promedio: float | None
    minimo: float | None
    maximo: float | None
    aprobados: int
    porcentaje_aprobacion: float | None
    meta: int | None
    porcentaje_participacion: float | None


class DesgloseOpcion(BaseModel):
    """Cuántas personas eligieron cada opción de una pregunta."""

    opcion_id: uuid.UUID
    texto: str
    es_correcta: bool
    elegida: int
    porcentaje: float


class EstadisticaPregunta(BaseModel):
    """Fila de la gráfica de preguntas con mayor índice de error."""

    pregunta_id: uuid.UUID
    orden: int
    texto: str
    total_respuestas: int
    correctas: int
    incorrectas: int
    porcentaje_acierto: float | None
    porcentaje_error: float | None
    opciones: list[DesgloseOpcion]


class RangoDistribucion(BaseModel):
    """Barra del histograma de calificaciones."""

    rango: str
    cantidad: int


class PuntoLineaTiempo(BaseModel):
    """Punto de la serie "respuestas por día"."""

    fecha: date
    cantidad: int
    promedio: float | None


class IntentoFila(BaseModel):
    """Fila de la tabla paginada de intentos."""

    id: uuid.UUID
    nombre: str
    numero_empleado: str
    area: str
    area_label: str
    iniciado_at: datetime
    finalizado_at: datetime | None
    duracion_segundos: int | None
    correctas: int
    total_preguntas: int
    puntaje: Decimal | None


class IntentosPaginados(BaseModel):
    """Respuesta paginada de la tabla de intentos."""

    total: int
    page: int
    size: int
    items: list[IntentoFila]


class MetaAreaOut(BaseModel):
    """Meta de headcount de un área."""

    area: str
    label: str
    headcount: int | None


class MetaAreaIn(BaseModel):
    """Meta enviada desde la pantalla de captura."""

    area: str
    headcount: int = Field(ge=0, le=100000)


class MetasAreaIn(BaseModel):
    """Cuerpo del guardado en lote de metas."""

    metas: list[MetaAreaIn]
