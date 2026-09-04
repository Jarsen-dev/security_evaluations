"""Catálogo de insumos de seguridad: medicamentos, EPP, señalización.

Todo el router exige acceso al módulo ``catalogo``; modificar y eliminar piden
además el permiso de edición.

El prefijo ``/api/catalogo`` es nuevo, así que hay que darlo de alta como
aplicación de Cloudflare Access, igual que la ruta ``catalogo`` del panel (ver
la regla 7 del CLAUDE.md y la lista de pendientes de SEGURIDAD.md). Mientras
eso no ocurra, lo único que lo defiende es la cookie de sesión más la
comprobación de permisos.

Aquí se dan de alta los insumos y se corrige su existencia tras el conteo
físico. El código **no** identifica al insumo: puede repetirse, y lo que
distingue a dos productos con el mismo código es su descripción. Las entradas por recepción no pasan por este router: las suma
``inventario``, que es donde se fotografía la remisión.
"""

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import requiere
from app.core.bitacora import anotar
from app.core.constants import (
    CATEGORIAS_INSUMO,
    CATEGORIAS_VALIDAS,
    UNIDADES_MEDIDA,
)
from app.core.errors import ErrorDeNegocio
from app.db.session import get_db
from app.models.insumo import ESTADOS_FILTRABLES
from app.schemas.catalogo import (
    CatalogoCategorias,
    CatalogoUnidades,
    ErrorImportacionInsumo,
    InsumoActualizar,
    InsumoCrear,
    InsumoOut,
    InsumosPaginados,
    ResultadoImportacionInsumos,
)
from app.services import catalogo_excel, insumo_service
from app.services.exportacion_comun import cabecera_descarga

router = APIRouter(
    prefix="/catalogo",
    tags=["catalogo"],
    dependencies=[Depends(requiere("catalogo"))],
)

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Nginx ya corta en 10 MB; este límite es la segunda barrera, por si el
# backend se expone sin el proxy delante.
MAX_TAMANO_ARCHIVO = 10 * 1024 * 1024

# --- Rutas literales -------------------------------------------------------
# IMPORTANTE: van declaradas ANTES de /catalogo/{insumo_id}. FastAPI resuelve
# por orden: si estuvieran después, "categorias" se interpretaría como un UUID
# y devolvería un 422.


@router.get(
    "/categorias",
    response_model=CatalogoCategorias,
    summary="Categorías válidas de los insumos",
)
async def listar_categorias() -> CatalogoCategorias:
    """Alimenta el selector del formulario y el filtro de la tabla.

    Se sirven desde el backend, igual que las áreas, para que el frontend
    nunca las tenga escritas a mano.
    """
    return CatalogoCategorias(categorias=list(CATEGORIAS_INSUMO))


@router.get(
    "/unidades",
    response_model=CatalogoUnidades,
    summary="Unidades de medida válidas de los insumos",
)
async def listar_unidades() -> CatalogoUnidades:
    """Alimenta el selector del formulario, igual que las categorías."""
    return CatalogoUnidades(unidades=list(UNIDADES_MEDIDA))


@router.get(
    "/plantilla-excel",
    summary="Plantilla de Excel para cargar el catálogo",
)
async def descargar_plantilla() -> StreamingResponse:
    """Excel con los encabezados, un ejemplo y una hoja de instrucciones."""
    flujo = catalogo_excel.generar_plantilla()
    return StreamingResponse(
        flujo,
        media_type=TIPO_EXCEL,
        headers=cabecera_descarga("plantilla_catalogo.xlsx"),
    )


@router.post(
    "/importar-excel",
    response_model=ResultadoImportacionInsumos,
    summary="Carga masiva del catálogo desde un Excel",
)
async def importar_excel(
    request: Request,
    archivo: UploadFile = File(description="Archivo .xlsx con la hoja 'Insumos'."),
    db: AsyncSession = Depends(get_db),
) -> ResultadoImportacionInsumos:
    """Da de alta los insumos nuevos y corrige los que ya existen.

    De un insumo que ya estaba solo se toca lo que el archivo trae **distinto**,
    y solo en las columnas que el archivo realmente traía. La **existencia
    queda fuera** a propósito: la mueven las recepciones, así que volver a
    subir un archivo viejo la borraría junto con las entradas de almacén
    posteriores. Una fila con problemas no invalida el resto; se reporta su
    número.
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

    lectura = catalogo_excel.parsear_excel(contenido)
    errores = [
        ErrorImportacionInsumo(fila=error.fila, mensaje=error.mensaje)
        for error in lectura.errores
    ]

    # Los schemas vuelven a validar lo que el lector dio por bueno: son la
    # misma puerta que usa el alta manual, así que ninguna fila entra por un
    # camino con menos comprobaciones.
    validas: list[InsumoCrear] = []
    for indice, datos in enumerate(lectura.filas):
        try:
            validas.append(InsumoCrear.model_validate(datos))
        except ValidationError as exc:
            errores.append(
                ErrorImportacionInsumo(
                    # El lector conserva el orden, y las filas empiezan en 2.
                    fila=indice + 2,
                    mensaje=str(exc.errors()[0].get("msg", "El renglón no es válido.")),
                )
            )

    resumen = await insumo_service.importar(db, validas, columnas=lectura.columnas)
    anotar(
        request,
        detalle=(
            f"{resumen.creados} nuevos, {resumen.actualizados} actualizados, "
            f"{resumen.sin_cambios} sin cambios"
        ),
    )

    return ResultadoImportacionInsumos(
        creados=resumen.creados,
        actualizados=resumen.actualizados,
        sin_cambios=resumen.sin_cambios,
        errores=errores,
    )


# --- Insumos ---------------------------------------------------------------


@router.get(
    "",
    response_model=InsumosPaginados,
    summary="Lista el catálogo con búsqueda y filtros",
)
async def listar_insumos(
    busqueda: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=30),
    estado: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
) -> InsumosPaginados:
    """Página de 50 insumos, en orden alfabético."""
    if categoria and categoria not in CATEGORIAS_VALIDAS:
        raise ErrorDeNegocio("La categoría del filtro no es válida.")

    if estado and estado not in ESTADOS_FILTRABLES:
        raise ErrorDeNegocio("El estado del filtro no es válido.")

    resultado = await insumo_service.listar(
        db,
        busqueda=busqueda,
        categoria=categoria or None,
        estado=estado or None,
        page=page,
    )

    return InsumosPaginados(
        total=resultado["total"],
        page=resultado["page"],
        size=resultado["size"],
        items=[InsumoOut.model_validate(fila) for fila in resultado["items"]],
    )


@router.post(
    "",
    response_model=InsumoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Da de alta un insumo",
)
async def crear_insumo(
    datos: InsumoCrear,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> InsumoOut:
    """Lo que no puede repetirse es la pareja código + descripción.

    Un mismo código de proveedor ampara varios productos; la descripción es lo
    que los distingue, y por eso es obligatoria.
    """
    insumo = await insumo_service.crear(db, datos)
    # Con el código repetible, `codigo` a secas ya no dice cuál insumo fue.
    anotar(request, detalle=insumo_service.etiquetar(insumo))
    return InsumoOut.model_validate(insumo)


@router.put(
    "/{insumo_id}",
    dependencies=[Depends(requiere("catalogo", editar=True))],
    response_model=InsumoOut,
    summary="Actualiza un insumo",
)
async def actualizar_insumo(
    insumo_id: uuid.UUID,
    datos: InsumoActualizar,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> InsumoOut:
    """Incluye la existencia: es donde se corrige tras el conteo."""
    insumo = await insumo_service.actualizar(db, insumo_id, datos)
    anotar(request, detalle=insumo_service.etiquetar(insumo))
    return InsumoOut.model_validate(insumo)


@router.delete(
    "/{insumo_id}",
    dependencies=[Depends(requiere("catalogo", editar=True))],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un insumo del catálogo",
)
async def eliminar_insumo(
    insumo_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Lo borra por completo; la bitácora conserva código y descripción."""
    etiqueta = await insumo_service.eliminar(db, insumo_id)
    anotar(request, detalle=etiqueta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
