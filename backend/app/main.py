"""Punto de entrada de la API del Sistema de Evaluación de Conocimientos."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    auth,
    cuestionarios,
    estadisticas,
    exportacion,
    publico,
    sistema,
)
from app.core.config import DIRECTORIO_ESTATICOS, settings
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.core.ratelimit import MiddlewareRateLimit
from app.db.session import engine

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

    yield

    logger.info("Cerrando conexiones a la base de datos")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="API interna para crear cuestionarios y evaluar al personal de planta.",
    version=sistema.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# Limita las peticiones a /api/publico/*. Se registra antes que CORS para que
# una IP bloqueada no consuma más trabajo del necesario.
app.add_middleware(MiddlewareRateLimit)

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


# Pydantic redacta sus mensajes en inglés. Se traducen por tipo de error
# para que ninguna respuesta de la API mezcle idiomas.
MENSAJES_VALIDACION: dict[str, str] = {
    "missing": "Este campo es obligatorio.",
    "string_too_short": "El texto es demasiado corto.",
    "string_too_long": "El texto es demasiado largo.",
    "string_type": "Se esperaba un texto.",
    "uuid_parsing": "El identificador no tiene un formato válido.",
    "int_parsing": "Se esperaba un número entero.",
    "int_type": "Se esperaba un número entero.",
    "float_parsing": "Se esperaba un número.",
    "bool_parsing": "Se esperaba un valor verdadero o falso.",
    "datetime_parsing": "La fecha no tiene un formato válido.",
    "greater_than_equal": "El valor es menor que el mínimo permitido.",
    "less_than_equal": "El valor es mayor que el máximo permitido.",
    "too_short": "Faltan elementos en la lista.",
    "too_long": "La lista tiene demasiados elementos.",
    "json_invalid": "El cuerpo de la petición no es JSON válido.",
    "value_error": "El valor no es válido.",
}


def _mensaje_de_error(error: dict) -> str:
    """Elige el texto en español para un error de validación de Pydantic.

    Los validadores propios ya lanzan su mensaje en español dentro de un
    ``ValueError``; ese texto es más específico que cualquier traducción
    genérica, así que se conserva. Pydantic lo entrega con el prefijo
    "Value error, ", que se recorta.
    """
    if error["type"] == "value_error":
        return str(error["msg"]).removeprefix("Value error, ")

    return MENSAJES_VALIDACION.get(error["type"], "El valor no es válido.")


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
                    "mensaje": _mensaje_de_error(error),
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
