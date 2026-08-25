"""Gestión de los usuarios del panel.

Solo el superadministrador llega aquí (lo impone la dependencia del router).
Las reglas que este módulo protege existen para que el sistema no pueda
quedarse sin nadie que lo administre: eso solo se recuperaría entrando por
SSH a correr la CLI.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictoDeNegocio, RecursoNoEncontrado
from app.core.security import hashear_contrasena
from app.models.admin_user import AdminUser
from app.schemas.administracion import Permisos, UsuarioActualizar, UsuarioCrear

DUPLICADO = (
    "Ya existe un usuario con ese nombre de usuario o ese correo electrónico."
)
NO_EXISTE = "El usuario no existe."


def _a_json(permisos: Permisos) -> dict[str, dict[str, bool]]:
    """Convierte los permisos validados a la forma que se guarda en JSONB."""
    return {modulo: {"editar": permiso.editar} for modulo, permiso in permisos.items()}


async def _obtener(db: AsyncSession, usuario_id: uuid.UUID) -> AdminUser:
    """Busca un usuario o lanza 404."""
    usuario = await db.scalar(select(AdminUser).where(AdminUser.id == usuario_id))
    if usuario is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return usuario


async def _otros_superadmins_activos(
    db: AsyncSession, usuario_id: uuid.UUID
) -> int:
    """Cuántos superadministradores activos quedarían sin contar a este."""
    total = await db.scalar(
        select(func.count(AdminUser.id)).where(
            AdminUser.es_superadmin.is_(True),
            AdminUser.activo.is_(True),
            AdminUser.id != usuario_id,
        )
    )
    return total or 0


async def _proteger_ultimo_superadmin(
    db: AsyncSession, objetivo: AdminUser, autor: AdminUser, accion: str
) -> None:
    """Impide quedarse sin quien administre el sistema.

    Dos casos, y ambos han de bloquearse antes de tocar la base:

    * Quitarse a uno mismo. Es casi siempre un clic equivocado en la fila
      propia, y el resultado es perder el acceso en el acto.
    * Dejar cero superadministradores activos. A partir de ahí la pestaña de
      Administración deja de existir para todos y solo se recupera con
      ``python -m app.cli create-admin`` dentro del contenedor.
    """
    if objetivo.id == autor.id:
        raise ConflictoDeNegocio(f"No puedes {accion} tu propia cuenta.")

    if objetivo.es_superadmin and not await _otros_superadmins_activos(
        db, objetivo.id
    ):
        raise ConflictoDeNegocio(
            f"No puedes {accion} al último superadministrador activo: "
            f"el sistema se quedaría sin quien lo administre."
        )


async def listar(db: AsyncSession) -> list[AdminUser]:
    """Todos los usuarios, del más antiguo al más reciente.

    Sin paginar a propósito: son las personas del departamento, no un
    catálogo que crezca.
    """
    resultado = await db.scalars(select(AdminUser).order_by(AdminUser.created_at))
    return list(resultado.all())


async def crear(db: AsyncSession, datos: UsuarioCrear) -> AdminUser:
    """Da de alta un usuario del panel.

    Nace activo y sin el rol de superadministrador: ese solo se otorga desde
    la CLI, para que no se pueda escalar privilegios desde la interfaz.
    """
    usuario = AdminUser(
        nombre=datos.nombre,
        username=datos.username,
        email=str(datos.email),
        password_hash=hashear_contrasena(datos.password),
        activo=True,
        es_superadmin=False,
        permisos=_a_json(datos.permisos),
    )
    db.add(usuario)

    # Se deja que la base decida la unicidad en lugar de consultarla antes:
    # entre el SELECT y el INSERT cabe otra alta con el mismo usuario.
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(DUPLICADO) from exc

    await db.refresh(usuario)
    return usuario


async def actualizar(
    db: AsyncSession, usuario_id: uuid.UUID, datos: UsuarioActualizar
) -> AdminUser:
    """Actualiza los datos y los permisos de un usuario.

    La contraseña solo se toca si viene una nueva; el schema ya convierte la
    cadena vacía en ``None``.
    """
    usuario = await _obtener(db, usuario_id)

    usuario.nombre = datos.nombre
    usuario.username = datos.username
    usuario.email = str(datos.email)
    usuario.permisos = _a_json(datos.permisos)
    usuario.actualizado_at = datetime.now(UTC)

    if datos.password:
        usuario.password_hash = hashear_contrasena(datos.password)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(DUPLICADO) from exc

    await db.refresh(usuario)
    return usuario


async def cambiar_estado(
    db: AsyncSession, usuario_id: uuid.UUID, *, activo: bool, autor: AdminUser
) -> AdminUser:
    """Activa o desactiva una cuenta.

    Desactivar corta también las sesiones abiertas: ``obtener_admin_actual``
    revisa el estado en cada petición.
    """
    usuario = await _obtener(db, usuario_id)

    if not activo:
        await _proteger_ultimo_superadmin(db, usuario, autor, "desactivar")

    usuario.activo = activo
    usuario.actualizado_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(usuario)
    return usuario


async def eliminar(
    db: AsyncSession, usuario_id: uuid.UUID, *, autor: AdminUser
) -> str:
    """Borra un usuario y devuelve su nombre de usuario para la bitácora.

    El histórico no se pierde: los controles ESH guardan ``responsable`` y la
    bitácora guarda ``username`` desnormalizados, así que las filas siguen
    diciendo quién fue aunque el FK quede en NULL.
    """
    usuario = await _obtener(db, usuario_id)
    await _proteger_ultimo_superadmin(db, usuario, autor, "eliminar")

    username = usuario.username
    await db.delete(usuario)
    await db.commit()
    return username
