"""Estudios y capacitaciones normativos.

Todo el router exige sesión y el módulo ``estudios``. El prefijo
``/api/estudios`` es nuevo, así que hay que darlo de alta como aplicación de
Cloudflare Access (regla 7 del CLAUDE.md y la nota en ``SEGURIDAD.md``):
mientras eso no ocurra, lo único que lo defiende es la cookie de sesión.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual, requiere
from app.core.bitacora import anotar
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.schemas.estudio import (
    AvisosOut,
    CatalogoEstudios,
    EstudioCrear,
    EstudioOut,
)
from app.services import estudio_service, estudios_excel
from app.services.exportacion_comun import cabecera_descarga

router = APIRouter(
    prefix="/estudios",
    tags=["estudios"],
    dependencies=[Depends(requiere("estudios"))],
)

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# Las rutas estáticas van declaradas ANTES que la paramétrica: si no, FastAPI
# intenta leer "catalogo" y "avisos" como UUID.


@router.get(
    "/catalogo",
    response_model=CatalogoEstudios,
    summary="Opciones válidas de cada campo",
)
async def catalogo() -> CatalogoEstudios:
    """Vigencias, prioridades, estatus y demás listas del formulario.

    El panel las pide en lugar de tenerlas escritas a mano, igual que hace con
    las áreas y con los puntos de los controles.
    """
    return CatalogoEstudios.actual()


@router.get(
    "/avisos",
    response_model=AvisosOut,
    summary="Estudios por vencer y vencidos",
)
async def avisos(db: AsyncSession = Depends(get_db)) -> AvisosOut:
    """Lo que dibuja la campana del encabezado.

    Cubre el mes que viene y también lo que ya se pasó de fecha: un estudio
    vencido es justo el que no debe desaparecer del aviso.
    """
    return await estudio_service.avisos_vencimiento(db)


@router.get(
    "/exportar/excel",
    summary="Descarga los estudios en Excel",
)
async def exportar_excel(db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Reproduce la hoja DETALLE del archivo del departamento."""
    estudios = await estudio_service.listar_estudios(db)
    flujo = estudios_excel.generar_excel_estudios(estudios)

    return StreamingResponse(
        flujo,
        media_type=TIPO_EXCEL,
        headers=cabecera_descarga(estudios_excel.nombre_archivo_estudios()),
    )


@router.get(
    "",
    response_model=list[EstudioOut],
    summary="Todos los estudios capturados",
)
async def listar(db: AsyncSession = Depends(get_db)) -> list[EstudioOut]:
    """En el orden en que se dieron de alta, como la hoja original."""
    estudios = await estudio_service.listar_estudios(db)
    return [EstudioOut.model_validate(estudio) for estudio in estudios]


@router.post(
    "",
    response_model=EstudioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Da de alta un estudio",
)
async def crear(
    datos: EstudioCrear,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> EstudioOut:
    """Alta desde el formulario de la pestaña."""
    estudio = await estudio_service.crear_estudio(db, datos, admin)
    anotar(request, detalle=estudio.estudio)

    return EstudioOut.model_validate(estudio)


@router.put(
    "/{estudio_id}",
    response_model=EstudioOut,
    dependencies=[Depends(requiere("estudios", editar=True))],
    summary="Actualiza un estudio",
)
async def actualizar(
    estudio_id: uuid.UUID,
    datos: EstudioCrear,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EstudioOut:
    """Un estudio es un documento vivo: cambia de estatus y se renueva."""
    estudio = await estudio_service.actualizar_estudio(db, estudio_id, datos)
    anotar(request, detalle=estudio.estudio)

    return EstudioOut.model_validate(estudio)


@router.delete(
    "/{estudio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(requiere("estudios", editar=True))],
    summary="Elimina un estudio",
)
async def eliminar(
    estudio_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Para un renglón capturado por error o que ya no aplica."""
    nombre = await estudio_service.eliminar_estudio(db, estudio_id)
    anotar(request, detalle=nombre)
