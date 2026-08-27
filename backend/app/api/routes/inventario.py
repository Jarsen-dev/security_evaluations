"""Recepciones de mercancía por foto de la remisión.

Todo el router exige acceso al módulo ``inventario``; guardar una recepción
pide además el permiso de edición, porque mueve existencias.

El prefijo ``/api/inventario`` es nuevo, así que hay que darlo de alta como
aplicación de Cloudflare Access, igual que la ruta ``inventario`` del panel
(ver la regla 7 del CLAUDE.md y la lista de pendientes de SEGURIDAD.md).
Mientras eso no ocurra, lo único que lo defiende es la cookie de sesión más la
comprobación de permisos.

Los dos endpoints que usa el celular para mandar la foto **no** están aquí:
cuelgan de ``/api/publico`` (ver ``routes/publico.py``), que es el prefijo que
Access deja pasar a propósito.
"""

import asyncio
import logging
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual, requiere
from app.core.bitacora import anotar
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.schemas.recepcion import (
    EstadoSesionOut,
    RecepcionCrear,
    RecepcionOut,
    RecepcionesPaginadas,
    ResultadoOcr,
    SesionQrOut,
    TipoDocumento,
)
from app.services import ocr_recepciones, plantilla_service, recepcion_service
from app.services.ocr_recepciones import TIPO_DESCONOCIDO, ResultadoExtraccion

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inventario",
    tags=["inventario"],
    dependencies=[Depends(requiere("inventario"))],
)

def _respuesta_ocr(
    foto_id: uuid.UUID, resultado: ResultadoExtraccion
) -> ResultadoOcr:
    """Traduce el resultado del pipeline a lo que consume el formulario.

    Se responde 200 aunque ``ocr_ok`` sea falso: la foto ya está guardada y el
    formulario abre en captura manual. Un código de error haría que el
    frontend tratara como fallo lo que en realidad es "hazlo a mano".
    """
    datos = resultado.datos or {}
    conocido = resultado.tipo_documento != TIPO_DESCONOCIDO

    items = datos.get("items") or []
    if not isinstance(items, list):
        items = []

    return ResultadoOcr(
        foto_id=foto_id,
        ocr_ok=resultado.ocr_ok,
        tipo_documento=resultado.tipo_documento,
        tipo_conocido=conocido,
        proveedor=datos.get("proveedor"),
        folio=datos.get("folio"),
        fecha=datos.get("fecha"),
        items=[item for item in items if isinstance(item, dict)],
        advertencias=resultado.advertencias,
        ocr_raw=datos or None,
        error=resultado.error,
    )


# --- Rutas literales -------------------------------------------------------
# IMPORTANTE: van declaradas ANTES de /recepciones/{recepcion_id}. Es un
# catch-all: si estuviera antes, "tipos-documento" se interpretaría como UUID
# y devolvería un 422.


@router.post(
    "/recepciones/ocr",
    response_model=ResultadoOcr,
    summary="Guarda la foto de una remisión y extrae sus datos",
)
async def procesar_foto(
    request: Request,
    archivo: UploadFile = File(description="Foto de la remisión."),
    db: AsyncSession = Depends(get_db),
) -> ResultadoOcr:
    """Guarda la evidencia **primero** y después intenta leerla.

    Ese orden es deliberado: si la extracción falla, el operador ya no tiene
    que volver al almacén por la hoja.
    """
    contenido = await archivo.read()
    tipo = recepcion_service.validar_foto(contenido, archivo.content_type)

    foto = await recepcion_service.guardar_foto(
        db, imagen=contenido, tipo_mime=tipo
    )
    await db.commit()

    corpus = await plantilla_service.corpus(db)
    resultado = await ocr_recepciones.extraer(contenido, corpus)

    anotar(request, detalle=f"tipo={resultado.tipo_documento}")
    return _respuesta_ocr(foto.id, resultado)


@router.post(
    "/recepciones/ocr/desde-sesion/{sesion_id}",
    response_model=ResultadoOcr,
    summary="Extrae los datos de la foto que subió el celular",
)
async def procesar_desde_sesion(
    sesion_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ResultadoOcr:
    """Toma la foto de una sesión QR ya subida y corre el pipeline."""
    foto = await recepcion_service.consumir_sesion(db, sesion_id)

    corpus = await plantilla_service.corpus(db)
    resultado = await ocr_recepciones.extraer(foto.imagen, corpus)

    anotar(request, detalle=f"tipo={resultado.tipo_documento}")
    return _respuesta_ocr(foto.id, resultado)


@router.get(
    "/recepciones/tipos-documento",
    response_model=list[TipoDocumento],
    summary="Formatos de documento registrados",
)
async def listar_tipos(
    db: AsyncSession = Depends(get_db),
) -> list[TipoDocumento]:
    """Alimenta el filtro del historial."""
    return [
        TipoDocumento(**fila) for fila in await plantilla_service.listar_tipos(db)
    ]


@router.get(
    "/recepciones/foto/{foto_id}",
    summary="Sirve la foto de una recepción",
    response_class=Response,
)
async def obtener_foto(
    foto_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Response:
    """La evidencia, siempre autenticada.

    No hay ``StaticFiles`` montado: la imagen sale por aquí para que la
    cubran la sesión y el permiso de módulo, igual que las evidencias de los
    controles ESH.
    """
    foto = await recepcion_service.obtener_foto(db, foto_id)
    return Response(
        content=foto.imagen,
        media_type=foto.tipo,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post(
    "/recepciones/qr-session",
    response_model=SesionQrOut,
    status_code=status.HTTP_201_CREATED,
    summary="Abre una sesión para capturar la foto desde el celular",
)
async def crear_sesion_qr(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> SesionQrOut:
    """Crea la sesión que el QR apunta, y barre las vencidas de paso."""
    sesion = await recepcion_service.crear_sesion(db, creado_por=admin.username)
    anotar(request, detalle=str(sesion.id))
    return SesionQrOut.model_validate(sesion)


@router.get(
    "/recepciones",
    response_model=RecepcionesPaginadas,
    summary="Historial de recepciones",
)
async def listar_recepciones(
    busqueda: str | None = Query(default=None, max_length=100),
    tipo_documento: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
) -> RecepcionesPaginadas:
    """Página de 50, de la captura más reciente hacia atrás."""
    resultado = await recepcion_service.listar(
        db,
        busqueda=busqueda,
        tipo_documento=tipo_documento or None,
        page=page,
    )

    return RecepcionesPaginadas(
        total=resultado["total"],
        page=resultado["page"],
        size=resultado["size"],
        items=[RecepcionOut.model_validate(fila) for fila in resultado["items"]],
    )


@router.post(
    "/recepciones",
    response_model=RecepcionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(requiere("inventario", editar=True))],
    summary="Guarda una recepción y da entrada al inventario",
)
async def crear_recepcion(
    datos: RecepcionCrear,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(obtener_admin_actual),
) -> RecepcionOut:
    """Valida los códigos, guarda el documento y **suma las existencias**.

    Después aprende del documento, si aporta señal. Ese último paso es
    best-effort a propósito: la recepción ya está guardada y confirmada, así
    que un fallo aprendiendo no debe deshacerla.
    """
    recepcion = await recepcion_service.crear(
        db, datos, creado_por=admin.username, admin_id=admin.id
    )

    await _aprender_del_documento(db, datos, admin.username)

    anotar(
        request,
        detalle=f"{datos.proveedor or 'sin proveedor'} · {len(datos.items)} partida(s)",
    )
    return RecepcionOut.model_validate(recepcion)


async def _aprender_del_documento(
    db: AsyncSession, datos: RecepcionCrear, usuario: str
) -> None:
    """Recicla el documento confirmado como ejemplo del clasificador.

    Se traga cualquier excepción: es la misma excusa que la bitácora, y por el
    mismo motivo. La recepción del usuario ya se completó y ya se le respondió;
    perder un ejemplo es malo, deshacer una entrada de almacén por no poder
    aprender de ella lo es mucho más.
    """
    if datos.foto_id is None or not datos.ocr_ok:
        return

    try:
        foto = await recepcion_service.obtener_foto(db, datos.foto_id)

        # El texto OCR de ESTA foto no viaja de vuelta desde el navegador: se
        # vuelve a leer para no guardar en el corpus un dato que el cliente
        # podría haber alterado. Es CPU-bound, así que va a un hilo.
        texto = await asyncio.to_thread(
            ocr_recepciones.texto_ocr_desde_imagen, foto.imagen
        )

        json_esperado = {
            "proveedor": datos.proveedor,
            "folio": datos.folio,
            "fecha": datos.fecha.isoformat() if datos.fecha else None,
            "items": [
                {"codigo": item.codigo, "cantidad": item.cantidad}
                for item in datos.items
            ],
        }

        if datos.nuevo_formato:
            await plantilla_service.registrar_formato(
                db,
                nombre=datos.nuevo_formato,
                imagen=foto.imagen,
                tipo_mime=foto.tipo,
                texto_ocr=texto,
                json_esperado=json_esperado,
                creado_por=usuario,
            )
        elif datos.tipo_documento != TIPO_DESCONOCIDO:
            await plantilla_service.aprender(
                db,
                slug=datos.tipo_documento,
                imagen=foto.imagen,
                tipo_mime=foto.tipo,
                texto_ocr=texto,
                json_esperado=json_esperado,
            )

        await db.commit()
    except Exception:
        logger.warning(
            "No se pudo aprender del documento; la recepción ya se guardó",
            exc_info=True,
        )
        await db.rollback()


# --- Rutas paramétricas ----------------------------------------------------
# Van AL FINAL: /{recepcion_id} es un catch-all y taparía todo lo de arriba.


@router.get(
    "/recepciones/{recepcion_id}",
    response_model=RecepcionOut,
    summary="Detalle de una recepción",
)
async def obtener_recepcion(
    recepcion_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> RecepcionOut:
    return RecepcionOut.model_validate(
        await recepcion_service.obtener(db, recepcion_id)
    )
