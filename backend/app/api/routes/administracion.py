"""Pestaña de Administración: usuarios, bitácora y mantenimiento.

Todo el router exige sesión de **superadministrador**.

El prefijo ``/api/administracion`` es nuevo, así que hay que darlo de alta
como aplicación de Cloudflare Access, igual que la ruta ``administracion``
del panel (ver la regla 7 del CLAUDE.md y la lista de pendientes de
SEGURIDAD.md). Mientras eso no ocurra, lo único que lo defiende es la cookie
de sesión más la comprobación del rol.
"""

import uuid
from datetime import date, time

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import requiere_superadmin
from app.core.bitacora import anotar
from app.core.config import settings
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.schemas.administracion import (
    AccesoPgAdmin,
    BitacoraFila,
    BitacoraPaginada,
    MantenimientoOut,
    UsuarioActualizar,
    UsuarioCrear,
    UsuarioEstado,
    UsuarioOut,
)
from app.services import bitacora_service, usuario_service

router = APIRouter(
    prefix="/administracion",
    tags=["administracion"],
    dependencies=[Depends(requiere_superadmin)],
)


# --- Usuarios --------------------------------------------------------------


@router.get(
    "/usuarios",
    response_model=list[UsuarioOut],
    summary="Lista los usuarios del panel",
)
async def listar_usuarios(db: AsyncSession = Depends(get_db)) -> list[UsuarioOut]:
    """Todos los usuarios, con su estado y sus permisos."""
    usuarios = await usuario_service.listar(db)
    return [UsuarioOut.model_validate(usuario) for usuario in usuarios]


@router.post(
    "/usuarios",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Da de alta un usuario",
)
async def crear_usuario(
    datos: UsuarioCrear,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UsuarioOut:
    """Crea la cuenta activa, con los permisos que se marcaron."""
    usuario = await usuario_service.crear(db, datos)
    anotar(request, detalle=usuario.username)
    return UsuarioOut.model_validate(usuario)


@router.put(
    "/usuarios/{usuario_id}",
    response_model=UsuarioOut,
    summary="Edita los datos y los permisos de un usuario",
)
async def actualizar_usuario(
    usuario_id: uuid.UUID,
    datos: UsuarioActualizar,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UsuarioOut:
    """La contraseña solo cambia si se escribe una nueva."""
    usuario = await usuario_service.actualizar(db, usuario_id, datos)
    anotar(request, detalle=usuario.username)
    return UsuarioOut.model_validate(usuario)


@router.patch(
    "/usuarios/{usuario_id}/activo",
    response_model=UsuarioOut,
    summary="Activa o desactiva un usuario",
)
async def cambiar_estado_usuario(
    usuario_id: uuid.UUID,
    datos: UsuarioEstado,
    request: Request,
    db: AsyncSession = Depends(get_db),
    autor: AdminUser = Depends(requiere_superadmin),
) -> UsuarioOut:
    """Desactivar corta también las sesiones que ese usuario tenga abiertas."""
    usuario = await usuario_service.cambiar_estado(
        db, usuario_id, activo=datos.activo, autor=autor
    )
    estado = "activado" if usuario.activo else "desactivado"
    anotar(request, detalle=f"{usuario.username} ({estado})")
    return UsuarioOut.model_validate(usuario)


@router.delete(
    "/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un usuario definitivamente",
)
async def eliminar_usuario(
    usuario_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    autor: AdminUser = Depends(requiere_superadmin),
) -> Response:
    """El histórico se conserva: la bitácora guarda el nombre, no solo el FK."""
    username = await usuario_service.eliminar(db, usuario_id, autor=autor)
    anotar(request, detalle=username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Bitácora --------------------------------------------------------------
# IMPORTANTE: /bitacora/usuarios va declarada ANTES que cualquier ruta
# paramétrica de /bitacora, o FastAPI intentaría leer "usuarios" como el
# parámetro de la otra.


@router.get(
    "/bitacora/usuarios",
    response_model=list[str],
    summary="Usuarios con actividad registrada",
)
async def usuarios_de_la_bitacora(db: AsyncSession = Depends(get_db)) -> list[str]:
    """Alimenta el filtro por usuario, incluidos los ya eliminados."""
    return await bitacora_service.usuarios_registrados(db)


@router.get(
    "/bitacora",
    response_model=BitacoraPaginada,
    summary="Actividad registrada del sistema",
)
async def listar_bitacora(
    fecha: date | None = Query(default=None),
    hora_desde: time | None = Query(default=None),
    hora_hasta: time | None = Query(default=None),
    usuario: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
) -> BitacoraPaginada:
    """Página de 50 renglones, de lo más reciente a lo más antiguo."""
    filtros = bitacora_service.FiltrosBitacora(
        fecha=fecha,
        hora_desde=hora_desde,
        hora_hasta=hora_hasta,
        usuario=usuario or None,
    )
    resultado = await bitacora_service.listar(db, filtros, page)

    return BitacoraPaginada(
        total=resultado["total"],
        page=resultado["page"],
        size=resultado["size"],
        items=[BitacoraFila.model_validate(fila) for fila in resultado["items"]],
    )


# --- Mantenimiento ---------------------------------------------------------


@router.get(
    "/mantenimiento",
    response_model=MantenimientoOut,
    summary="Accesos a pgAdmin",
)
async def mantenimiento() -> MantenimientoOut:
    """Devuelve las URLs de pgAdmin y las credenciales guardadas.

    Sí, la contraseña sale de la API. Es el punto del botón de "copiar
    credenciales": pgAdmin no admite iniciar sesión desde una liga externa
    (su formulario exige un token CSRF propio), así que lo más cerca del
    acceso de un clic es abrir la pestaña con las credenciales ya en el
    portapapeles. Solo la ve un superadministrador con sesión iniciada, y
    queda anotado como riesgo aceptado en SEGURIDAD.md.
    """
    accesos = [
        AccesoPgAdmin(
            entorno="local",
            url=settings.PGADMIN_URL_LOCAL,
            disponible=bool(settings.PGADMIN_URL_LOCAL.strip()),
        ),
        AccesoPgAdmin(
            entorno="produccion",
            url=settings.PGADMIN_URL_PRODUCCION,
            disponible=bool(settings.PGADMIN_URL_PRODUCCION.strip()),
        ),
    ]

    return MantenimientoOut(
        accesos=accesos,
        email=settings.PGADMIN_EMAIL,
        password=settings.PGADMIN_PASSWORD,
        configurado=settings.pgadmin_configurado,
    )
