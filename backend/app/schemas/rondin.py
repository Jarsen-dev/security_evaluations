"""Schemas de los rondines de seguridad."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class PuntoRondinOut(BaseModel):
    """Punto de control tal como sale de la API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero: int
    nombre: str
    #: AppSheet no tiene una ubicación legible: `Ubicación_Referencia` son
    #: coordenadas y el nombre YA es el lugar ("CASETA", "SILOS"). Se queda por
    #: si algún día se captura a mano.
    ubicacion: str | None = None
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
    #: Bloques del turno que ya ocurrieron. El cumplimiento se mide contra
    #: estos, no contra los seis: los rondines futuros no son faltas.
    rondines_transcurridos: int
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
    """Petición de envío manual del reporte de un turno.

    ``destinatario`` es ``EmailStr`` y no ``str``: con un ``str`` pelado, un
    valor con comas se convertía en varios destinatarios reales al armar la
    cabecera ``To``, y cualquier texto sin arroba solo fallaba mucho después,
    ya dentro del SMTP.
    """

    fecha: date
    turno: str
    destinatario: EmailStr = Field(max_length=200)


class MensajeRondin(BaseModel):
    """Respuesta simple con un mensaje en español."""

    mensaje: str


# --- Ingesta desde AppSheet ------------------------------------------------


class EscaneoAppSheetIn(BaseModel):
    """Un escaneo tal como lo manda el Bot de AppSheet.

    ``extra="ignore"`` porque AppSheet manda las columnas que se le antojen
    —GPS, foto, comentario, y las que agregue mañana— y ninguna debe tumbar
    el lote.

    ``escaneado_at`` es ``str`` y NO ``datetime`` a propósito: con un
    ``datetime``, Pydantic rechazaría el lote entero con un 422 por una sola
    fecha ilegible, y el 2.6 % del histórico viene sucio. Se parsea en el
    servicio para que una fila mala descarte una fila.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    origen_id: str | None = Field(default=None, alias="id", max_length=64)
    numero: int | None = None
    escaneado_at: str | None = None

    def a_dict(self) -> dict[str, Any]:
        """Aplana el modelo con sus extras, que es lo que el servicio espera."""
        return {**(self.model_extra or {}), **self.model_dump(exclude_none=True)}


class LoteEscaneosIn(BaseModel):
    """Lo que llega al webhook.

    Acepta las tres formas que puede tomar el cuerpo de un Bot según cómo se
    configure: un objeto suelto (una fila por petición, el modo normal), una
    lista, o ``{"escaneos": [...]}``.
    """

    escaneos: list[EscaneoAppSheetIn] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _aceptar_fila_suelta(cls, datos: Any) -> Any:
        if isinstance(datos, list):
            return {"escaneos": datos}
        if isinstance(datos, dict) and "escaneos" not in datos:
            return {"escaneos": [datos]}
        return datos


class IngestaOut(BaseModel):
    """Resumen de lo que pasó con el lote."""

    recibidos: int
    insertados: int
    duplicados: int
    descartados: int
