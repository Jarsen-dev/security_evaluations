"""Rondines de seguridad: tablero del turno y puntos de control.

Todo el router exige acceso al módulo ``rondines``; editar y eliminar puntos
piden además el permiso de edición.

El prefijo ``/api/rondines`` es nuevo, así que hay que darlo de alta como
aplicación de Cloudflare Access, igual que la ruta ``rondines`` del panel (ver
la regla 7 del CLAUDE.md y la lista de pendientes de SEGURIDAD.md).

Ojo con lo contrario: ``/p/*`` y ``/api/publico/rondin/*`` **no** deben
protegerse con Access, o los códigos QR dejan de funcionar.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response, status
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
    PuntoRondinActualizar,
    PuntoRondinCrear,
    PuntoRondinOut,
    TableroOut,
)
from app.services import (
    correo_service,
    rondin_service,
    rondines_excel,
    rondines_pdf,
)
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
# IMPORTANTE: /puntos/imprimir va declarada ANTES de /puntos/{punto_id}, o
# FastAPI intentaría leer "imprimir" como un UUID y devolvería 422.


@router.get(
    "/puntos/imprimir",
    summary="Hoja imprimible con los códigos QR de los puntos activos",
)
async def imprimir_qr(db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """PDF con una etiqueta por punto, para recortar y pegar en la planta."""
    puntos = await rondin_service.listar_puntos(db, solo_activos=True)
    if not puntos:
        raise ErrorDeNegocio("No hay puntos de control activos que imprimir.")

    flujo = rondines_pdf.generar_hoja_qr(puntos)
    return StreamingResponse(
        flujo,
        media_type="application/pdf",
        headers=cabecera_descarga("qr_puntos_rondin.pdf"),
    )


@router.get(
    "/puntos",
    response_model=list[PuntoRondinOut],
    summary="Lista los puntos de control",
)
async def listar_puntos(db: AsyncSession = Depends(get_db)) -> list[PuntoRondinOut]:
    """Todos los puntos, activos y retirados, ordenados por número."""
    puntos = await rondin_service.listar_puntos(db)
    return [PuntoRondinOut.model_validate(punto) for punto in puntos]


@router.post(
    "/puntos",
    response_model=PuntoRondinOut,
    status_code=status.HTTP_201_CREATED,
    summary="Da de alta un punto de control",
)
async def crear_punto(
    datos: PuntoRondinCrear,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PuntoRondinOut:
    """El código QR se genera aquí y ya no cambia."""
    punto = await rondin_service.crear_punto(
        db, numero=datos.numero, nombre=datos.nombre, ubicacion=datos.ubicacion
    )
    anotar(request, detalle=f"{punto.numero} — {punto.nombre}")
    return PuntoRondinOut.model_validate(punto)


@router.put(
    "/puntos/{punto_id}",
    dependencies=[Depends(requiere("rondines", editar=True))],
    response_model=PuntoRondinOut,
    summary="Actualiza un punto de control",
)
async def actualizar_punto(
    punto_id: uuid.UUID,
    datos: PuntoRondinActualizar,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PuntoRondinOut:
    """Desactivar un punto lo retira del tablero sin borrar su historia."""
    punto = await rondin_service.actualizar_punto(
        db,
        punto_id,
        numero=datos.numero,
        nombre=datos.nombre,
        ubicacion=datos.ubicacion,
        activo=datos.activo,
    )
    anotar(request, detalle=f"{punto.numero} — {punto.nombre}")
    return PuntoRondinOut.model_validate(punto)


@router.delete(
    "/puntos/{punto_id}",
    dependencies=[Depends(requiere("rondines", editar=True))],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un punto de control",
)
async def eliminar_punto(
    punto_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Casi siempre conviene desactivarlo en vez de borrarlo.

    Al borrar, los escaneos históricos quedan sin punto asociado; conservan su
    número, pero el tablero de los turnos pasados deja de contarlos.
    """
    etiqueta = await rondin_service.eliminar_punto(db, punto_id)
    anotar(request, detalle=etiqueta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
