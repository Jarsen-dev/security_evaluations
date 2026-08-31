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

from app.api.deps import obtener_admin_actual, requiere
from app.core.bitacora import anotar
from app.core.constants import AREAS_VALIDAS, etiqueta_area
from app.core.controles_catalogo import (
    AREAS_PLATICAS,
    CONTROLES_CHECKLIST,
    MAX_FOTOS,
    PCI_PRIMER_MES,
    PUNTOS_SQP,
    CampoFormato,
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
    AvisoPciMtto,
    AvisosPciMtto,
    CampoFormatoOut,
    CatalogoChecklist,
    CatalogoSqp,
    ChecklistCrear,
    CierreCrear,
    CierreOut,
    DetalleCierre,
    HallazgoOut,
    IncidenciaOut,
    InspeccionSqpCrear,
    InspeccionSqpDetalle,
    InspeccionSqpResumen,
    ListadoPciMtto,
    MesPendientePci,
    MotivoPciMtto,
    PlaticaCrear,
    PlaticaOut,
    PuntoControlOut,
    PuntoSqpOut,
    SeccionFormatoOut,
    RespuestaSqpOut,
    RangoRayser,
    RegistroChecklistOut,
    RegistroPciMttoOut,
    RegistroRayserOut,
)
from app.services import (
    cierre_service,
    control_service,
    controles_excel,
    incidencias_excel,
    pci_excel,
    pci_service,
)
from app.services.exportacion_comun import cabecera_descarga

router = APIRouter(
    prefix="/controles",
    tags=["controles"],
    dependencies=[Depends(requiere("controles"))],
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


def _campo(campo: CampoFormato) -> CampoFormatoOut:
    """Traduce un campo del catálogo a su forma de salida."""
    return CampoFormatoOut(
        clave=campo.clave,
        etiqueta=campo.etiqueta,
        etiqueta_ko=campo.etiqueta_ko,
        tipo=campo.tipo,
        opciones=list(campo.opciones),
        unidad=campo.unidad,
        obligatorio=campo.obligatorio,
        automatico=campo.automatico,
    )


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

    # Los cierres del periodo, en una consulta, más sus fotos de verificación:
    # el Excel se comparte, así que debe contar el problema y su solución.
    cierres = await cierre_service.cierres_por_registro(
        db, "rayser", [registro["id"] for registro in registros]
    )
    evidencias += await cierre_service.evidencias_de_cierres(
        db, cierres, {registro["id"]: registro["fecha"] for registro in registros}
    )

    flujo = controles_excel.generar_excel_rayser(
        registros,
        evidencias,
        desde,
        hasta,
        controles_excel.titulo_periodo(desde, hasta),
        cierres,
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
    request: Request,
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
    anotar(request, detalle=f"{registro.fecha:%Y-%m-%d}")

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
    dependencies=[Depends(requiere("controles", editar=True))],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un registro mal capturado",
)
async def eliminar_rayser(
    registro_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permite recapturar el día: solo puede existir un registro por fecha."""
    fecha_borrada = await control_service.eliminar_rayser(db, registro_id)
    anotar(request, detalle=f"{fecha_borrada:%Y-%m-%d}")


# --- Inspección de SQP -----------------------------------------------------


def _detalle(
    inspeccion: InspeccionSqp,
    fotos: dict[int, list[uuid.UUID]] | None = None,
) -> InspeccionSqpDetalle:
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
                fotos=(fotos or {}).get(respuesta.orden, []),
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
    request: Request,
    datos: str = Form(description="JSON con la inspección completa."),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> InspeccionSqpDetalle:
    """Exige el formato entero: los 23 puntos, observaciones y foto en cada NO.

    Llega como ``multipart`` porque cada punto inconforme trae su evidencia,
    igual que las listas de verificación: la parte estructurada viaja como
    JSON en ``datos`` y las imágenes en campos ``fotos_{orden}``.
    """
    try:
        limpio = InspeccionSqpCrear.model_validate(json.loads(datos))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ErrorDeNegocio(_primer_error(exc)) from exc

    formulario = await request.form()
    fotos_por_punto: dict[int, list[tuple[bytes, str]]] = {}

    for respuesta in limpio.respuestas:
        archivos = [
            archivo
            for archivo in formulario.getlist(f"fotos_{respuesta.orden}")
            if isinstance(archivo, ArchivoSubido)
        ]
        if archivos:
            fotos_por_punto[respuesta.orden] = await _leer_fotos(
                archivos, PUNTOS_SQP[respuesta.orden].codigo
            )

    inspeccion = await control_service.registrar_sqp(
        db, limpio, admin, fotos_por_punto
    )
    anotar(
        request,
        detalle=f"{etiqueta_area(inspeccion.area)}, {inspeccion.fecha:%Y-%m-%d}",
    )
    return _detalle(inspeccion, await control_service.ids_fotos_sqp(db, inspeccion))


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
    return _detalle(inspeccion, await control_service.ids_fotos_sqp(db, inspeccion))


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

    cierre = await cierre_service.obtener_cierre(db, "sqp", inspeccion.id)
    evidencias = await control_service.evidencias_sqp(db, inspeccion.id)

    if cierre is not None:
        evidencias += await cierre_service.evidencias_de_cierres(
            db, {inspeccion.id: cierre}, {inspeccion.id: inspeccion.fecha}
        )

    flujo = controles_excel.generar_excel_sqp(
        inspeccion, sustancias, cierre, evidencias
    )
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
        titulo_ko=definicion.titulo_ko,
        subtitulo=definicion.subtitulo,
        puntos=[
            PuntoControlOut(
                orden=orden,
                clave=punto.clave,
                etiqueta=punto.etiqueta,
                etiqueta_ko=punto.etiqueta_ko,
                categoria=punto.categoria,
                medicion=punto.medicion,
            )
            for orden, punto in enumerate(definicion.puntos)
        ],
        max_fotos=MAX_FOTOS,
        encabezado=[_campo(campo) for campo in definicion.encabezado],
        secciones=[
            SeccionFormatoOut(
                clave=seccion.clave,
                titulo=seccion.titulo,
                titulo_ko=seccion.titulo_ko,
                campos=[_campo(campo) for campo in seccion.campos],
            )
            for seccion in definicion.secciones
        ],
        # Lo que decide la forma del control: con encabezado es un formato por
        # inspección y admite varios registros el mismo día.
        por_inspeccion=bool(definicion.encabezado),
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

    cierres = await cierre_service.cierres_por_registro(
        db, control, [registro["id"] for registro in registros]
    )
    evidencias += await cierre_service.evidencias_de_cierres(
        db, cierres, {registro["id"]: registro["fecha"] for registro in registros}
    )

    flujo = controles_excel.generar_excel_checklist(
        definicion,
        registros,
        evidencias,
        desde,
        hasta,
        controles_excel.titulo_periodo(desde, hasta),
        cierres,
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
    encabezado: str = Form(default="{}", description="JSON del encabezado."),
    secciones: str = Form(default="{}", description="JSON de los bloques del pie."),
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
            {
                "fecha": fecha,
                "puntos": json.loads(puntos),
                "encabezado": json.loads(encabezado),
                "secciones": json.loads(secciones),
            }
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
    # Por id y no por fecha: un formato por inspección admite varios registros
    # el mismo día y el primero de la lista podría ser otro.
    guardado = await control_service.obtener_checklist(db, definicion, registro.id)
    return RegistroChecklistOut(**guardado)


@router.get(
    "/checklist/{control}/{registro_id}/exportar/excel",
    summary="Descarga una inspección en Excel",
)
async def exportar_inspeccion(
    control: str,
    registro_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Reproduce la hoja del formato con lo capturado en esa inspección."""
    definicion = _definicion(control)

    registro = await control_service.obtener_checklist(db, definicion, registro_id)
    evidencias = await control_service.evidencias_registro(db, definicion, registro_id)

    cierre = await cierre_service.obtener_cierre(db, control, registro_id)

    # Las fotos de la verificación van a la misma hoja de evidencias que las
    # del hallazgo: el Excel se comparte y tiene que mostrar el problema y la
    # prueba de que se resolvió.
    if cierre is not None:
        evidencias += await cierre_service.evidencias_de_cierres(
            db, {registro_id: cierre}, {registro_id: registro["fecha"]}
        )

    flujo = controles_excel.generar_excel_formato(
        definicion, registro, evidencias, cierre
    )
    nombre = f"{definicion.clave}_{registro['fecha']:%Y%m%d}_{str(registro_id)[:8]}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )


@router.delete(
    "/checklist/{control}/{registro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(requiere("controles", editar=True))],
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
    dependencies=[Depends(requiere("controles", editar=True))],
    summary="Elimina una plática mal capturada",
)
async def eliminar_platica(
    platica_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Borra el registro y sus fotos."""
    await control_service.eliminar_platica(db, platica_id)


# --- Cierre de hallazgos e incidencias -------------------------------------
#
# Cuelgan del mismo prefijo `/api/controles`, ya cubierto por
# `requiere("controles")` y por su aplicación de Cloudflare Access.


def _control_con_cierre(control: str) -> str:
    """Comprueba que el control admita cierre, o responde 404.

    Pláticas queda fuera a propósito: una plática impartida no es una
    inspección y no puede tener hallazgos.
    """
    if not cierre_service.es_control_valido(control):
        raise RecursoNoEncontrado("El control solicitado no existe.")
    return control


def _a_cierre_out(cierre) -> CierreOut | None:
    """Traduce el cierre del ORM, resolviendo los ids de sus evidencias."""
    if cierre is None:
        return None

    return CierreOut(
        id=cierre.id,
        hora_hallazgo=cierre.hora_hallazgo,
        ubicacion=cierre.ubicacion,
        accion_inmediata=cierre.accion_inmediata,
        responsable_accion=cierre.responsable_accion,
        hora_cierre=cierre.hora_cierre,
        accion_pendiente=cierre.accion_pendiente,
        responsable=cierre.responsable,
        creado_at=cierre.creado_at,
        actualizado_at=cierre.actualizado_at,
        fotos=[foto.id for foto in cierre.fotos],
    )


async def _leer_cierre_del_formulario(
    request: Request, datos_json: str
) -> tuple[CierreCrear, list[tuple[bytes, str]]]:
    """Valida la parte estructurada y lee las evidencias del multipart."""
    try:
        datos = CierreCrear.model_validate(json.loads(datos_json))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ErrorDeNegocio(_primer_error(exc)) from exc

    formulario = await request.form()
    archivos = [
        archivo
        for archivo in formulario.getlist("fotos")
        # El parser de Starlette crea SUS `UploadFile`, no la subclase de
        # FastAPI: con la clase equivocada se descartan todas en silencio.
        if isinstance(archivo, ArchivoSubido)
    ]

    fotos = await _leer_fotos(archivos, "Evidencia de la verificación")

    return datos, fotos


# Las rutas estáticas van ANTES que las paramétricas, o `/{control}` se traga
# `incidencias` y FastAPI intenta leerlo como clave de control.
@router.get(
    "/incidencias/exportar/excel",
    summary="Descarga las incidencias del periodo en Excel",
)
async def exportar_incidencias(
    desde: date,
    hasta: date,
    control: str | None = Query(default=None),
    estado: str | None = Query(default=None, description="'pendiente' o 'cerrado'."),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Todo lo que los filtros dejen a la vista, con sus evidencias."""
    incidencias = await cierre_service.listar_incidencias(
        db, desde=desde, hasta=hasta, control=control, estado=estado
    )
    detalles = await cierre_service.detalles_de_incidencias(db, incidencias)

    flujo = incidencias_excel.generar_excel_incidencias(
        detalles, controles_excel.titulo_periodo(desde, hasta)
    )

    nombre = f"incidencias_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )


@router.get(
    "/incidencias",
    response_model=list[IncidenciaOut],
    summary="Problemas detectados en el periodo, de todos los controles",
)
async def listar_incidencias(
    desde: date,
    hasta: date,
    control: str | None = Query(default=None),
    estado: str | None = Query(default=None, description="'pendiente' o 'cerrado'."),
    db: AsyncSession = Depends(get_db),
) -> list[IncidenciaOut]:
    """De la más reciente a la más antigua, con su cierre si ya lo tiene."""
    incidencias = await cierre_service.listar_incidencias(
        db, desde=desde, hasta=hasta, control=control, estado=estado
    )

    return [
        IncidenciaOut(
            control=incidencia.control,
            registro_id=incidencia.registro_id,
            fecha=incidencia.fecha,
            identificacion=incidencia.identificacion,
            total_hallazgos=incidencia.total_hallazgos,
            responsable=incidencia.responsable,
            estado=incidencia.estado,
            cierre=_a_cierre_out(incidencia.cierre),
        )
        for incidencia in incidencias
    ]


@router.get(
    "/cierres/{control}/{registro_id}",
    response_model=DetalleCierre,
    summary="Los hallazgos de una hoja y su cierre, si ya lo tiene",
)
async def obtener_cierre(
    control: str,
    registro_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DetalleCierre:
    """Lo que necesita el modal para abrirse."""
    detalle = await cierre_service.detalle_cierre(
        db, _control_con_cierre(control), registro_id
    )

    return DetalleCierre(
        control=detalle["control"],
        registro_id=detalle["registro_id"],
        fecha=detalle["fecha"],
        hallazgos=[
            HallazgoOut(
                orden=hallazgo.orden,
                etiqueta=hallazgo.etiqueta,
                observaciones=hallazgo.observaciones,
                fotos=hallazgo.fotos,
            )
            for hallazgo in detalle["hallazgos"]
        ],
        cierre=_a_cierre_out(detalle["cierre"]),
    )


@router.post(
    "/cierres/{control}/{registro_id}",
    response_model=CierreOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra el cierre de los hallazgos de una hoja",
)
async def crear_cierre(
    control: str,
    registro_id: uuid.UUID,
    request: Request,
    datos: str = Form(description="JSON con los campos del cierre."),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> CierreOut:
    """Da de alta el cierre.

    Se queda con el acceso simple del módulo, sin `editar`: quien levantó el
    hallazgo debe poder cerrarlo. Si la hoja ya tiene cierre responde 409 y
    hay que usar el `PUT`, que sí exige permiso de edición.
    """
    limpio, fotos = await _leer_cierre_del_formulario(request, datos)

    cierre = await cierre_service.guardar_cierre(
        db,
        control=_control_con_cierre(control),
        registro_id=registro_id,
        datos=cierre_service.DatosCierre(**limpio.model_dump()),
        fotos=fotos,
        admin=admin,
        actualizando=False,
    )

    anotar(request, detalle=f"{control} — {limpio.ubicacion}")

    return _a_cierre_out(cierre)  # type: ignore[return-value]


@router.put(
    "/cierres/{control}/{registro_id}",
    response_model=CierreOut,
    summary="Actualiza el cierre de una hoja",
    dependencies=[Depends(requiere("controles", editar=True))],
)
async def actualizar_cierre(
    control: str,
    registro_id: uuid.UUID,
    request: Request,
    datos: str = Form(description="JSON con los campos del cierre."),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> CierreOut:
    """Corrige un cierre ya capturado o le suma la acción pendiente resuelta.

    Sobrescribe información que alguien más pudo haber capturado, así que
    exige permiso de edición. Las evidencias solo se reemplazan si vienen
    fotos nuevas: reabrir el modal para corregir un dedazo no debe borrar la
    que ya estaba.
    """
    limpio, fotos = await _leer_cierre_del_formulario(request, datos)

    cierre = await cierre_service.guardar_cierre(
        db,
        control=_control_con_cierre(control),
        registro_id=registro_id,
        datos=cierre_service.DatosCierre(**limpio.model_dump()),
        fotos=fotos,
        admin=admin,
        actualizando=True,
    )

    anotar(request, detalle=f"{control} — {limpio.ubicacion}")

    return _a_cierre_out(cierre)  # type: ignore[return-value]


# --- PCI MTTO: mantenimiento del sistema contra incendios -------------------
#
# Las rutas estáticas van declaradas ANTES que las paramétricas, o `/{anio}`
# se tragaría "avisos" y "exportar".


async def _leer_reporte(
    archivo: UploadFile | None,
) -> tuple[bytes, str, str] | None:
    """Lee el documento adjunto, si vino alguno con contenido."""
    if archivo is None:
        return None

    contenido = await archivo.read()
    # Algunos navegadores mandan la parte del input aunque no se haya elegido
    # nada: eso no es un reporte vacío, es que no hay reporte.
    if not contenido:
        return None

    return pci_service.validar_reporte(contenido, archivo.filename)


async def _leer_evidencias(archivos: list[UploadFile]) -> list[tuple[bytes, str]]:
    """Las fotos del mantenimiento, con la misma validación que el resto."""
    return await _leer_fotos(
        [archivo for archivo in archivos if isinstance(archivo, ArchivoSubido)],
        "Evidencia del mantenimiento",
    )


@router.get(
    "/pci-mtto/avisos",
    response_model=AvisosPciMtto,
    summary="Meses sin explicar, para la campana del encabezado",
)
async def avisos_pci_mtto(db: AsyncSession = Depends(get_db)) -> AvisosPciMtto:
    """Los meses que el sistema cerró y nadie ha justificado.

    Viajan sin texto: el panel arma la frase con su diccionario y el nombre del
    mes con `Intl` (regla 6 del CLAUDE.md).
    """
    hoy = date.today()
    pendientes = await pci_service.meses_pendientes(db)

    avisos = [
        AvisoPciMtto(
            id=f"{pendiente['anio']}-{pendiente['mes']:02d}",
            anio=pendiente["anio"],
            mes=pendiente["mes"],
            # Nunca negativo: un mes cerrado por adelantado —solo posible si
            # alguien movió el reloj del servidor— no lleva "retraso".
            meses_de_retraso=max(
                0,
                (hoy.year - pendiente["anio"]) * 12 + hoy.month - pendiente["mes"],
            ),
        )
        for pendiente in pendientes
    ]

    return AvisosPciMtto(total=len(avisos), avisos=avisos)


@router.get(
    "/pci-mtto/exportar/excel",
    summary="Descarga el año en Excel",
)
async def exportar_pci_mtto(
    anio: int = Query(ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Dos hojas: los registros del año y las evidencias fotográficas."""
    registros = await pci_service.listar(db, anio)
    evidencias = await pci_service.evidencias(db, anio)

    flujo = pci_excel.generar_excel_pci(registros, evidencias, anio)
    nombre = f"pci_mtto_{anio}.xlsx"

    return StreamingResponse(
        flujo, media_type=TIPO_EXCEL, headers=cabecera_descarga(nombre)
    )


@router.get(
    "/pci-mtto",
    response_model=ListadoPciMtto,
    summary="Registros del año, años disponibles y meses sin explicar",
)
async def listar_pci_mtto(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
) -> ListadoPciMtto:
    """Todo lo que la pestaña necesita para dibujarse, en una sola petición."""
    elegido = anio if anio is not None else date.today().year

    return ListadoPciMtto(
        anio=elegido,
        registros=[
            RegistroPciMttoOut(**registro)
            for registro in await pci_service.listar(db, elegido)
        ],
        anios=await pci_service.anios_con_registros(db),
        pendientes=[
            MesPendientePci(**pendiente)
            for pendiente in await pci_service.meses_pendientes(db)
        ],
        primer_mes=MesPendientePci(
            anio=PCI_PRIMER_MES[0], mes=PCI_PRIMER_MES[1]
        ),
    )


@router.post(
    "/pci-mtto",
    response_model=RegistroPciMttoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra el mantenimiento de un mes",
)
async def registrar_pci_mtto(
    request: Request,
    anio: int = Form(),
    mes: int = Form(),
    realizado: bool = Form(),
    fecha: date | None = Form(default=None),
    motivo: str = Form(default=""),
    fotos: list[UploadFile] = File(default_factory=list),
    reporte: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroPciMttoOut:
    """Da de alta el registro del mes, con su evidencia o con su motivo."""
    registro = await pci_service.registrar(
        db,
        anio=anio,
        mes=mes,
        realizado=realizado,
        fecha=fecha,
        motivo=motivo,
        fotos=await _leer_evidencias(fotos),
        reporte=await _leer_reporte(reporte),
        admin=admin,
        hoy=date.today(),
    )

    anotar(request, detalle=f"{anio}-{mes:02d}")

    guardados = await pci_service.listar(db, anio)
    return RegistroPciMttoOut(
        **next(fila for fila in guardados if fila["id"] == registro.id)
    )


@router.get(
    "/pci-mtto/{anio}/{mes}/reporte",
    summary="Descarga el reporte de mantenimiento adjunto",
    response_class=Response,
)
async def descargar_reporte_pci_mtto(
    anio: int,
    mes: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Sirve el documento tal como se subió.

    **Siempre como `attachment` y con `nosniff`**, y no es opcional: el control
    acepta cualquier formato, y el archivo sale del mismo origen que el panel y
    con la cookie de sesión. Servido *inline*, un `.svg` o un `.html` subido
    como "reporte" se ejecutaría en ese origen —XSS almacenado con robo de
    sesión—. El endpoint de fotos se salva de esto porque su lista blanca son
    JPG y PNG; aquí la defensa tiene que estar en la respuesta.
    """
    contenido, nombre, tipo = await pci_service.obtener_reporte(db, anio, mes)

    return Response(
        content=contenido,
        media_type=tipo,
        headers={
            **cabecera_descarga(nombre),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post(
    "/pci-mtto/{anio}/{mes}/motivo",
    response_model=RegistroPciMttoOut,
    summary="Explica un mes que cerró sin mantenimiento",
)
async def capturar_motivo_pci_mtto(
    request: Request,
    anio: int,
    mes: int,
    datos: MotivoPciMtto,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroPciMttoOut:
    """Rellena el motivo que la solicitud urgente reclama.

    Va con el acceso simple del router y no con `editar`: llenar un hueco vacío
    es parte de capturar, y quien opera el control debe poder responder el aviso
    aunque no tenga permiso de edición. Mismo criterio que el cierre de
    hallazgos. Si el mes ya tiene motivo, responde 409 y hay que usar el PUT.
    """
    await pci_service.guardar_motivo(
        db, anio=anio, mes=mes, motivo=datos.motivo, admin=admin, actualizando=False
    )

    anotar(request, detalle=f"{anio}-{mes:02d}")

    registros = await pci_service.listar(db, anio)
    return RegistroPciMttoOut(
        **next(fila for fila in registros if fila["mes"] == mes)
    )


@router.put(
    "/pci-mtto/{anio}/{mes}/motivo",
    response_model=RegistroPciMttoOut,
    dependencies=[Depends(requiere("controles", editar=True))],
    summary="Corrige el motivo ya capturado de un mes",
)
async def corregir_motivo_pci_mtto(
    request: Request,
    anio: int,
    mes: int,
    datos: MotivoPciMtto,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroPciMttoOut:
    """Pisa el motivo que escribió alguien más: por eso exige `editar`."""
    await pci_service.guardar_motivo(
        db, anio=anio, mes=mes, motivo=datos.motivo, admin=admin, actualizando=True
    )

    anotar(request, detalle=f"{anio}-{mes:02d}")

    registros = await pci_service.listar(db, anio)
    return RegistroPciMttoOut(
        **next(fila for fila in registros if fila["mes"] == mes)
    )


@router.put(
    "/pci-mtto/{anio}/{mes}",
    response_model=RegistroPciMttoOut,
    dependencies=[Depends(requiere("controles", editar=True))],
    summary="Corrige el registro de un mes",
)
async def corregir_pci_mtto(
    request: Request,
    anio: int,
    mes: int,
    realizado: bool = Form(),
    fecha: date | None = Form(default=None),
    motivo: str = Form(default=""),
    conserva_reporte: bool = Form(default=True),
    fotos: list[UploadFile] = File(default_factory=list),
    reporte: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RegistroPciMttoOut:
    """La única forma de arreglar un mes: **no hay borrado**.

    Borrar no serviría de nada en un cierre automático, porque la vigilancia lo
    volvería a levantar en menos de una hora con el motivo otra vez en blanco.
    Es también la salida del caso incómodo: el sistema cerró el mes en rojo y
    resulta que el mantenimiento sí se hizo.
    """
    await pci_service.corregir(
        db,
        anio=anio,
        mes=mes,
        realizado=realizado,
        fecha=fecha,
        motivo=motivo,
        fotos=await _leer_evidencias(fotos),
        reporte=await _leer_reporte(reporte),
        conserva_reporte=conserva_reporte,
        admin=admin,
    )

    anotar(request, detalle=f"{anio}-{mes:02d}")

    registros = await pci_service.listar(db, anio)
    return RegistroPciMttoOut(
        **next(fila for fila in registros if fila["mes"] == mes)
    )
