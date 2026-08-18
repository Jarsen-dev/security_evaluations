"""Endpoints de autenticación del administrador."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual
from app.core.config import settings
from app.core.security import (
    COOKIE_SESION,
    crear_token_acceso,
    hash_dummy,
    verificar_contrasena,
)
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminOut, LoginRequest, MensajeOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Mensaje deliberadamente ambiguo: no revela si el usuario existe.
CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos."


def _establecer_cookie_sesion(response: Response, token: str) -> None:
    """Escribe la cookie de sesión con las banderas de seguridad correctas."""
    response.set_cookie(
        key=COOKIE_SESION,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        httponly=True,  # inaccesible desde JavaScript
        samesite="lax",
        # Activado en producción: todo el acceso entra por el dominio HTTPS
        # del túnel. Si se administra entrando directo por la IP de la LAN
        # (HTTP), hay que apagar COOKIE_SECURE o el navegador descarta la
        # cookie y el login no funciona por esa vía.
        secure=settings.COOKIE_SECURE,
        path="/",
    )


@router.post("/login", response_model=AdminOut, summary="Iniciar sesión")
async def login(
    datos: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AdminOut:
    """Valida las credenciales y emite el JWT de sesión en una cookie httpOnly."""
    admin = await db.scalar(
        select(AdminUser).where(AdminUser.username == datos.username)
    )

    if admin is None:
        # Se verifica contra un hash de descarte para que el tiempo de
        # respuesta no delate si el usuario existe.
        verificar_contrasena(datos.password, hash_dummy())
        logger.warning("Intento de acceso con usuario inexistente: %s", datos.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=CREDENCIALES_INVALIDAS
        )

    if not verificar_contrasena(datos.password, admin.password_hash):
        logger.warning("Contraseña incorrecta para el usuario: %s", admin.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=CREDENCIALES_INVALIDAS
        )

    admin.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(admin)

    _establecer_cookie_sesion(response, crear_token_acceso(admin.id, admin.username))
    logger.info("Sesión iniciada: %s", admin.username)

    return AdminOut.model_validate(admin)


@router.post("/logout", response_model=MensajeOut, summary="Cerrar sesión")
async def logout(response: Response) -> MensajeOut:
    """Borra la cookie de sesión.

    No requiere sesión válida: cerrar sesión con un token ya vencido debe
    funcionar igual y limpiar la cookie del navegador.
    """
    response.delete_cookie(
        key=COOKIE_SESION,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    return MensajeOut(mensaje="Sesión cerrada correctamente.")


@router.get("/me", response_model=AdminOut, summary="Administrador de la sesión actual")
async def me(admin: AdminUser = Depends(obtener_admin_actual)) -> AdminOut:
    """Devuelve el administrador autenticado; 401 si no hay sesión válida."""
    return AdminOut.model_validate(admin)
