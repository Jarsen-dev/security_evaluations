"""Registro automático de la actividad del panel.

Un middleware escribe una fila en ``bitacora`` por cada petición que cambia
datos, más los inicios y cierres de sesión. Se hace aquí, y no llamando a un
servicio desde cada endpoint, para que ninguna ruta nueva se quede sin
registrar por olvido.

Qué NO se registra, a propósito:

* Las lecturas (GET). Son la mayoría del tráfico y su ruido escondería
  justo lo que se quiere auditar: quién creó, cambió o borró algo.
* ``/api/publico`` completo. Lo contesta el personal de piso desde el
  celular, son cientos de peticiones por hora y ya dejan su propio rastro
  en ``intentos`` y ``respuestas``.
* Las respuestas de error, salvo el 401 del login: un intento fallido de
  acceso sí interesa, un 403 o un 422 solo dirían que alguien se equivocó.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Final

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.ratelimit import obtener_ip_cliente
from app.core.security import COOKIE_SESION, TokenInvalidoError, decodificar_token
from app.db.session import SessionLocal
from app.models.bitacora import Bitacora

logger = logging.getLogger(__name__)

#: Clave de ``request.state`` donde un endpoint puede enriquecer su registro.
CLAVE_ESTADO: Final[str] = "bitacora"

METODOS_REGISTRADOS: Final[frozenset[str]] = frozenset(
    {"POST", "PUT", "PATCH", "DELETE"}
)

RUTA_LOGIN: Final[str] = "/api/auth/login"
PREFIJO_EXCLUIDO: Final[str] = "/api/publico"

LONGITUD_MAXIMA_DESCRIPCION: Final[int] = 300


def anotar(request: Request, *, detalle: str | None = None, **extra: object) -> None:
    """Enriquece desde un endpoint la fila que escribirá el middleware.

    ``detalle`` se anexa a la descripción del catálogo para que la bitácora
    diga *qué* se tocó ("Creó un cuestionario: Bloqueo LOTO") y no solo la
    acción. Se usa donde el dato ya está a la mano en la ruta; donde no,
    queda la descripción genérica y el identificador vive en la columna
    ``ruta``.

    El login además pasa por aquí el usuario, porque todavía no hay cookie
    de la que deducirlo.
    """
    actual = getattr(request.state, CLAVE_ESTADO, None)
    datos: dict[str, object] = actual if isinstance(actual, dict) else {}
    if detalle is not None:
        datos["detalle"] = detalle
    datos.update(extra)
    setattr(request.state, CLAVE_ESTADO, datos)


@dataclass(frozen=True)
class EntradaCatalogo:
    """Cómo se nombra en la bitácora una ruta de la API."""

    metodo: str
    patron: re.Pattern[str]
    accion: str
    modulo: str
    descripcion: str


def _ruta(expresion: str) -> re.Pattern[str]:
    """Compila el patrón de una ruta; ``{}`` representa un identificador."""
    return re.compile(expresion.replace("{}", r"[^/]+") + "/?")


# El orden importa: se toma la primera coincidencia, así que las rutas más
# específicas van antes que las que podrían tragárselas.
CATALOGO: Final[tuple[EntradaCatalogo, ...]] = (
    # --- Sesión ------------------------------------------------------------
    EntradaCatalogo(
        "POST", _ruta("/api/auth/login"), "sesion.iniciar", "sesion", "Inició sesión"
    ),
    EntradaCatalogo(
        "POST", _ruta("/api/auth/logout"), "sesion.cerrar", "sesion", "Cerró sesión"
    ),
    # --- Cuestionarios -----------------------------------------------------
    EntradaCatalogo(
        "POST",
        _ruta("/api/cuestionarios/importar-excel"),
        "cuestionario.importar",
        "cuestionarios",
        "Importó un cuestionario desde Excel",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/cuestionarios/{}/duplicar"),
        "cuestionario.duplicar",
        "cuestionarios",
        "Duplicó un cuestionario",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/cuestionarios/{}/preguntas/orden"),
        "pregunta.reordenar",
        "cuestionarios",
        "Reordenó las preguntas de un cuestionario",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/cuestionarios/{}/preguntas"),
        "pregunta.crear",
        "cuestionarios",
        "Agregó una pregunta",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/cuestionarios"),
        "cuestionario.crear",
        "cuestionarios",
        "Creó un cuestionario",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/cuestionarios/{}"),
        "cuestionario.editar",
        "cuestionarios",
        "Editó un cuestionario",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/cuestionarios/{}"),
        "cuestionario.eliminar",
        "cuestionarios",
        "Eliminó un cuestionario",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/preguntas/{}"),
        "pregunta.editar",
        "cuestionarios",
        "Editó una pregunta",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/preguntas/{}"),
        "pregunta.eliminar",
        "cuestionarios",
        "Eliminó una pregunta",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/metas-area"),
        "meta.guardar",
        "cuestionarios",
        "Actualizó las metas por área",
    ),
    # --- Controles ESH -----------------------------------------------------
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/rayser"),
        "rayser.registrar",
        "controles",
        "Registró la lectura de manómetros de Rayser",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/controles/rayser/{}"),
        "rayser.eliminar",
        "controles",
        "Eliminó un registro de Rayser",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/sqp"),
        "sqp.registrar",
        "controles",
        "Registró una inspección de sustancias químicas peligrosas",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/checklist/{}"),
        "checklist.registrar",
        "controles",
        "Llenó una hoja de lista de verificación",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/controles/checklist/{}/{}"),
        "checklist.eliminar",
        "controles",
        "Eliminó una hoja de lista de verificación",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/cierres/{}/{}"),
        "cierre.registrar",
        "controles",
        "Registró el cierre de los hallazgos de un control",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/controles/cierres/{}/{}"),
        "cierre.actualizar",
        "controles",
        "Actualizó el cierre de los hallazgos de un control",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/platicas"),
        "platica.registrar",
        "controles",
        "Registró una plática de seguridad",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/controles/platicas/{}"),
        "platica.eliminar",
        "controles",
        "Eliminó una plática de seguridad",
    ),
    # PCI MTTO. El cierre automático de un mes sin respuesta NO deja renglón
    # aquí: no pasa por HTTP y este middleware es la única vía. Su rastro queda
    # en la propia fila (`automatico = true`, `responsable = 'sistema'`).
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/pci-mtto"),
        "pci.registrar",
        "controles",
        "Registró el mantenimiento del sistema contra incendios",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/pci-mtto/{}/{}/motivo"),
        "pci.motivo",
        "controles",
        "Capturó el motivo de un mes sin mantenimiento contra incendios",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/controles/pci-mtto/{}/{}/motivo"),
        "pci.motivo_actualizar",
        "controles",
        "Corrigió el motivo de un mes sin mantenimiento contra incendios",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/controles/pci-mtto/{}/{}"),
        "pci.corregir",
        "controles",
        "Corrigió el registro de mantenimiento contra incendios",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/insumos"),
        "control_insumos.registrar",
        "controles",
        "Registró la salida de un insumo del almacén",
    ),
    # Las más específicas antes: `/extintores/{}` se tragaría `/etiquetas` y
    # `/{}/revision` si fueran después.
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/extintores/etiquetas"),
        "extintores.etiquetas",
        "controles",
        "Imprimió etiquetas QR de extintores",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/extintores/{}/revision"),
        "extintores.revisar",
        "controles",
        "Registró la revisión diaria de un extintor",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/controles/extintores/{}/revision"),
        "extintores.corregir_revision",
        "controles",
        "Corrigió la revisión diaria de un extintor",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/controles/extintores"),
        "extintores.registrar",
        "controles",
        "Dio de alta un extintor",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/controles/extintores/{}"),
        "extintores.actualizar",
        "controles",
        "Corrigió la ficha de un extintor",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/controles/extintores/{}"),
        "extintores.eliminar",
        "controles",
        "Eliminó la ficha de un extintor",
    ),
    # --- Estudios y capacitaciones -----------------------------------------
    EntradaCatalogo(
        "POST",
        _ruta("/api/estudios"),
        "estudio.crear",
        "estudios",
        "Dio de alta un estudio",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/estudios/{}"),
        "estudio.editar",
        "estudios",
        "Actualizó un estudio",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/estudios/{}"),
        "estudio.eliminar",
        "estudios",
        "Eliminó un estudio",
    ),
    # --- Catálogo de insumos -----------------------------------------------
    # La de importar va ANTES del POST a secas, o el patrón general se la
    # tragaría: `_buscar_en_catalogo` toma la primera coincidencia.
    EntradaCatalogo(
        "POST",
        _ruta("/api/catalogo/importar-excel"),
        "insumo.importar",
        "catalogo",
        "Importó insumos desde Excel",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/catalogo"),
        "insumo.crear",
        "catalogo",
        "Dio de alta un insumo",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/catalogo/{}"),
        "insumo.editar",
        "catalogo",
        "Editó un insumo",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/catalogo/{}"),
        "insumo.eliminar",
        "catalogo",
        "Eliminó un insumo",
    ),
    # --- Rondines de seguridad ---------------------------------------------
    # La INGESTA no se registra: el webhook de AppSheet cae bajo /api/publico,
    # excluido a propósito, y cada escaneo ya deja su propio rastro en
    # `escaneos_rondin` con su `origen_id` y su `recibido_at`.
    # Los puntos tampoco aparecen: el catálogo es de solo lectura y se refresca
    # con `python -m app.cli importar-puntos`, que no pasa por HTTP.
    EntradaCatalogo(
        "POST",
        _ruta("/api/rondines/reporte/enviar"),
        "rondin.reporte",
        "rondines",
        "Envió el reporte de rondines por correo",
    ),
    # --- Recepciones de mercancía ------------------------------------------
    # Las rutas específicas van ANTES del POST a secas, o el patrón general se
    # las tragaría: `_buscar_en_catalogo` toma la primera coincidencia.
    #
    # La subida desde el CELULAR no se registra: cae bajo /api/publico, que
    # está excluido a propósito, y ya deja rastro en la sesión y en la foto.
    EntradaCatalogo(
        "POST",
        _ruta("/api/inventario/recepciones/ocr/desde-sesion/{}"),
        "recepcion.ocr",
        "inventario",
        "Procesó con IA una foto tomada desde el celular",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/inventario/recepciones/ocr"),
        "recepcion.ocr",
        "inventario",
        "Procesó con IA la foto de una remisión",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/inventario/recepciones/qr-session"),
        "recepcion.sesion",
        "inventario",
        "Abrió una sesión de captura por QR",
    ),
    EntradaCatalogo(
        "POST",
        _ruta("/api/inventario/recepciones"),
        "recepcion.crear",
        "inventario",
        "Registró una recepción y dio entrada al inventario",
    ),
    # --- Administración ----------------------------------------------------
    EntradaCatalogo(
        "POST",
        _ruta("/api/administracion/usuarios"),
        "usuario.crear",
        "administracion",
        "Creó un usuario",
    ),
    EntradaCatalogo(
        "PATCH",
        _ruta("/api/administracion/usuarios/{}/activo"),
        "usuario.estado",
        "administracion",
        "Cambió el estado de un usuario",
    ),
    EntradaCatalogo(
        "PUT",
        _ruta("/api/administracion/usuarios/{}"),
        "usuario.editar",
        "administracion",
        "Editó un usuario",
    ),
    EntradaCatalogo(
        "DELETE",
        _ruta("/api/administracion/usuarios/{}"),
        "usuario.eliminar",
        "administracion",
        "Eliminó un usuario",
    ),
)


def _buscar_en_catalogo(metodo: str, ruta: str) -> EntradaCatalogo | None:
    """Primera entrada del catálogo que describe esta petición."""
    for entrada in CATALOGO:
        if entrada.metodo == metodo and entrada.patron.fullmatch(ruta):
            return entrada
    return None


def _usuario_de_la_cookie(request: Request) -> tuple[uuid.UUID | None, str]:
    """Deduce quién hace la petición sin volver a consultar la base.

    El JWT ya viene firmado y validado por la dependencia de la ruta; aquí
    solo se relee para obtener el identificador y el nombre. Si el token es
    inválido, la petición ya habrá fallado y no llegará a registrarse.
    """
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        return None, ""

    try:
        payload = decodificar_token(token)
    except TokenInvalidoError:
        return None, ""

    username = str(payload.get("username") or "")
    sub = payload.get("sub")
    try:
        return (uuid.UUID(str(sub)) if sub else None), username
    except ValueError:
        return None, username


class MiddlewareBitacora(BaseHTTPMiddleware):
    """Escribe en ``bitacora`` después de responder."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        respuesta = await call_next(request)

        try:
            await self._registrar(request, respuesta)
        except Exception:  # noqa: BLE001
            # Deliberado, y la única excepción a la regla de no tragarse
            # errores: la operación del usuario YA se completó y ya se le
            # respondió. Perder el renglón de bitácora es malo; deshacer un
            # cuestionario recién guardado por un fallo al auditarlo lo es
            # mucho más. Queda en los logs del contenedor para revisarlo.
            logger.exception("No se pudo registrar la actividad en la bitácora")

        return respuesta

    def _debe_registrar(self, request: Request, respuesta: Response) -> bool:
        """Filtra qué peticiones merecen un renglón."""
        ruta = request.url.path

        if request.method not in METODOS_REGISTRADOS:
            return False
        if not ruta.startswith("/api/") or ruta.startswith(PREFIJO_EXCLUIDO):
            return False

        if 200 <= respuesta.status_code < 300:
            return True

        # El login fallido es el único error que interesa auditar.
        return respuesta.status_code == 401 and ruta.rstrip("/") == RUTA_LOGIN

    async def _registrar(self, request: Request, respuesta: Response) -> None:
        """Arma la fila y la guarda con su propia sesión."""
        if not self._debe_registrar(request, respuesta):
            return

        ruta = request.url.path
        entrada = _buscar_en_catalogo(request.method, ruta)
        anotado = getattr(request.state, CLAVE_ESTADO, None)
        anotado = anotado if isinstance(anotado, dict) else {}

        usuario_id, username = _usuario_de_la_cookie(request)
        # El login todavía no tiene cookie: la ruta deja ahí el usuario.
        # `request.state` vive en el `scope`, que el endpoint y este
        # middleware comparten.
        usuario_id = anotado.get("usuario_id", usuario_id)  # type: ignore[assignment]
        username = str(anotado.get("username") or username or "desconocido")

        fallo_de_acceso = respuesta.status_code == 401
        if entrada is None:
            accion, modulo = "otro", "sistema"
            descripcion = f"{request.method} {ruta}"
        elif fallo_de_acceso:
            accion, modulo = "sesion.fallida", entrada.modulo
            descripcion = "Intento de acceso fallido"
        else:
            accion, modulo = entrada.accion, entrada.modulo
            descripcion = entrada.descripcion

        detalle = anotado.get("detalle")
        if detalle:
            descripcion = f"{descripcion}: {detalle}"

        async with SessionLocal() as db:
            db.add(
                Bitacora(
                    usuario_id=usuario_id,
                    username=username[:50],
                    accion=accion,
                    modulo=modulo,
                    descripcion=descripcion[:LONGITUD_MAXIMA_DESCRIPCION],
                    metodo=request.method,
                    ruta=ruta[:255],
                    estado=respuesta.status_code,
                    ip=obtener_ip_cliente(request)[:45],
                )
            )
            await db.commit()
