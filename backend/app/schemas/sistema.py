"""Schemas de endpoints de sistema y catálogos."""

from pydantic import BaseModel, Field


class EstadoSalud(BaseModel):
    """Respuesta de ``GET /api/health``."""

    status: str = Field(description="'ok' si la API responde.")
    db: str = Field(description="'ok' si la base de datos contesta la consulta de prueba.")
    version: str = Field(description="Versión de la aplicación.")


class AreaOut(BaseModel):
    """Área de la planta tal como la consume el frontend."""

    value: str = Field(description="Valor almacenado en la base de datos, sin acentos.")
    label: str = Field(description="Etiqueta mostrada al usuario, con acentos.")
