"""Hashing de contraseñas y emisión/verificación de JWT."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITMO = "HS256"

# Nombre de la cookie de sesión del administrador.
COOKIE_SESION = "evaluaciones_sesion"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenInvalidoError(Exception):
    """El token no es válido, está vencido o fue firmado con otra llave."""


def hashear_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en claro."""
    return pwd_context.hash(contrasena)


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    """Compara una contraseña en claro contra su hash bcrypt."""
    return pwd_context.verify(contrasena, hash_guardado)


def hash_dummy() -> str:
    """Hash de descarte para igualar tiempos cuando el usuario no existe.

    Sin esto, un login con usuario inexistente responde notablemente más
    rápido que uno con contraseña incorrecta, lo que permite enumerar
    usuarios midiendo el tiempo de respuesta.
    """
    return pwd_context.hash("contrasena_inexistente")


def crear_token_acceso(admin_id: uuid.UUID, username: str) -> str:
    """Emite el JWT de sesión del administrador."""
    ahora = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "username": username,
        "iat": ahora,
        "exp": ahora + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITMO)


def decodificar_token(token: str) -> dict[str, Any]:
    """Valida firma y expiración del JWT y devuelve su contenido.

    Lanza ``TokenInvalidoError`` en cualquier caso de fallo: quien llama no
    necesita distinguir entre vencido y manipulado, y no conviene revelarlo.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITMO])
    except jwt.ExpiredSignatureError as exc:
        raise TokenInvalidoError("La sesión expiró.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidoError("La sesión no es válida.") from exc
