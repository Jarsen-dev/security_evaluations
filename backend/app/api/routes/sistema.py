"""Endpoints de sistema: salud del servicio y catálogo de áreas."""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual
from app.core.config import settings
from app.core.constants import AREAS
from app.db.session import get_db
from app.schemas.sistema import AreaOut, ConfigWifi, EstadoSalud

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sistema"])

VERSION = "0.1.0"


@router.get(
    "/health",
    response_model=EstadoSalud,
    summary="Estado del servicio y de la base de datos",
)
async def health(db: AsyncSession = Depends(get_db)) -> EstadoSalud | JSONResponse:
    """Verifica que la API responde y que la conexión async a Postgres funciona.

    Ejecuta un ``SELECT 1`` real: un 200 estático no distinguiría entre una
    base de datos sana y una caída.
    """
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("Fallo de conexión con la base de datos: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degradado",
                "db": "error",
                "version": VERSION,
                "detail": "No se pudo conectar con la base de datos.",
            },
        )

    return EstadoSalud(status="ok", db="ok", version=VERSION)


@router.get(
    "/areas",
    response_model=list[AreaOut],
    summary="Catálogo de áreas de la planta",
)
async def listar_areas() -> list[AreaOut]:
    """Devuelve las áreas definidas en ``app.core.constants``.

    El frontend siempre las consume desde aquí para que exista un solo lugar
    donde agregarlas o renombrarlas.
    """
    return [AreaOut(value=area.value, label=area.label) for area in AREAS]


@router.get(
    "/wifi",
    response_model=ConfigWifi,
    summary="Datos de la red WiFi para el código QR de acceso",
    dependencies=[Depends(obtener_admin_actual)],
)
async def config_wifi() -> ConfigWifi:
    """Devuelve la red configurada en el .env.

    Exige sesión de administrador: la respuesta trae la contraseña de la red
    en claro. El resto de este router es público, por eso la dependencia va
    en la ruta y no en el router completo.
    """
    return ConfigWifi(
        configurado=settings.wifi_configurado,
        ssid=settings.WIFI_SSID,
        password=settings.WIFI_PASSWORD,
        seguridad=settings.WIFI_SEGURIDAD,
        oculta=settings.WIFI_OCULTA,
    )
