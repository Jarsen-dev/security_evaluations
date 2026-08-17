"""Schemas de autenticación."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credenciales enviadas por el formulario de acceso."""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class AdminOut(BaseModel):
    """Datos del administrador que sí pueden salir de la API.

    Nunca incluye ``password_hash``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    last_login_at: datetime | None = None


class MensajeOut(BaseModel):
    """Respuesta simple con un mensaje en español."""

    mensaje: str
