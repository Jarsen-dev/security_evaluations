"""Schemas de autenticación."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.administracion import PermisoModulo


class LoginRequest(BaseModel):
    """Credenciales enviadas por el formulario de acceso."""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class AdminOut(BaseModel):
    """Datos del usuario en sesión que sí pueden salir de la API.

    Nunca incluye ``password_hash``.

    Lleva el rol y los permisos porque el panel los necesita para esconder
    las pestañas y los botones que esta persona no puede usar. Es cosmética:
    quien autoriza de verdad es la dependencia de cada endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    username: str
    email: str | None = None
    activo: bool
    es_superadmin: bool
    permisos: dict[str, PermisoModulo]
    last_login_at: datetime | None = None


class MensajeOut(BaseModel):
    """Respuesta simple con un mensaje en español."""

    mensaje: str
