"""Dependencias compartidas de la capa HTTP."""

import ipaddress
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import obtener_ip_cliente
from app.core.security import COOKIE_SESION, TokenInvalidoError, decodificar_token
from app.db.session import get_db
from app.models.admin_user import AdminUser


def ip_valida(request: Request) -> str | None:
    """Devuelve la IP del cliente solo si es una dirección válida.

    Las columnas `ip` e `ip_origen` son de tipo INET: un valor con formato
    inválido —por una cabecera manipulada— abortaría el insert completo.
    """
    crudo = obtener_ip_cliente(request)
    try:
        return str(ipaddress.ip_address(crudo))
    except ValueError:
        return None

NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No has iniciado sesión o tu sesión expiró.",
)

# Se responde 401, no 403: para el usuario desactivado la sesión dejó de
# existir, y el panel ya sabe rebotar al login ante un 401.
CUENTA_DESACTIVADA = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Tu cuenta fue desactivada. Habla con el administrador del sistema.",
)

SIN_PERMISO = "No tienes permiso para realizar esta acción."


async def obtener_admin_actual(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Devuelve el usuario de la sesión actual.

    Lee el JWT de la cookie httpOnly, valida su firma y confirma que el
    usuario sigue existiendo y sigue activo: si se elimina o se desactiva a
    alguien, sus tokens vigentes dejan de servir de inmediato en vez de
    esperar a que venzan.
    """
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        raise NO_AUTENTICADO

    try:
        payload = decodificar_token(token)
    except TokenInvalidoError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise NO_AUTENTICADO

    try:
        admin_id = uuid.UUID(sub)
    except ValueError as exc:
        raise NO_AUTENTICADO from exc

    admin = await db.scalar(select(AdminUser).where(AdminUser.id == admin_id))
    if admin is None:
        raise NO_AUTENTICADO

    if not admin.activo:
        raise CUENTA_DESACTIVADA

    return admin


def requiere(
    modulo: str, *, editar: bool = False
) -> Callable[[AdminUser], Awaitable[AdminUser]]:
    """Fábrica de dependencias: exige acceso (o edición) sobre un módulo.

    Se cuelga del ``APIRouter`` completo para el acceso de lectura y alta, y
    se repite por endpoint con ``editar=True`` en los que modifican o
    eliminan. La decisión la toma ``AdminUser.puede()``; aquí solo se
    traduce a HTTP.

    El panel esconde las pestañas y los botones que el usuario no puede usar,
    pero eso es cosmética: quien realmente autoriza es esta dependencia.
    """

    async def dependencia(
        admin: AdminUser = Depends(obtener_admin_actual),
    ) -> AdminUser:
        if not admin.puede(modulo, editar=editar):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=SIN_PERMISO
            )
        return admin

    return dependencia


async def requiere_superadmin(
    admin: AdminUser = Depends(obtener_admin_actual),
) -> AdminUser:
    """Exige el rol de superadministrador (la pestaña de Administración)."""
    if not admin.es_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SIN_PERMISO)
    return admin
