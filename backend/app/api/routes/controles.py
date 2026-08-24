"""Controles ESH: presiones del Rayser e inspección de SQP.

Todo el router exige sesión de administrador. El prefijo ``/api/controles`` es
nuevo, así que hay que darlo de alta como aplicación de Cloudflare Access
(ver la regla 7 del CLAUDE.md y la nota en SEGURIDAD.md): mientras eso no
ocurra, lo único que lo defiende es la cookie de sesión.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual
from app.core.constants import AREAS_VALIDAS, etiqueta_area
from app.core.controles_catalogo import (
    PUNTOS_SQP,
    fuera_de_rango,
    RAYSER_MANOMETROS,
    RAYSER_MAXIMO,
    RAYSER_MINIMO,
    RAYSER_NORMAL,
    RENGLONES_SUSTANCIAS,
    SECCIONES_SQP,
)
from app.core.errors import ErrorDeNegocio
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.models.control import InspeccionSqp
from app.schemas.control import (
    CatalogoSqp,
    InspeccionSqpCrear,
    InspeccionSqpDetalle,
    InspeccionSqpResumen,
    PuntoSqpOut,
    RespuestaSqpOut,
    RangoRayser,
    RegistroRayserOut,
)
from app.services import control_service, controles_excel
from app.services.exportacion_comun import cabecera_descarga

router = APIRouter(
    prefix="/controles",
    tags=["controles"],
    dependencies=[Depends(obtener_admin_actual)],
)

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- Rayser ----------------------------------------------------------------


@router.get(
    "/rayser/rango",
    response_model=RangoRayser,
    summary="Rango de operación de los manómetros",
)
async def rango_rayser() -> RangoRayser:
    """Valores del semáforo, para que el frontend no los tenga escritos a mano."""
    return RangoRayser(
        minimo=RAYSER_MINIMO,
        maximo=RAYSER_MAXIMO,
        normal=RAYSER_NORMAL,
        manometros=RAYSER_MANOMETROS,
    )


@router.get(
    "/rayser/exportar/excel",
    summary="Descarga el control de presiones en Excel",
)
async def exportar_rayser(
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Hoja mensual con la semaforización y, si las hay, las evidencias."""
    registros = await control_service.listar_rayser(db, desde, hasta)
    evidencias = await control_service.evidencias_rayser(db, desde, hasta)

    flujo = controles_excel.generar_excel_rayser(
        registros,
        evidencias,
        desde,
        hasta,
        controles_excel.titulo_periodo(desde, hasta),
    )

    nombre = f"rayser_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )


@router.get(
    "/rayser",
    response_model=list[RegistroRayserOut],
    summary="Registros de presiones del periodo",
)
async def listar_rayser(
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
) -> list[RegistroRayserOut]:
    """Del más reciente al más antiguo. No incluye las fotos."""
    registros = await control_service.listar_rayser(db, desde, hasta)
    return [RegistroRayserOut(**registro) for registro in registros]


@router.post(
    "/rayser",
    response_model=RegistroRayserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra la lectura diaria de los cuatro manómetros",
)
async def registrar_rayser(
    fecha: date = Form(),
    manometro_1: str = Form(),
    manometro_2: str = Form(),
    manometro_3: str = Form(),
    manometro_4: str = Form(),
    observaciones: str = Form(default=""),
    foto: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroRayserOut:
    """Guarda el registro del día.

    Llega como ``multipart`` porque puede traer la foto de evidencia, así que
    los valores viajan como texto y se convierten en el servicio.
    """
    lecturas = [
        control_service.convertir_lectura(valor, f"Manómetro {indice}")
        for indice, valor in enumerate(
            (manometro_1, manometro_2, manometro_3, manometro_4), start=1
        )
    ]

    contenido: bytes | None = None
    tipo: str | None = None

    if foto is not None:
        contenido = await foto.read()
        tipo = control_service.validar_foto(contenido, foto.content_type)

    registro = await control_service.registrar_rayser(
        db,
        fecha=fecha,
        lecturas=lecturas,
        observaciones=observaciones.strip() or None,
        foto=contenido,
        foto_tipo=tipo,
        admin=admin,
    )

    return RegistroRayserOut(
        id=registro.id,
        fecha=registro.fecha,
        manometros=control_service.describir_lecturas(registro.lecturas),
        observaciones=registro.observaciones,
        tiene_foto=registro.tiene_foto,
        fuera_de_rango=fuera_de_rango(registro.lecturas),
        responsable=registro.responsable,
        creado_at=registro.creado_at,
    )


@router.get(
    "/rayser/{registro_id}/foto",
    summary="Foto de evidencia de un registro",
    response_class=Response,
)
async def foto_rayser(
    registro_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Devuelve la imagen tal como se subió."""
    registro = await control_service.obtener_rayser(db, registro_id)

    if registro.foto is None or registro.foto_tipo is None:
        raise ErrorDeNegocio("Este registro no tiene evidencia fotográfica.")

    return Response(
        content=registro.foto,
        media_type=registro.foto_tipo,
        # Privado: la evidencia solo debe verla quien tiene sesión abierta.
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete(
    "/rayser/{registro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un registro mal capturado",
)
async def eliminar_rayser(
    registro_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permite recapturar el día: solo puede existir un registro por fecha."""
    await control_service.eliminar_rayser(db, registro_id)


# --- Inspección de SQP -----------------------------------------------------


def _detalle(inspeccion: InspeccionSqp) -> InspeccionSqpDetalle:
    """Arma la respuesta de una inspección resolviendo el texto de cada punto.

    El texto no se guarda con la respuesta: vive en el catálogo y se resuelve
    por ``orden``, para que corregir una errata no obligue a tocar el
    histórico.
    """
    return InspeccionSqpDetalle(
        id=inspeccion.id,
        fecha=inspeccion.fecha,
        area=inspeccion.area,
        area_label=etiqueta_area(inspeccion.area),
        encargado=inspeccion.encargado,
        cargo=inspeccion.cargo,
        responsable=inspeccion.responsable,
        creado_at=inspeccion.creado_at,
        total_no=sum(1 for r in inspeccion.respuestas if r.valor == "no"),
        sustancias=control_service.separar_sustancias(inspeccion.sustancias),
        respuestas=[
            RespuestaSqpOut(
                orden=respuesta.orden,
                codigo=respuesta.codigo,
                seccion=PUNTOS_SQP[respuesta.orden].seccion,
                texto=PUNTOS_SQP[respuesta.orden].texto,
                valor=respuesta.valor,
                observaciones=respuesta.observaciones,
            )
            for respuesta in inspeccion.respuestas
        ],
    )


@router.get(
    "/sqp/catalogo",
    response_model=CatalogoSqp,
    summary="Puntos del formato de inspección de SQP",
)
async def catalogo_sqp() -> CatalogoSqp:
    """Los textos viven en el backend: el frontend nunca los tiene a mano."""
    return CatalogoSqp(
        secciones=list(SECCIONES_SQP),
        puntos=[
            PuntoSqpOut(
                orden=orden,
                codigo=punto.codigo,
                seccion=punto.seccion,
                texto=punto.texto,
            )
            for orden, punto in enumerate(PUNTOS_SQP)
        ],
        renglones_sustancias=RENGLONES_SUSTANCIAS,
    )


@router.get(
    "/sqp",
    response_model=list[InspeccionSqpResumen],
    summary="Historial de inspecciones de SQP",
)
async def listar_sqp(
    desde: date | None = None,
    hasta: date | None = None,
    area: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[InspeccionSqpResumen]:
    """Con el conteo de puntos contestados con NO."""
    if area and area not in AREAS_VALIDAS:
        raise ErrorDeNegocio("El área seleccionada no existe en el catálogo.")

    filas = await control_service.listar_sqp(db, desde, hasta, area)
    return [InspeccionSqpResumen(**fila) for fila in filas]


@router.post(
    "/sqp",
    response_model=InspeccionSqpDetalle,
    status_code=status.HTTP_201_CREATED,
    summary="Guarda una inspección de SQP completa",
)
async def registrar_sqp(
    datos: InspeccionSqpCrear,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> InspeccionSqpDetalle:
    """Exige el formato entero: los 23 puntos y observaciones en cada NO."""
    inspeccion = await control_service.registrar_sqp(db, datos, admin)
    return _detalle(inspeccion)


@router.get(
    "/sqp/{inspeccion_id}",
    response_model=InspeccionSqpDetalle,
    summary="Inspección completa con sus respuestas",
)
async def obtener_sqp(
    inspeccion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> InspeccionSqpDetalle:
    """Detalle de una inspección guardada."""
    inspeccion = await control_service.obtener_sqp(db, inspeccion_id)
    return _detalle(inspeccion)


@router.get(
    "/sqp/{inspeccion_id}/exportar/excel",
    summary="Descarga la inspección en Excel",
)
async def exportar_sqp(
    inspeccion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Reproduce el formato en papel de la inspección."""
    inspeccion = await control_service.obtener_sqp(db, inspeccion_id)
    sustancias = control_service.separar_sustancias(inspeccion.sustancias)

    flujo = controles_excel.generar_excel_sqp(inspeccion, sustancias)
    nombre = f"inspeccion_sqp_{inspeccion.area.lower()}_{inspeccion.fecha:%Y%m%d}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )
