"""Controles ESH: presiones del Rayser e inspección de SQP.

Todo el router exige sesión de administrador. El prefijo ``/api/controles`` es
nuevo, así que hay que darlo de alta como aplicación de Cloudflare Access
(ver la regla 7 del CLAUDE.md y la nota en SEGURIDAD.md): mientras eso no
ocurra, lo único que lo defiende es la cookie de sesión.
"""

import json
import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
# El parser de formularios de Starlette crea SUS `UploadFile`, no la subclase
# de FastAPI: al leer los campos de fotos a mano hay que comprobar contra esta
# clase o el `isinstance` descarta todos los archivos en silencio.
from starlette.datastructures import UploadFile as ArchivoSubido

from app.api.deps import obtener_admin_actual
from app.core.constants import AREAS_VALIDAS, etiqueta_area
from app.core.controles_catalogo import (
    AREAS_PLATICAS,
    CONTROLES_CHECKLIST,
    MAX_FOTOS,
    PUNTOS_SQP,
    DefinicionChecklist,
    definicion_checklist,
    fuera_de_rango,
    RAYSER_MANOMETROS,
    RAYSER_MAXIMO,
    RAYSER_MINIMO,
    RAYSER_NORMAL,
    RENGLONES_SUSTANCIAS,
    SECCIONES_SQP,
)
from app.core.errors import (
    ErrorDeNegocio,
    RecursoNoEncontrado,
    mensaje_de_validacion,
)
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.models.control import InspeccionSqp
from app.schemas.control import (
    AreaPlaticaOut,
    CatalogoChecklist,
    CatalogoSqp,
    ChecklistCrear,
    InspeccionSqpCrear,
    InspeccionSqpDetalle,
    InspeccionSqpResumen,
    PlaticaCrear,
    PlaticaOut,
    PuntoControlOut,
    PuntoSqpOut,
    RespuestaSqpOut,
    RangoRayser,
    RegistroChecklistOut,
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


async def _leer_fotos(
    archivos: list[ArchivoSubido], etiqueta: str
) -> list[tuple[bytes, str]]:
    """Lee y valida las imágenes de un campo del multipart.

    Un archivo vacío se descarta: algunos navegadores mandan la parte del
    formulario aunque no se haya elegido nada.
    """
    imagenes: list[tuple[bytes, str]] = []

    for archivo in archivos:
        contenido = await archivo.read()
        if not contenido:
            continue
        tipo = control_service.validar_foto(contenido, archivo.content_type)
        imagenes.append((contenido, tipo))

    control_service.validar_cantidad_fotos(len(imagenes), etiqueta)

    return imagenes


def _primer_error(exc: ValidationError | json.JSONDecodeError) -> str:
    """Mensaje en español del primer problema de un cuerpo multipart.

    La parte estructurada del multipart se valida a mano, así que su error no
    pasa por el manejador de ``RequestValidationError`` y hay que traducirlo
    aquí.
    """
    if isinstance(exc, ValidationError):
        errores = exc.errors()
        if errores:
            return mensaje_de_validacion(errores[0])

    return "El cuerpo de la petición no es JSON válido."


def _definicion(control: str) -> DefinicionChecklist:
    """Busca el control en el catálogo o responde 404."""
    definicion = definicion_checklist(control)
    if definicion is None:
        raise RecursoNoEncontrado("El control solicitado no existe.")
    return definicion


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
    fotos: list[UploadFile] = File(default_factory=list),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroRayserOut:
    """Guarda el registro del día.

    Llega como ``multipart`` porque puede traer fotos de evidencia, así que
    los valores viajan como texto y se convierten en el servicio.
    """
    lecturas = [
        control_service.convertir_lectura(valor, f"Manómetro {indice}")
        for indice, valor in enumerate(
            (manometro_1, manometro_2, manometro_3, manometro_4), start=1
        )
    ]

    imagenes = await _leer_fotos(fotos, "Evidencia de la lectura")

    registro = await control_service.registrar_rayser(
        db,
        fecha=fecha,
        lecturas=lecturas,
        observaciones=observaciones.strip() or None,
        fotos=imagenes,
        admin=admin,
    )

    return RegistroRayserOut(
        id=registro.id,
        fecha=registro.fecha,
        manometros=control_service.describir_lecturas(registro.lecturas),
        observaciones=registro.observaciones,
        fotos=[foto.id for foto in registro.fotos],
        fuera_de_rango=fuera_de_rango(registro.lecturas),
        responsable=registro.responsable,
        creado_at=registro.creado_at,
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


# --- Fotos de evidencia ----------------------------------------------------


@router.get(
    "/fotos/{foto_id}",
    summary="Foto de evidencia de cualquier control",
    response_class=Response,
)
async def obtener_foto(
    foto_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Devuelve la imagen tal como se subió.

    Un solo endpoint para las tres procedencias: Rayser, los controles de
    lista de verificación y las pláticas.
    """
    foto = await control_service.obtener_foto(db, foto_id)

    return Response(
        content=foto.imagen,
        media_type=foto.tipo,
        # Privado: la evidencia solo debe verla quien tiene sesión abierta.
        headers={"Cache-Control": "private, max-age=3600"},
    )


# --- Listas de verificación (OK / NO OK) -----------------------------------


@router.get(
    "/checklist/{control}/catalogo",
    response_model=CatalogoChecklist,
    summary="Puntos de un control de lista de verificación",
)
async def catalogo_checklist(control: str) -> CatalogoChecklist:
    """Los puntos viven en el backend: el frontend nunca los tiene a mano."""
    definicion = _definicion(control)

    return CatalogoChecklist(
        clave=definicion.clave,
        titulo=definicion.titulo,
        subtitulo=definicion.subtitulo,
        puntos=[
            PuntoControlOut(orden=orden, clave=punto.clave, etiqueta=punto.etiqueta)
            for orden, punto in enumerate(definicion.puntos)
        ],
        max_fotos=MAX_FOTOS,
    )


@router.get(
    "/checklist/{control}/exportar/excel",
    summary="Descarga el control en Excel",
)
async def exportar_checklist(
    control: str,
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Hoja mensual con los colores del formato y sus evidencias."""
    definicion = _definicion(control)

    registros = await control_service.listar_checklist(db, definicion, desde, hasta)
    evidencias = await control_service.evidencias_checklist(db, definicion, desde, hasta)

    flujo = controles_excel.generar_excel_checklist(
        definicion,
        registros,
        evidencias,
        desde,
        hasta,
        controles_excel.titulo_periodo(desde, hasta),
    )

    nombre = f"{definicion.clave}_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )


@router.get(
    "/checklist/{control}",
    response_model=list[RegistroChecklistOut],
    summary="Registros de un control en el periodo",
)
async def listar_checklist(
    control: str,
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
) -> list[RegistroChecklistOut]:
    """Del más reciente al más antiguo. No incluye las imágenes."""
    definicion = _definicion(control)
    registros = await control_service.listar_checklist(db, definicion, desde, hasta)
    return [RegistroChecklistOut(**registro) for registro in registros]


@router.post(
    "/checklist/{control}",
    response_model=RegistroChecklistOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra el recorrido del día",
)
async def registrar_checklist(
    control: str,
    request: Request,
    fecha: date = Form(),
    puntos: str = Form(description="JSON con la respuesta de cada punto."),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroChecklistOut:
    """Guarda el recorrido completo con sus evidencias.

    Llega como ``multipart`` porque cada punto en NO OK trae sus fotos. La
    parte estructurada viaja como JSON en ``puntos`` y se valida con Pydantic
    para que los mensajes salgan en español; las imágenes vienen en campos
    ``fotos_{orden}``, uno por punto.
    """
    definicion = _definicion(control)

    try:
        datos = ChecklistCrear.model_validate(
            {"fecha": fecha, "puntos": json.loads(puntos)}
        )
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ErrorDeNegocio(_primer_error(exc)) from exc

    formulario = await request.form()
    fotos_por_punto: dict[int, list[tuple[bytes, str]]] = {}

    for punto in datos.puntos:
        archivos = [
            archivo
            for archivo in formulario.getlist(f"fotos_{punto.orden}")
            if isinstance(archivo, ArchivoSubido)
        ]
        if archivos:
            etiqueta = definicion.puntos[punto.orden].etiqueta
            fotos_por_punto[punto.orden] = await _leer_fotos(archivos, etiqueta)

    registro = await control_service.registrar_checklist(
        db,
        definicion=definicion,
        datos=datos,
        fotos_por_punto=fotos_por_punto,
        admin=admin,
    )

    # Se relee para devolver los identificadores de las fotos ya guardadas.
    guardados = await control_service.listar_checklist(
        db, definicion, registro.fecha, registro.fecha
    )
    return RegistroChecklistOut(**guardados[0])


@router.delete(
    "/checklist/{control}/{registro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un registro mal capturado",
)
async def eliminar_checklist(
    control: str,
    registro_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permite recapturar el día: solo puede existir un registro por fecha."""
    await control_service.eliminar_checklist(db, _definicion(control), registro_id)


# --- Pláticas diarias de seguridad -----------------------------------------


@router.get(
    "/platicas/areas",
    response_model=list[AreaPlaticaOut],
    summary="Áreas del formato de pláticas",
)
async def areas_platicas() -> list[AreaPlaticaOut]:
    """No son las áreas del cuestionario: son las columnas de esta hoja."""
    return [
        AreaPlaticaOut(clave=area.clave, etiqueta=area.etiqueta)
        for area in AREAS_PLATICAS
    ]


@router.get(
    "/platicas/exportar/excel",
    summary="Descarga las pláticas en Excel",
)
async def exportar_platicas(
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Hoja mensual con una columna por área y sus evidencias."""
    platicas = await control_service.listar_platicas(db, desde, hasta)
    evidencias = await control_service.evidencias_platicas(db, desde, hasta)

    flujo = controles_excel.generar_excel_platicas(
        platicas,
        evidencias,
        desde,
        hasta,
        controles_excel.titulo_periodo(desde, hasta),
    )

    nombre = f"platicas_esh_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )


@router.get(
    "/platicas",
    response_model=list[PlaticaOut],
    summary="Pláticas impartidas en el periodo",
)
async def listar_platicas(
    desde: date,
    hasta: date,
    db: AsyncSession = Depends(get_db),
) -> list[PlaticaOut]:
    """De la más reciente a la más antigua. No incluye las imágenes."""
    platicas = await control_service.listar_platicas(db, desde, hasta)
    return [PlaticaOut(**platica) for platica in platicas]


@router.post(
    "/platicas",
    response_model=PlaticaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra una plática impartida",
)
async def registrar_platica(
    fecha: date = Form(),
    tema: str = Form(),
    areas: str = Form(description="JSON con las claves de las áreas."),
    fotos: list[UploadFile] = File(default_factory=list),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> PlaticaOut:
    """Guarda la plática con su evidencia fotográfica, que es obligatoria."""
    try:
        datos = PlaticaCrear.model_validate(
            {"fecha": fecha, "tema": tema, "areas": json.loads(areas)}
        )
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ErrorDeNegocio(_primer_error(exc)) from exc

    imagenes = await _leer_fotos(fotos, "Evidencia de la plática")

    platica = await control_service.registrar_platica(
        db, datos=datos, fotos=imagenes, admin=admin
    )

    guardadas = await control_service.listar_platicas(db, platica.fecha, platica.fecha)
    actual = next(item for item in guardadas if item["id"] == platica.id)

    return PlaticaOut(**actual)


@router.delete(
    "/platicas/{platica_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina una plática mal capturada",
)
async def eliminar_platica(
    platica_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Borra el registro y sus fotos."""
    await control_service.eliminar_platica(db, platica_id)
