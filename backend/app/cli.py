"""Comandos de administración del sistema.

Uso dentro del contenedor:

    docker-compose exec backend python -m app.cli create-admin --username admin

La contraseña se pide por stdin y nunca se acepta como argumento: en la
línea de comandos quedaría registrada en el historial del shell y en la
lista de procesos.
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.constants import LONGITUD_MINIMA_CONTRASENA, MODULOS_PERMISO
from app.core.security import hashear_contrasena
from app.db.session import SessionLocal, engine
from app.models.admin_user import AdminUser

# El usuario creado por la CLI es superadministrador con acceso completo: es
# la vía de rescate cuando no queda nadie que pueda entrar al panel. Los
# usuarios normales se dan de alta desde la pestaña de Administración.
PERMISOS_COMPLETOS = {modulo: {"editar": True} for modulo in MODULOS_PERMISO}


def _pedir_contrasena() -> str:
    """Solicita la contraseña dos veces y valida su longitud."""
    contrasena = getpass.getpass("Contraseña: ")

    if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        print(
            f"Error: la contraseña debe tener al menos "
            f"{LONGITUD_MINIMA_CONTRASENA} caracteres.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    confirmacion = getpass.getpass("Confirmar contraseña: ")
    if contrasena != confirmacion:
        print("Error: las contraseñas no coinciden.", file=sys.stderr)
        raise SystemExit(1)

    return contrasena


async def crear_admin(
    username: str,
    reestablecer: bool,
    nombre: str | None = None,
    email: str | None = None,
) -> None:
    """Crea el superadministrador o reestablece su contraseña."""
    async with SessionLocal() as db:
        existente = await db.scalar(
            select(AdminUser).where(AdminUser.username == username)
        )

        if existente is not None and not reestablecer:
            print(
                f"Error: el usuario '{username}' ya existe. "
                f"Usa --reestablecer para cambiarle la contraseña.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        contrasena = _pedir_contrasena()

        if existente is not None:
            existente.password_hash = hashear_contrasena(contrasena)
            # Reestablecer la contraseña también reabre la cuenta: si se usa
            # es porque alguien se quedó fuera, y devolverle la contraseña
            # sin reactivarlo lo dejaría igual de bloqueado.
            existente.activo = True
            existente.es_superadmin = True
            await db.commit()
            print(f"Contraseña actualizada para el usuario '{username}'.")
            return

        db.add(
            AdminUser(
                nombre=nombre or username,
                username=username,
                email=email,
                password_hash=hashear_contrasena(contrasena),
                activo=True,
                es_superadmin=True,
                permisos=PERMISOS_COMPLETOS,
            )
        )
        await db.commit()
        print(f"Superadministrador '{username}' creado correctamente.")


async def listar_admins() -> None:
    """Muestra los administradores registrados y su último acceso."""
    async with SessionLocal() as db:
        admins = (
            await db.scalars(select(AdminUser).order_by(AdminUser.created_at))
        ).all()

    if not admins:
        print("No hay administradores registrados.")
        return

    print(f"{'Usuario':<20} {'Rol':<16} {'Estado':<12} Último acceso")
    for admin in admins:
        ultimo = (
            admin.last_login_at.strftime("%Y-%m-%d %H:%M")
            if admin.last_login_at
            else "nunca"
        )
        rol = "superadmin" if admin.es_superadmin else "usuario"
        estado = "activo" if admin.activo else "desactivado"
        print(f"{admin.username:<20} {rol:<16} {estado:<12} {ultimo}")


def construir_parser() -> argparse.ArgumentParser:
    """Arma el parser de argumentos de la CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Herramientas de administración del sistema de evaluaciones.",
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    crear = subcomandos.add_parser(
        "create-admin",
        help="Crea un superadministrador o reestablece su contraseña.",
    )
    crear.add_argument("--username", required=True, help="Nombre de usuario.")
    crear.add_argument("--nombre", help="Nombre completo (default: el usuario).")
    crear.add_argument("--email", help="Correo electrónico (opcional).")
    crear.add_argument(
        "--reestablecer",
        action="store_true",
        help="Si el usuario ya existe, cambia su contraseña en lugar de fallar.",
    )

    subcomandos.add_parser("listar-admins", help="Lista los usuarios del panel.")

    return parser


async def _ejecutar(args: argparse.Namespace) -> None:
    """Despacha el subcomando y cierra el pool al terminar."""
    try:
        if args.comando == "create-admin":
            await crear_admin(
                args.username, args.reestablecer, args.nombre, args.email
            )
        elif args.comando == "listar-admins":
            await listar_admins()
    finally:
        await engine.dispose()


def main() -> None:
    """Punto de entrada de la CLI."""
    args = construir_parser().parse_args()
    try:
        asyncio.run(_ejecutar(args))
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
