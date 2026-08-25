"""Schemas de los rondines de seguridad."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _texto(valor: str) -> str:
    """Recorta espacios y colapsa los interiores."""
    return " ".join(valor.split())


class PuntoRondinBase(BaseModel):
    """Campos comunes al alta y a la edición de un punto."""

    numero: int = Field(ge=1, le=999, description="El que se imprime en la etiqueta.")
    nombre: str = Field(min_length=1, max_length=150)
    ubicacion: str | None = Field(default=None, max_length=150)

    @field_validator("nombre")
    @classmethod
    def _limpiar_nombre(cls, valor: str) -> str:
        limpio = _texto(valor)
        if not limpio:
            raise ValueError("El nombre del punto es obligatorio.")
        return limpio

    @field_validator("ubicacion")
    @classmethod
    def _limpiar_ubicacion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return _texto(valor) or None


class PuntoRondinCrear(PuntoRondinBase):
    """Alta de un punto. El token del QR lo genera el servidor."""


class PuntoRondinActualizar(PuntoRondinBase):
    """Edición de un punto. El token no se toca: el QR impreso sigue vivo."""

    activo: bool = True


class PuntoRondinOut(BaseModel):
    """Punto de control tal como sale de la API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero: int
    nombre: str
    ubicacion: str | None = None
    #: Lo que va en el QR. Solo se sirve con sesión: es la credencial del punto.
    token_publico: str
    activo: bool
    creado_at: datetime
    actualizado_at: datetime | None = None


class FilaTableroOut(BaseModel):
    """Un punto con sus seis celdas del turno."""

    numero: int
    nombre: str
    ubicacion: str | None = None
    #: Hora del escaneo por rondín, o ``null`` si no se visitó.
    rondines: list[datetime | None]
    visitados: int


class TableroOut(BaseModel):
    """Todo lo que pinta la pantalla, ya resuelto en el servidor.

    El frontend no recalcula nada: misma disciplina que la semaforización de
    Rayser y la del catálogo de insumos.
    """

    fecha: date
    turno: str
    inicio: datetime
    fin: datetime
    puntos_activos: int
    rondines: int
    filas: list[FilaTableroOut]
    visitados: int
    total: int
    cumplimiento: float
    #: Puntos visitados en cada rondín, en orden.
    por_rondin: list[int]
    #: Índice del rondín que corre ahora, o ``null`` si el turno no está vivo.
    rondin_actual: int | None = None
    avance_actual: int | None = None


class EnvioReporteIn(BaseModel):
    """Petición de envío manual del reporte de un turno."""

    fecha: date
    turno: str
    destinatario: str = Field(min_length=3, max_length=200)


class MensajeRondin(BaseModel):
    """Respuesta simple con un mensaje en español."""

    mensaje: str
