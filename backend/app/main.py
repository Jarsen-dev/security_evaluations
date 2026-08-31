"""Punto de entrada de la API del Sistema ESH."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    administracion,
    auth,
    catalogo,
    controles,
    cuestionarios,
    estadisticas,
    estudios,
    exportacion,
    inventario,
    publico,
    rondines,
    sistema,
)
from app.core.bitacora import MiddlewareBitacora
from app.core.config import DIRECTORIO_ESTATICOS, settings
from app.core.errors import (
    ConflictoDeNegocio,
    ErrorDeNegocio,
    RecursoNoEncontrado,
    mensaje_de_validacion,
)
from app.core.ratelimit import MiddlewareRateLimit
from app.db.session import engine
from app.services import pci_automatico, reporte_automatico

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Avisos de arranque y cierre ordenado del pool de conexiones."""
    logger.info("Iniciando %s", settings.APP_NAME)

    if settings.base_url_es_local:
        logger.warning(
            "NEXT_PUBLIC_BASE_URL apunta a '%s': los códigos QR generados no "
            "se podrán abrir desde un celular. Configura la IP del servidor "
            "en la LAN (hostname -I).",
            settings.NEXT_PUBLIC_BASE_URL,
        )

    # Tareas periódicas. Todas corren en CADA worker de uvicorn, así que cada
    # una necesita su propio candado en la base para no duplicar su efecto:
    # `envios_reporte_rondin` en el reporte de rondines, y la restricción
    # `uq_pci_anio_mes` en el cierre de PCI MTTO.
    periodicas = (
        (reporte_automatico, "Reporte automático de rondines"),
        (pci_automatico, "Cierre automático de PCI MTTO"),
    )

    tareas: list[asyncio.Task[None]] = []
    for modulo, nombre in periodicas:
        arrancar, motivo = modulo.debe_arrancar()
        if arrancar:
            tareas.append(asyncio.create_task(modulo.ejecutar()))
        else:
            logger.info("%s apagado: %s", nombre, motivo)

    yield

    for tarea in tareas:
        tarea.cancel()

    for tarea in tareas:
        # Se espera a que terminen de verdad: sin esto, un bucle podría quedar
        # a medio ciclo con una sesión de base de datos abierta.
        with suppress(asyncio.CancelledError):
            await tarea

    logger.info("Cerrando conexiones a la base de datos")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "API interna del departamento de seguridad: evaluaciones de "
        "conocimientos y controles ESH."
    ),
    version=sistema.VERSION,
    lifespan=lifespan,
    # Solo en desarrollo: en producción el esquema completo de la API no se
    # publica (ver `docs_publicas` en core/config.py).
    docs_url="/api/docs" if settings.docs_publicas else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.docs_publicas else None,
)

# Limita el login y los endpoints públicos. Se registra antes que CORS para
# que una IP bloqueada no consuma más trabajo del necesario.
app.add_middleware(MiddlewareRateLimit)

# Escribe en `bitacora` lo que cambia datos y los inicios de sesión. Un 429
# del limitador no cae en ninguna de sus reglas de registro, así que el orden
# entre ambos no altera lo que se guarda.
app.add_middleware(MiddlewareBitacora)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # necesario para la cookie de sesión del admin
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Starlette genera estos mensajes en inglés antes de que el router entregue
# el control a la aplicación; se traducen aquí para que ninguna respuesta de
# la API salga en otro idioma.
MENSAJES_HTTP: dict[str, str] = {
    "Not Found": "El recurso solicitado no existe.",
    "Method Not Allowed": "El método HTTP no está permitido para este recurso.",
    "Internal Server Error": "Ocurrió un error interno en el servidor.",
    "Forbidden": "No tienes permiso para acceder a este recurso.",
    "Unauthorized": "No has iniciado sesión.",
}


@app.exception_handler(StarletteHTTPException)
async def manejar_error_http(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Devuelve los errores HTTP con el mensaje en español."""
    detalle = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": MENSAJES_HTTP.get(detalle, detalle)},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def manejar_error_validacion(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Traduce los errores de validación de Pydantic a mensajes en español."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Los datos enviados no son válidos.",
            "errores": [
                {
                    # loc[0] es el origen (body, path, query); se omite porque
                    # al usuario solo le sirve el nombre del campo.
                    "campo": ".".join(str(parte) for parte in error["loc"][1:]),
                    "mensaje": mensaje_de_validacion(error),
                }
                for error in exc.errors()
            ],
        },
    )


@app.exception_handler(ErrorDeNegocio)
async def manejar_error_negocio(
    request: Request, exc: ErrorDeNegocio
) -> JSONResponse:
    """Regla de negocio incumplida: 422 con el detalle de cada problema."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.mensaje, "errores": exc.errores},
    )


@app.exception_handler(RecursoNoEncontrado)
async def manejar_recurso_no_encontrado(
    request: Request, exc: RecursoNoEncontrado
) -> JSONResponse:
    """Recurso inexistente: 404."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.mensaje}
    )


@app.exception_handler(ConflictoDeNegocio)
async def manejar_conflicto(
    request: Request, exc: ConflictoDeNegocio
) -> JSONResponse:
    """Conflicto con el estado actual de los datos: 409."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": exc.mensaje}
    )


# Archivos estáticos (el logo). Va bajo /api porque Nginx enruta /api/* al
# backend; sin sesión, porque el formulario público también lo necesita.
if DIRECTORIO_ESTATICOS.is_dir():
    app.mount(
        "/api/static",
        StaticFiles(directory=DIRECTORIO_ESTATICOS),
        name="estaticos",
    )

app.include_router(sistema.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cuestionarios.router, prefix="/api")
app.include_router(publico.router, prefix="/api")
app.include_router(estadisticas.router, prefix="/api")
app.include_router(exportacion.router, prefix="/api")
app.include_router(controles.router, prefix="/api")
app.include_router(estudios.router, prefix="/api")
app.include_router(administracion.router, prefix="/api")
app.include_router(catalogo.router, prefix="/api")
app.include_router(rondines.router, prefix="/api")
app.include_router(inventario.router, prefix="/api")
