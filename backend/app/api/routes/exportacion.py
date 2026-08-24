"""Descarga de reportes en Excel y PowerPoint.

Ambos formatos se generan en memoria (``BytesIO``) y se devuelven con
``StreamingResponse``: no se escriben archivos temporales en disco, que
habría que limpiar y que se acumularían en el servidor de planta.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import requiere
from app.api.routes.estadisticas import obtener_filtros
from app.db.session import get_db
from app.services import cuestionario_service, excel_export, pdf_export, pptx_export
from app.services.estadistica_service import Filtros
from app.services.exportacion_comun import (
    cabecera_descarga,
    nombre_archivo,
    periodo_texto,
    reunir_datos,
    slug,
)

router = APIRouter(
    tags=["exportacion"],
    dependencies=[Depends(requiere("cuestionarios"))],
)

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_PPTX = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


@router.get(
    "/cuestionarios/{cuestionario_id}/imprimir",
    summary="Descarga el cuestionario en PDF para contestarlo en papel",
)
async def imprimir_cuestionario(
    cuestionario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Versión imprimible, en blanco.

    Para quien no trae celular a su turno. **No marca la respuesta correcta**:
    la hoja se le entrega a quien va a contestar.
    """
    cuestionario = await cuestionario_service.obtener_cuestionario(db, cuestionario_id)
    flujo = pdf_export.generar_pdf_cuestionario(cuestionario)

    nombre = f"cuestionario_{slug(cuestionario.nombre)}.pdf"

    return StreamingResponse(
        flujo,
        media_type="application/pdf",
        headers=cabecera_descarga(nombre),
    )


@router.get(
    "/estadisticas/exportar/excel",
    summary="Descarga el reporte en Excel (4 hojas)",
)
async def exportar_excel(
    filtros: Filtros = Depends(obtener_filtros),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Resumen, respuestas detalladas, por área y por pregunta."""
    cuestionario = await cuestionario_service.obtener_cuestionario(
        db, filtros.cuestionario_id
    )
    datos = await reunir_datos(db, cuestionario, filtros)

    flujo = excel_export.generar_excel(datos, periodo_texto(filtros))

    return StreamingResponse(
        flujo,
        media_type=TIPO_EXCEL,
        headers=cabecera_descarga(nombre_archivo(cuestionario, "xlsx")),
    )


@router.get(
    "/estadisticas/exportar/powerpoint",
    summary="Descarga la presentación en PowerPoint (7 diapositivas)",
)
async def exportar_powerpoint(
    filtros: Filtros = Depends(obtener_filtros),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Presentación 16:9 con gráficas nativas, editables en PowerPoint."""
    cuestionario = await cuestionario_service.obtener_cuestionario(
        db, filtros.cuestionario_id
    )
    datos = await reunir_datos(db, cuestionario, filtros)

    flujo = pptx_export.generar_pptx(datos, periodo_texto(filtros))

    return StreamingResponse(
        flujo,
        media_type=TIPO_PPTX,
        headers=cabecera_descarga(nombre_archivo(cuestionario, "pptx")),
    )
