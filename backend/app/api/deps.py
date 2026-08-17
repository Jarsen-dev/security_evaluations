"""Dependencias compartidas de la capa HTTP."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import COOKIE_SESION, TokenInvalidoError, decodificar_token
from app.db.session import get_db
from app.models.admin_user import AdminUser

NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No has iniciado sesión o tu sesión expiró.",
)


async def obtener_admin_actual(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Devuelve el administrador de la sesión actual.

    Lee el JWT de la cookie httpOnly, valida su firma y confirma que el
    usuario sigue existiendo: si se elimina un admin, sus tokens vigentes
    dejan de servir de inmediato.
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

    return admin
