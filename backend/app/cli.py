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

from app.core.security import hashear_contrasena
from app.db.session import SessionLocal, engine
from app.models.admin_user import AdminUser

LONGITUD_MINIMA_CONTRASENA = 8


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


async def crear_admin(username: str, reestablecer: bool) -> None:
    """Crea el administrador o reestablece su contraseña."""
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
            await db.commit()
            print(f"Contraseña actualizada para el usuario '{username}'.")
            return

        db.add(
            AdminUser(username=username, password_hash=hashear_contrasena(contrasena))
        )
        await db.commit()
        print(f"Administrador '{username}' creado correctamente.")


async def listar_admins() -> None:
    """Muestra los administradores registrados y su último acceso."""
    async with SessionLocal() as db:
        admins = (
            await db.scalars(select(AdminUser).order_by(AdminUser.created_at))
        ).all()

    if not admins:
        print("No hay administradores registrados.")
        return

    print(f"{'Usuario':<20} {'Creado':<22} Último acceso")
    for admin in admins:
        ultimo = (
            admin.last_login_at.strftime("%Y-%m-%d %H:%M")
            if admin.last_login_at
            else "nunca"
        )
        print(f"{admin.username:<20} {admin.created_at:%Y-%m-%d %H:%M:%S}    {ultimo}")


def construir_parser() -> argparse.ArgumentParser:
    """Arma el parser de argumentos de la CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Herramientas de administración del sistema de evaluaciones.",
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    crear = subcomandos.add_parser(
        "create-admin", help="Crea un administrador o reestablece su contraseña."
    )
    crear.add_argument("--username", required=True, help="Nombre de usuario.")
    crear.add_argument(
        "--reestablecer",
        action="store_true",
        help="Si el usuario ya existe, cambia su contraseña en lugar de fallar.",
    )

    subcomandos.add_parser("listar-admins", help="Lista los administradores.")

    return parser


async def _ejecutar(args: argparse.Namespace) -> None:
    """Despacha el subcomando y cierra el pool al terminar."""
    try:
        if args.comando == "create-admin":
            await crear_admin(args.username, args.reestablecer)
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
