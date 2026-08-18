"""Schemas de endpoints de sistema y catálogos."""

from pydantic import BaseModel, Field


class EstadoSalud(BaseModel):
    """Respuesta de ``GET /api/health``."""

    status: str = Field(description="'ok' si la API responde.")
    db: str = Field(description="'ok' si la base de datos contesta la consulta de prueba.")
    version: str = Field(description="Versión de la aplicación.")


class ConfigWifi(BaseModel):
    """Datos de la red WiFi para armar el código QR de acceso.

    Solo se entrega al administrador: incluye la contraseña de la red.
    """

    configurado: bool = Field(
        description="False si no se capturó la red en el archivo .env."
    )
    ssid: str = Field(description="Nombre de la red.")
    password: str = Field(description="Contraseña de la red.")
    seguridad: str = Field(description="WPA, WEP o nopass.")
    oculta: bool = Field(description="Si la red no difunde su nombre.")


class AreaOut(BaseModel):
    """Área de la planta tal como la consume el frontend."""

    value: str = Field(description="Valor almacenado en la base de datos, sin acentos.")
    label: str = Field(description="Etiqueta mostrada al usuario, con acentos.")
