"""Comandos de administración del sistema.

Uso dentro del contenedor:

    docker-compose exec backend python -m app.cli create-admin --username admin

La contraseña se pide por stdin y nunca se acepta como argumento: en la
línea de comandos quedaría registrada en el historial del shell y en la
lista de procesos.
"""

import argparse
import asyncio
import csv
import getpass
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import DIRECTORIO_FORMATOS
from app.core.constants import LONGITUD_MINIMA_CONTRASENA, MODULOS_PERMISO
from app.core.security import hashear_contrasena
from app.db.session import SessionLocal, engine
from app.models.admin_user import AdminUser
from app.models.recepcion import EjemploPlantillaRecepcion, PlantillaRecepcion
from app.services import appsheet_rondines, espejo_formatos

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


async def exportar_formatos() -> None:
    """Vuelca a disco los ejemplos del clasificador que ya están en la base.

    El espejo se escribe al aprender, así que sin este comando la carpeta
    arranca vacía en una base que ya tiene formatos aprendidos —y en un
    servidor donde el volumen se creó después—.

    Es un comando y no una tarea de arranque a propósito: una tarea del
    `lifespan` correría en cada uno de los cuatro workers de uvicorn.
    """
    async with SessionLocal() as db:
        filas = (
            await db.execute(
                select(
                    PlantillaRecepcion.slug,
                    PlantillaRecepcion.nombre,
                    EjemploPlantillaRecepcion.imagen,
                    EjemploPlantillaRecepcion.tipo,
                    EjemploPlantillaRecepcion.texto_ocr,
                    EjemploPlantillaRecepcion.json_esperado,
                )
                .join(
                    EjemploPlantillaRecepcion,
                    EjemploPlantillaRecepcion.plantilla_id == PlantillaRecepcion.id,
                )
                .order_by(
                    PlantillaRecepcion.slug, EjemploPlantillaRecepcion.creado_at
                )
            )
        ).all()

    if not filas:
        print("No hay formatos aprendidos que exportar.")
        return

    for slug, nombre, imagen, tipo, texto, esperado in filas:
        espejo_formatos.guardar_ejemplo(
            slug=slug,
            nombre=nombre,
            imagen=imagen,
            tipo_mime=tipo,
            texto_ocr=texto,
            json_esperado=esperado,
        )
        # Un segundo entre ejemplos: la carpeta lleva el sello de tiempo con
        # resolución de segundo y dos del mismo formato se pisarían.
        await asyncio.sleep(1.05)

    print(f"{len(filas)} ejemplo(s) exportado(s) a {DIRECTORIO_FORMATOS}.")


# --- Ingesta de rondines desde AppSheet ------------------------------------


def _leer_csv(ruta: str) -> list[dict[str, Any]]:
    """Lee un CSV exportado de AppSheet.

    `utf-8-sig` y no `utf-8`: el export que baja de AppSheet no trae BOM, pero
    en cuanto alguien lo abre y lo vuelve a guardar con Excel sí, y sin el
    `-sig` la primera cabecera se vuelve `\ufeffID_Registro`. El resultado es
    que **cada fila pierde su primera columna en silencio**.
    """
    archivo = Path(ruta)
    if not archivo.is_file():
        print(f"No existe el archivo: {ruta}", file=sys.stderr)
        raise SystemExit(2)

    with archivo.open(encoding="utf-8-sig", newline="") as manejador:
        return list(csv.DictReader(manejador))


def _reportar(problemas: tuple[str, ...], *, tope: int = 10) -> None:
    """Enseña los primeros motivos de descarte, para poder corregir el CSV."""
    if not problemas:
        return
    print(f"\nRenglones no importados ({len(problemas)}):", file=sys.stderr)
    for motivo in problemas[:tope]:
        print(f"  - {motivo}", file=sys.stderr)
    if len(problemas) > tope:
        print(f"  ... y {len(problemas) - tope} más.", file=sys.stderr)


async def importar_puntos(ruta: str, desactivar_ausentes: bool) -> None:
    """Carga el catálogo desde el export de `Puntos_Referencia` de AppSheet.

    Idempotente: empareja por `ID_QR`, que es el `numero` del punto aquí.
    Correrlo dos veces no crea nada la segunda vez.
    """
    filas = _leer_csv(ruta)
    async with SessionLocal() as db:
        resultado = await appsheet_rondines.sincronizar_puntos(
            db, filas, desactivar_ausentes=desactivar_ausentes
        )

    print(
        f"{resultado.creados} punto(s) nuevo(s), "
        f"{resultado.actualizados} actualizado(s), "
        f"{resultado.retirados} retirado(s), "
        f"{resultado.descartados} descartado(s)."
    )
    _reportar(resultado.problemas)


def _en_lotes(filas: list[dict[str, Any]], tamano: int) -> Iterator[list[dict]]:
    """Trocea el histórico: son decenas de miles de renglones."""
    for inicio in range(0, len(filas), tamano):
        yield filas[inicio : inicio + tamano]


async def importar_escaneos(ruta: str, tamano_lote: int) -> None:
    """Carga el histórico desde el export de `Hoja 1` de AppSheet.

    Idempotente por el UNIQUE de `origen_id`: correrlo dos veces inserta cero.
    Por eso mismo sirve además para **reparar huecos**: si el túnel se cayó o
    AppSheet agotó los reintentos del Bot, se reexporta el rango y se vuelve a
    correr.

    Sin tope de antigüedad, al revés que el webhook: el histórico arranca en
    febrero y con el tope de 30 días se descartaría entero.
    """
    filas = _leer_csv(ruta)
    total = appsheet_rondines.ResultadoIngesta()
    problemas: list[str] = []

    async with SessionLocal() as db:
        # El catálogo se resuelve UNA vez y se reusa en todos los lotes: son
        # ~48 mil renglones y una consulta por fila sería inaceptable.
        catalogo = await appsheet_rondines.catalogo_de_puntos(db)
        if not catalogo:
            print(
                "El catálogo de puntos está vacío. Corre antes importar-puntos.",
                file=sys.stderr,
            )
            raise SystemExit(2)

        for lote in _en_lotes(filas, tamano_lote):
            parcial = await appsheet_rondines.registrar_lote(
                db,
                lote,
                origen=appsheet_rondines.ORIGEN_HISTORICO,
                antiguedad_maxima_dias=None,
                catalogo=catalogo,
            )
            problemas.extend(parcial.problemas)
            total = appsheet_rondines.ResultadoIngesta(
                recibidos=total.recibidos + parcial.recibidos,
                insertados=total.insertados + parcial.insertados,
                duplicados=total.duplicados + parcial.duplicados,
                descartados=total.descartados + parcial.descartados,
            )

    print(
        f"{total.recibidos} fila(s) leída(s); "
        f"{total.insertados} nueva(s), "
        f"{total.duplicados} ya estaban, "
        f"{total.descartados} descartada(s)."
    )
    _reportar(tuple(problemas))



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

    subcomandos.add_parser(
        "exportar-formatos",
        help="Vuelca a disco los formatos que el OCR ya tiene aprendidos.",
    )

    puntos = subcomandos.add_parser(
        "importar-puntos",
        help="Carga los puntos de rondín desde el CSV de AppSheet.",
    )
    puntos.add_argument(
        "--archivo", required=True, help="CSV exportado de `Puntos_Referencia`."
    )
    puntos.add_argument(
        "--desactivar-ausentes",
        action="store_true",
        help=(
            "Retira (activo = false) los puntos que no vengan en el archivo. "
            "Apagado por omisión: una exportación truncada retiraría la planta."
        ),
    )

    escaneos = subcomandos.add_parser(
        "importar-escaneos",
        help="Carga el histórico de escaneos desde el CSV de AppSheet.",
    )
    escaneos.add_argument(
        "--archivo", required=True, help="CSV exportado de `Hoja 1`."
    )
    escaneos.add_argument(
        "--tamano-lote", type=int, default=500, help="Filas por INSERT (default 500)."
    )

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
        elif args.comando == "exportar-formatos":
            await exportar_formatos()
        elif args.comando == "importar-puntos":
            await importar_puntos(args.archivo, args.desactivar_ausentes)
        elif args.comando == "importar-escaneos":
            await importar_escaneos(args.archivo, args.tamano_lote)
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
