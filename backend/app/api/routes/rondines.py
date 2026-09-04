"""Rondines de seguridad: tablero del turno y puntos de control.

Todo el router exige acceso al módulo ``rondines``; enviar el reporte pide
además el permiso de edición.

El catálogo de puntos es de **solo lectura**: la captura la hace una app de
AppSheet y los puntos se cargan con ``python -m app.cli importar-puntos``.
Por eso aquí no hay alta, edición ni borrado.

El prefijo ``/api/rondines`` es nuevo, así que hay que darlo de alta como
aplicación de Cloudflare Access, igual que la ruta ``rondines`` del panel (ver
la regla 7 del CLAUDE.md y la lista de pendientes de SEGURIDAD.md).

Ojo con lo contrario: ``/api/publico/rondin/escaneos`` —el webhook por donde
entra AppSheet— **no** debe protegerse con Access, o la ingesta se corta.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import requiere
from app.core.bitacora import anotar
from app.core.errors import ErrorDeNegocio
from app.db.session import get_db
from app.schemas.rondin import (
    EnvioReporteIn,
    FilaTableroOut,
    MensajeRondin,
    PuntoRondinOut,
    TableroOut,
)
from app.services import correo_service, rondin_service, rondines_excel
from app.services.exportacion_comun import cabecera_descarga

router = APIRouter(
    prefix="/rondines",
    tags=["rondines"],
    dependencies=[Depends(requiere("rondines"))],
)

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _validar_turno(turno: str) -> str:
    """Rechaza cualquier cosa que no sea un turno conocido."""
    if turno not in rondin_service.TURNOS_VALIDOS:
        raise ErrorDeNegocio("El turno debe ser 'dia' o 'noche'.")
    return turno


def _a_salida(tablero: dict) -> TableroOut:
    """Traduce el diccionario del servicio al schema de respuesta."""
    return TableroOut(
        **{clave: tablero[clave] for clave in tablero if clave != "filas"},
        filas=[
            FilaTableroOut(
                numero=fila.numero,
                nombre=fila.nombre,
                ubicacion=fila.ubicacion,
                rondines=fila.rondines,
                visitados=fila.visitados,
            )
            for fila in tablero["filas"]
        ],
    )


# --- Tablero ---------------------------------------------------------------


@router.get(
    "/tablero",
    response_model=TableroOut,
    summary="Matriz de puntos por rondín de un turno",
)
async def obtener_tablero(
    fecha: date = Query(description="Día en que INICIA el turno."),
    turno: str = Query(default=rondin_service.TURNO_DIA),
    db: AsyncSession = Depends(get_db),
) -> TableroOut:
    """El día que se pide es el de inicio del turno, no el del calendario.

    La noche del 25 al 26 se consulta pidiendo el 25 con turno ``noche``.
    """
    return _a_salida(
        await rondin_service.construir_tablero(db, fecha, _validar_turno(turno))
    )


@router.get(
    "/exportar/excel",
    summary="Excel del tablero de un turno",
)
async def exportar_excel(
    fecha: date = Query(),
    turno: str = Query(default=rondin_service.TURNO_DIA),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """La misma matriz, con el semáforo de los controles ESH."""
    turno = _validar_turno(turno)
    tablero = await rondin_service.construir_tablero(db, fecha, turno)
    flujo = rondines_excel.generar_excel(tablero)

    return StreamingResponse(
        flujo,
        media_type=TIPO_EXCEL,
        headers=cabecera_descarga(rondines_excel.nombre_reporte(fecha, turno)),
    )


@router.post(
    "/reporte/enviar",
    dependencies=[Depends(requiere("rondines", editar=True))],
    response_model=MensajeRondin,
    summary="Envía el reporte de un turno por correo",
)
async def enviar_reporte(
    datos: EnvioReporteIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MensajeRondin:
    """Manda el Excel del turno al correo indicado."""
    turno = _validar_turno(datos.turno)
    await correo_service.enviar_reporte_rondines(
        db, datos.fecha, turno, destinatarios=[datos.destinatario]
    )
    anotar(request, detalle=f"{datos.fecha:%Y-%m-%d} {turno} → {datos.destinatario}")

    return MensajeRondin(mensaje="Reporte enviado correctamente.")


# --- Puntos de control -----------------------------------------------------
# Solo lectura: el catálogo lo manda AppSheet y se refresca con
# `python -m app.cli importar-puntos`.


@router.get(
    "/puntos",
    response_model=list[PuntoRondinOut],
    summary="Lista los puntos de control",
)
async def listar_puntos(db: AsyncSession = Depends(get_db)) -> list[PuntoRondinOut]:
    """Todos los puntos, activos y retirados, ordenados por número."""
    puntos = await rondin_service.listar_puntos(db)
    return [PuntoRondinOut.model_validate(punto) for punto in puntos]
