"""Descarga de reportes en Excel y PowerPoint.

Ambos formatos se generan en memoria (``BytesIO``) y se devuelven con
``StreamingResponse``: no se escriben archivos temporales en disco, que
habría que limpiar y que se acumularían en el servidor de planta.
"""

from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual
from app.api.routes.estadisticas import obtener_filtros
from app.db.session import get_db
from app.services import cuestionario_service, excel_export, pptx_export
from app.services.estadistica_service import Filtros
from app.services.exportacion_comun import (
    nombre_archivo,
    periodo_texto,
    reunir_datos,
)

router = APIRouter(
    tags=["exportacion"],
    dependencies=[Depends(obtener_admin_actual)],
)

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_PPTX = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def _cabecera_descarga(nombre: str) -> dict[str, str]:
    """Arma el Content-Disposition.

    El nombre ya viene sin acentos, pero se agrega la variante ``filename*``
    por si en el futuro incluye caracteres fuera de ASCII: sin ella, algunos
    navegadores truncan el nombre del archivo.
    """
    return {
        "Content-Disposition": (
            f'attachment; filename="{nombre}"; '
            f"filename*=UTF-8''{quote(nombre)}"
        )
    }


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
        headers=_cabecera_descarga(nombre_archivo(cuestionario, "xlsx")),
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
        headers=_cabecera_descarga(nombre_archivo(cuestionario, "pptx")),
    )
