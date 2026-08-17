"""Endpoints del dashboard de estadísticas. Requieren sesión de administrador."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual
from app.db.session import get_db
from app.schemas.estadistica import (
    DetalleIntento,
    EstadisticaArea,
    EstadisticaPregunta,
    IntentosPaginados,
    MetaAreaOut,
    MetasAreaIn,
    PuntoLineaTiempo,
    RangoDistribucion,
    ResumenOut,
)
from app.services import estadistica_service
from app.services.estadistica_service import Filtros

router = APIRouter(
    tags=["estadisticas"],
    dependencies=[Depends(obtener_admin_actual)],
)


def obtener_filtros(
    cuestionario_id: uuid.UUID = Query(description="Cuestionario a analizar."),
    area: str | None = Query(default=None, description="Filtra por área."),
    desde: date | None = Query(default=None, description="Fecha inicial inclusiva."),
    hasta: date | None = Query(default=None, description="Fecha final inclusiva."),
) -> Filtros:
    """Dependencia con los filtros comunes de todos los endpoints."""
    return Filtros(cuestionario_id=cuestionario_id, area=area, desde=desde, hasta=hasta)


@router.get(
    "/estadisticas/resumen",
    response_model=ResumenOut,
    summary="KPIs generales",
)
async def resumen(
    filtros: Filtros = Depends(obtener_filtros), db: AsyncSession = Depends(get_db)
) -> ResumenOut:
    """Total de respuestas, participación, promedio y tasa de aprobación."""
    return ResumenOut.model_validate(await estadistica_service.resumen(db, filtros))


@router.get(
    "/estadisticas/por-area",
    response_model=list[EstadisticaArea],
    summary="Participación y calificación promedio por área",
)
async def por_area(
    filtros: Filtros = Depends(obtener_filtros), db: AsyncSession = Depends(get_db)
) -> list[EstadisticaArea]:
    """Incluye las áreas sin respuestas: son las que interesa detectar."""
    filas = await estadistica_service.por_area(db, filtros)
    return [EstadisticaArea.model_validate(fila) for fila in filas]


@router.get(
    "/estadisticas/por-pregunta",
    response_model=list[EstadisticaPregunta],
    summary="Índice de acierto y error por pregunta",
)
async def por_pregunta(
    filtros: Filtros = Depends(obtener_filtros), db: AsyncSession = Depends(get_db)
) -> list[EstadisticaPregunta]:
    """Alimenta la gráfica más accionable del dashboard."""
    filas = await estadistica_service.por_pregunta(db, filtros)
    return [EstadisticaPregunta.model_validate(fila) for fila in filas]


@router.get(
    "/estadisticas/distribucion",
    response_model=list[RangoDistribucion],
    summary="Histograma de calificaciones por rangos",
)
async def distribucion(
    filtros: Filtros = Depends(obtener_filtros), db: AsyncSession = Depends(get_db)
) -> list[RangoDistribucion]:
    """Rangos 0-59, 60-69, 70-79, 80-89 y 90-100."""
    filas = await estadistica_service.distribucion(db, filtros)
    return [RangoDistribucion.model_validate(fila) for fila in filas]


@router.get(
    "/estadisticas/linea-tiempo",
    response_model=list[PuntoLineaTiempo],
    summary="Respuestas por día",
)
async def linea_tiempo(
    filtros: Filtros = Depends(obtener_filtros), db: AsyncSession = Depends(get_db)
) -> list[PuntoLineaTiempo]:
    """Serie diaria con el promedio de cada día."""
    filas = await estadistica_service.linea_tiempo(db, filtros)
    return [PuntoLineaTiempo.model_validate(fila) for fila in filas]


@router.get(
    "/estadisticas/intentos",
    response_model=IntentosPaginados,
    summary="Tabla paginada de intentos",
)
async def listar_intentos(
    filtros: Filtros = Depends(obtener_filtros),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=200),
    orden_por: str = Query(default="finalizado_at"),
    descendente: bool = Query(default=True),
    busqueda: str | None = Query(
        default=None,
        max_length=100,
        description="Texto a buscar en el nombre o el número de empleado.",
    ),
    db: AsyncSession = Depends(get_db),
) -> IntentosPaginados:
    """Ordenable por nombre, número de empleado, área, fecha o puntaje."""
    datos = await estadistica_service.listar_intentos(
        db,
        filtros,
        page=page,
        size=size,
        orden_por=orden_por,
        descendente=descendente,
        busqueda=busqueda,
    )
    return IntentosPaginados.model_validate(datos)


@router.get(
    "/estadisticas/intentos/{intento_id}",
    response_model=DetalleIntento,
    summary="Respuestas de un intento, con aciertos y errores",
)
async def detalle_intento(
    intento_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> DetalleIntento:
    """Lo que contestó una persona, pregunta por pregunta."""
    datos = await estadistica_service.detalle_intento(db, intento_id)
    return DetalleIntento.model_validate(datos)


# --- Metas por área --------------------------------------------------------


@router.get(
    "/metas-area",
    response_model=list[MetaAreaOut],
    summary="Headcount configurado por área",
)
async def listar_metas(db: AsyncSession = Depends(get_db)) -> list[MetaAreaOut]:
    """Devuelve el catálogo completo; `headcount` es None si no se capturó."""
    filas = await estadistica_service.listar_metas(db)
    return [MetaAreaOut.model_validate(fila) for fila in filas]


@router.put(
    "/metas-area",
    response_model=list[MetaAreaOut],
    summary="Guarda las metas en lote",
)
async def guardar_metas(
    datos: MetasAreaIn, db: AsyncSession = Depends(get_db)
) -> list[MetaAreaOut]:
    """Sin metas capturadas, el KPI de participación no tiene denominador."""
    filas = await estadistica_service.guardar_metas(
        db, [(meta.area, meta.headcount) for meta in datos.metas]
    )
    return [MetaAreaOut.model_validate(fila) for fila in filas]
