"""Endpoints de administración de cuestionarios, preguntas y opciones.

Todo el router exige acceso al módulo de cuestionarios. Crear y leer basta
con el acceso; modificar y eliminar piden además el permiso de edición, que
se agrega endpoint por endpoint.
"""

import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import requiere
from app.core.bitacora import anotar
from app.core.errors import ErrorDeNegocio
from app.db.session import get_db
from app.schemas.cuestionario import (
    CuestionarioActualizar,
    CuestionarioCrear,
    CuestionarioOut,
    CuestionarioResumen,
    ErrorImportacion,
    PreguntaIn,
    PreguntaOut,
    ReordenarPreguntas,
    ResultadoImportacionOut,
)
from app.services import cuestionario_service, excel_import

router = APIRouter(
    tags=["cuestionarios"],
    dependencies=[Depends(requiere("cuestionarios"))],
)

# Nginx ya corta en 10 MB; este límite es la segunda barrera, por si el
# backend se expone sin el proxy delante.
MAX_TAMANO_ARCHIVO = 10 * 1024 * 1024


# --- Cuestionarios ---------------------------------------------------------


@router.get(
    "/cuestionarios",
    response_model=list[CuestionarioResumen],
    summary="Lista los cuestionarios con sus conteos",
)
async def listar(db: AsyncSession = Depends(get_db)) -> list[CuestionarioResumen]:
    """Devuelve todos los cuestionarios, del más reciente al más antiguo."""
    filas = await cuestionario_service.listar_cuestionarios(db)
    return [CuestionarioResumen.model_validate(fila) for fila in filas]


@router.post(
    "/cuestionarios",
    response_model=CuestionarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un cuestionario con sus preguntas",
)
async def crear(
    datos: CuestionarioCrear, request: Request, db: AsyncSession = Depends(get_db)
) -> CuestionarioOut:
    """Crea el cuestionario y genera su token público."""
    cuestionario = await cuestionario_service.crear_cuestionario(db, datos)
    anotar(request, detalle=cuestionario.nombre)
    return CuestionarioOut.model_validate(cuestionario)


# --- Importación desde Excel -----------------------------------------------
# IMPORTANTE: estas dos rutas van declaradas ANTES de /cuestionarios/{id}.
# FastAPI resuelve por orden: si estuvieran después, "plantilla-excel" se
# interpretaría como un UUID y devolvería un 422.


@router.get(
    "/cuestionarios/plantilla-excel",
    summary="Descarga la plantilla de Excel para capturar preguntas",
)
async def descargar_plantilla() -> StreamingResponse:
    """Genera la plantilla en memoria, sin escribir archivos temporales."""
    flujo = excel_import.generar_plantilla()

    return StreamingResponse(
        flujo,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="plantilla_preguntas.xlsx"'
            )
        },
    )


@router.post(
    "/cuestionarios/importar-excel",
    response_model=ResultadoImportacionOut,
    summary="Lee un Excel y devuelve las preguntas válidas y los errores por fila",
)
async def importar_excel(
    archivo: UploadFile = File(description="Archivo .xlsx con la hoja 'Preguntas'."),
) -> ResultadoImportacionOut:
    """Parsea el archivo sin guardar nada.

    Las preguntas se devuelven al constructor para que el usuario las revise
    y decida; se persisten hasta que guarde el cuestionario.
    """
    nombre = (archivo.filename or "").lower()
    if not nombre.endswith(".xlsx"):
        raise ErrorDeNegocio(
            "El archivo debe ser un Excel con extensión .xlsx. "
            "Si tu archivo es .xls, ábrelo en Excel y guárdalo como .xlsx."
        )

    contenido = await archivo.read()

    if len(contenido) == 0:
        raise ErrorDeNegocio("El archivo está vacío.")

    if len(contenido) > MAX_TAMANO_ARCHIVO:
        raise ErrorDeNegocio(
            f"El archivo pesa más de {MAX_TAMANO_ARCHIVO // (1024 * 1024)} MB."
        )

    resultado = excel_import.parsear_excel(contenido)

    return ResultadoImportacionOut(
        importadas=resultado.importadas,
        errores=[
            ErrorImportacion(fila=error.fila, mensaje=error.mensaje)
            for error in resultado.errores
        ],
        preguntas=resultado.preguntas,
    )


@router.get(
    "/cuestionarios/{cuestionario_id}",
    response_model=CuestionarioOut,
    summary="Detalle completo con preguntas y opciones",
)
async def detalle(
    cuestionario_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CuestionarioOut:
    """Devuelve el cuestionario con todo lo necesario para editarlo."""
    cuestionario = await cuestionario_service.obtener_cuestionario(db, cuestionario_id)
    return CuestionarioOut.model_validate(cuestionario)


@router.put(
    "/cuestionarios/{cuestionario_id}",
    dependencies=[Depends(requiere("cuestionarios", editar=True))],
    response_model=CuestionarioOut,
    summary="Actualiza el cuestionario",
)
async def actualizar(
    cuestionario_id: uuid.UUID,
    datos: CuestionarioActualizar,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CuestionarioOut:
    """Actualiza metadatos y, si se envían, el conjunto de preguntas."""
    cuestionario = await cuestionario_service.actualizar_cuestionario(
        db, cuestionario_id, datos
    )
    anotar(request, detalle=cuestionario.nombre)
    return CuestionarioOut.model_validate(cuestionario)


@router.delete(
    "/cuestionarios/{cuestionario_id}",
    dependencies=[Depends(requiere("cuestionarios", editar=True))],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina el cuestionario y todo su contenido",
)
async def eliminar(
    cuestionario_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """Borra en cascada preguntas, opciones, intentos y respuestas."""
    nombre = await cuestionario_service.eliminar_cuestionario(db, cuestionario_id)
    anotar(request, detalle=nombre)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/cuestionarios/{cuestionario_id}/duplicar",
    response_model=CuestionarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Clona el cuestionario sin sus respuestas",
)
async def duplicar(
    cuestionario_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> CuestionarioOut:
    """La copia nace inactiva y con un token público propio."""
    copia = await cuestionario_service.duplicar_cuestionario(db, cuestionario_id)
    anotar(request, detalle=copia.nombre)
    return CuestionarioOut.model_validate(copia)


# --- Preguntas -------------------------------------------------------------


@router.post(
    "/cuestionarios/{cuestionario_id}/preguntas",
    response_model=PreguntaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agrega una pregunta al final",
)
async def agregar_pregunta(
    cuestionario_id: uuid.UUID,
    datos: PreguntaIn,
    db: AsyncSession = Depends(get_db),
) -> PreguntaOut:
    """Agrega una pregunta validando las reglas de negocio."""
    pregunta = await cuestionario_service.agregar_pregunta(db, cuestionario_id, datos)
    return PreguntaOut.model_validate(pregunta)


@router.put(
    "/preguntas/{pregunta_id}",
    dependencies=[Depends(requiere("cuestionarios", editar=True))],
    response_model=PreguntaOut,
    summary="Actualiza una pregunta y sus opciones",
)
async def actualizar_pregunta(
    pregunta_id: uuid.UUID, datos: PreguntaIn, db: AsyncSession = Depends(get_db)
) -> PreguntaOut:
    """Reemplaza texto, puntos y opciones de la pregunta."""
    pregunta = await cuestionario_service.actualizar_pregunta(db, pregunta_id, datos)
    return PreguntaOut.model_validate(pregunta)


@router.delete(
    "/preguntas/{pregunta_id}",
    dependencies=[Depends(requiere("cuestionarios", editar=True))],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina una pregunta",
)
async def eliminar_pregunta(
    pregunta_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Response:
    """Elimina la pregunta y compacta el orden de las restantes."""
    await cuestionario_service.eliminar_pregunta(db, pregunta_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/cuestionarios/{cuestionario_id}/preguntas/orden",
    dependencies=[Depends(requiere("cuestionarios", editar=True))],
    response_model=CuestionarioOut,
    summary="Reordena las preguntas en lote",
)
async def reordenar_preguntas(
    cuestionario_id: uuid.UUID,
    datos: ReordenarPreguntas,
    db: AsyncSession = Depends(get_db),
) -> CuestionarioOut:
    """Recibe la lista completa de preguntas con su nuevo orden."""
    cuestionario = await cuestionario_service.reordenar_preguntas(
        db, cuestionario_id, datos.preguntas
    )
    return CuestionarioOut.model_validate(cuestionario)
