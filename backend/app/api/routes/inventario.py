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
from typing import Any

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
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import obtener_admin_actual, requiere
from app.core.bitacora import anotar
from app.db.session import SessionLocal, get_db
from app.core.constants import CATEGORIAS_INSUMO, CATEGORIAS_VALIDAS
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio
from app.models.admin_user import AdminUser
from app.models.insumo import ESTADOS_FILTRABLES, Insumo
from app.models.recepcion import Recepcion
from app.schemas.catalogo import (
    CatalogoCategorias,
    InsumoOut,
    InsumosPaginados,
)
from app.schemas.recepcion import (
    EstadoSesionOut,
    RecepcionCrear,
    RecepcionOut,
    RecepcionesPaginadas,
    ResultadoOcr,
    SesionQrOut,
    TipoDocumento,
)
from app.services import (
    espejo_formatos,
    insumo_service,
    ocr_recepciones,
    plantilla_service,
    recepcion_service,
)
from app.services.ocr_recepciones import TIPO_DESCONOCIDO, ResultadoExtraccion

logger = logging.getLogger(__name__)

#: Motivos por los que un documento no deja ejemplo. Van en español y salen en
#: la respuesta: antes se perdían en el log y el operador no sabía que su
#: formato no se había guardado.
SIN_LECTURA_IA = (
    "La recepción se guardó, pero el formato no se aprendió: la IA no pudo "
    "leer este documento."
)
FALLO_APRENDIZAJE = (
    "La recepción se guardó, pero no se pudo aprender el formato. Revisa los "
    "registros del servidor."
)

router = APIRouter(
    prefix="/inventario",
    tags=["inventario"],
    dependencies=[Depends(requiere("inventario"))],
)

async def _respuesta_ocr(
    foto_id: uuid.UUID, resultado: ResultadoExtraccion, db: AsyncSession
) -> ResultadoOcr:
    """Traduce el resultado del pipeline a lo que consume el formulario.

    Se responde 200 aunque ``ocr_ok`` sea falso: la foto ya está guardada y el
    formulario abre en captura manual. Un código de error haría que el
    frontend tratara como fallo lo que en realidad es "hazlo a mano".

    Aquí se resuelve además a qué insumo apunta cada partida: un código puede
    amparar varios productos, y el formulario necesita las descripciones para
    ofrecerlas.
    """
    datos = resultado.datos or {}
    conocido = resultado.tipo_documento != TIPO_DESCONOCIDO

    items = datos.get("items") or []
    if not isinstance(items, list):
        items = []

    limpios = [item for item in items if isinstance(item, dict)]

    return ResultadoOcr(
        foto_id=foto_id,
        ocr_ok=resultado.ocr_ok,
        tipo_documento=resultado.tipo_documento,
        tipo_conocido=conocido,
        tipo_nombre=await _nombre_del_formato(resultado.tipo_documento, db)
        if conocido
        else None,
        proveedor=datos.get("proveedor"),
        folio=datos.get("folio"),
        fecha=datos.get("fecha"),
        items=await _con_candidatos(limpios, db),
        advertencias=resultado.advertencias,
        # `datos` y no los ítems enriquecidos: `ocr_raw` promete ser lo que
        # devolvió la IA SIN las correcciones ni los añadidos de nadie, y es
        # lo que después permite auditar qué leyó contra qué se corrigió.
        ocr_raw=datos or None,
        error=resultado.error,
    )


async def _nombre_del_formato(slug: str, db: AsyncSession) -> str | None:
    """El nombre legible de un formato, a partir de su identificador.

    El clasificador devuelve el slug, que es lo que la pantalla enseñaba: un
    operador no tiene por qué leer `mgpharma_remision` para saber que el
    sistema reconoció su remisión.
    """
    try:
        for tipo in await plantilla_service.listar_tipos(db):
            if tipo["slug"] == slug:
                return tipo["nombre"]
    except Exception:
        logger.warning("No se pudo resolver el nombre del formato", exc_info=True)
    return None


async def _con_candidatos(
    items: list[dict[str, Any]], db: AsyncSession
) -> list[dict[str, Any]]:
    """Añade a cada partida las descripciones de su código y la elegida.

    Los candidatos viajan en la misma respuesta y no en una segunda vuelta del
    navegador por dos razones: una petición menos por documento, y sobre todo
    porque el formulario salta al primer campo en ámbar a los 300 ms de
    pintarse — si los candidatos llegaran después, el foco caería en el campo
    equivocado.

    Nada de esto puede tumbar la extracción: corre fuera de la red de
    `extraer()` y fuera del presupuesto de tiempo, así que un fallo aquí
    convertiría el contrato "200 con ocr_ok:false" en un 500 opaco. Si algo
    sale mal, la partida se queda sin resolver y el operador elige.
    """
    if not items:
        return items

    try:
        catalogo = await insumo_service.mapa_por_codigo(
            db,
            {
                str(item["codigo"]).strip().lower()
                for item in items
                if isinstance(item.get("codigo"), str) and item["codigo"].strip()
            },
        )
    except Exception:
        logger.warning("No se pudieron resolver los códigos leídos", exc_info=True)
        return items

    enriquecidos: list[dict[str, Any]] = []

    for item in items:
        # Copia: mutar el original contaminaría `ocr_raw`, que apunta al mismo
        # diccionario y se guarda como la lectura cruda de la IA.
        copia = dict(item)
        codigo = item.get("codigo")
        candidatos = (
            catalogo.get(str(codigo).strip().lower(), [])
            if isinstance(codigo, str)
            else []
        )

        copia["candidatos"] = [
            {
                "id": str(insumo.id),
                "descripcion": insumo.descripcion,
                "unidad_medida": insumo.unidad_medida,
                "piezas_por_empaque": insumo.piezas_por_empaque,
            }
            for insumo in candidatos
        ]
        copia["insumo_id"] = await _elegir_insumo(item.get("descripcion"), candidatos)
        enriquecidos.append(copia)

    return enriquecidos


async def _elegir_insumo(descripcion: Any, candidatos: list[Insumo]) -> str | None:
    """Cuál de las descripciones del código se parece a la de la remisión.

    Con un solo candidato no hay nada que decidir. Con varios, se compara y
    solo se elige si el parecido es claro; si no, devuelve ``None`` y el campo
    queda en ámbar para que el operador elija. Prefiere preguntar antes que
    sumarle la existencia al producto equivocado.
    """
    if len(candidatos) == 1:
        return str(candidatos[0].id)

    if not isinstance(descripcion, str) or not descripcion.strip():
        return None

    try:
        # En un hilo: TF-IDF es CPU-bound y bloquearía el bucle de eventos.
        indice, _, _ = await asyncio.to_thread(
            ocr_recepciones.mejor_coincidencia,
            descripcion,
            [insumo.descripcion for insumo in candidatos],
        )
    except Exception:
        logger.warning("El emparejado de descripción falló", exc_info=True)
        return None

    return str(candidatos[indice].id) if indice is not None else None


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
    return await _respuesta_ocr(foto.id, resultado, db)


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
    return await _respuesta_ocr(foto.id, resultado, db)


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
    que un fallo aprendiendo no debe deshacerla — pero **sí se dice**, en el
    campo `aviso`, para que el operador no se quede creyendo que su formato se
    guardó cuando no fue así.
    """
    recepcion = await recepcion_service.crear(
        db, datos, creado_por=admin.username, admin_id=admin.id
    )

    aviso = await _aprender_del_documento(recepcion.id, datos, admin.username)

    anotar(
        request,
        detalle=f"{datos.proveedor or 'sin proveedor'} · {len(datos.items)} partida(s)",
    )

    salida = RecepcionOut.model_validate(recepcion)
    salida.aviso = aviso
    # El sellado ocurre en la otra sesión, así que el objeto de esta no lo ve.
    if aviso is None and datos.nuevo_formato:
        salida.tipo_documento = ocr_recepciones.slugify(datos.nuevo_formato)
    return salida


async def _aprender_del_documento(
    recepcion_id: uuid.UUID, datos: RecepcionCrear, usuario: str
) -> str | None:
    """Recicla el documento confirmado como ejemplo del clasificador.

    Devuelve ``None`` si aprendió, o **el motivo por el que no**. Antes se lo
    tragaba entero: los mensajes que el servicio ya prepara —«ya existe un
    formato con ese nombre», «este formato ya tiene sus ejemplos»— nunca
    llegaban a la pantalla, y el operador solo veía que su formato no aparecía
    por ningún lado.

    Corre en **su propia sesión**, no en la de la petición. La regla de fondo
    no cambia —la recepción ya está confirmada y un fallo aprendiendo no puede
    deshacerla— pero antes su `rollback` expiraba el objeto `recepcion` que la
    ruta estaba a punto de serializar, y eso reventaba como `MissingGreenlet`:
    un 500 con la recepción ya guardada, que el panel leía como fallo y que al
    reintentar duplicaba la entrada de almacén.
    """
    if datos.foto_id is None:
        return None

    if not datos.ocr_ok:
        # Sin lectura de la IA no hay nada que enseñar, y es el caso más
        # frecuente cuando Ollama está caído: conviene decirlo.
        logger.info("No se aprende del documento: la IA no pudo leerlo")
        return SIN_LECTURA_IA

    async with SessionLocal() as db:
        try:
            foto = await recepcion_service.obtener_foto(db, datos.foto_id)

            # El texto OCR de ESTA foto no viaja de vuelta desde el navegador:
            # se vuelve a leer para no guardar en el corpus un dato que el
            # cliente podría haber alterado. Es CPU-bound, así que va a un hilo.
            texto = await asyncio.to_thread(
                ocr_recepciones.texto_ocr_desde_imagen, foto.imagen
            )

            json_esperado = {
                "proveedor": datos.proveedor,
                "folio": datos.folio,
                "fecha": datos.fecha.isoformat() if datos.fecha else None,
                # La descripción va **como la leyó de la hoja**, no la del
                # catálogo: el ejemplo le enseña al modelo qué extraer del
                # texto, y con la del catálogo le estaríamos enseñando a
                # inventar.
                "items": [
                    {
                        "codigo": item.codigo,
                        "descripcion": item.descripcion,
                        "cantidad": item.cantidad,
                    }
                    for item in datos.items
                ],
            }

            slug_aprendido: str | None = None
            nombre_formato = ""

            if datos.nuevo_formato:
                plantilla = await plantilla_service.registrar_formato(
                    db,
                    nombre=datos.nuevo_formato,
                    imagen=foto.imagen,
                    tipo_mime=foto.tipo,
                    texto_ocr=texto,
                    json_esperado=json_esperado,
                    creado_por=usuario,
                )
                # El documento que estrena un formato queda sellado con él. Sin
                # esto se guardaba como "desconocido" y el historial no lo
                # encontraba bajo el formato que él mismo definió.
                await db.execute(
                    update(Recepcion)
                    .where(Recepcion.id == recepcion_id)
                    .values(tipo_documento=plantilla.slug)
                )
                slug_aprendido = plantilla.slug
                nombre_formato = plantilla.nombre
            elif datos.tipo_documento != TIPO_DESCONOCIDO:
                await plantilla_service.aprender(
                    db,
                    slug=datos.tipo_documento,
                    imagen=foto.imagen,
                    tipo_mime=foto.tipo,
                    texto_ocr=texto,
                    json_esperado=json_esperado,
                )
                slug_aprendido = datos.tipo_documento
                nombre_formato = await _nombre_del_formato(datos.tipo_documento, db) or ""

            await db.commit()

            # El espejo va DESPUÉS del commit: refleja lo que la base ya
            # aceptó, nunca al revés. Y no lanza, así que no hace falta
            # protegerlo aquí.
            if slug_aprendido is not None:
                espejo_formatos.guardar_ejemplo(
                    slug=slug_aprendido,
                    nombre=nombre_formato or slug_aprendido,
                    imagen=foto.imagen,
                    tipo_mime=foto.tipo,
                    texto_ocr=texto,
                    json_esperado=json_esperado,
                )

            return None

        except (ErrorDeNegocio, ConflictoDeNegocio) as exc:
            # Son reglas de negocio con mensaje en español ya escrito: se
            # devuelven tal cual en vez de morir en el log.
            await db.rollback()
            logger.info("No se aprendió del documento: %s", exc)
            return str(exc)

        except Exception:
            logger.warning(
                "No se pudo aprender del documento; la recepción ya se guardó",
                exc_info=True,
            )
            await db.rollback()
            return FALLO_APRENDIZAJE


# --- Stock -----------------------------------------------------------------
#
# La existencia vive en el catálogo, pero la pantalla que la consulta es una
# pestaña de Inventario, y los dos módulos tienen permisos separados. Colgar
# esto de `/api/catalogo` habría dejado la pestaña en 403 para quien tiene
# `inventario` y no `catalogo` —que es justo el caso del almacenista—, así que
# los endpoints se sirven desde aquí y reutilizan el servicio del catálogo tal
# cual. Son de LECTURA: corregir la existencia sigue siendo cosa del catálogo,
# con su propio permiso.


@router.get(
    "/stock/categorias",
    response_model=CatalogoCategorias,
    summary="Categorías para el filtro de Stock",
)
async def categorias_stock() -> CatalogoCategorias:
    """Las mismas del catálogo, servidas bajo el permiso de inventario.

    Se repite el endpoint en vez de que el frontend llame al del catálogo
    porque aquel exige otro módulo: el select se quedaría vacío para siempre
    con un 403 que nadie ve.
    """
    return CatalogoCategorias(categorias=list(CATEGORIAS_INSUMO))


@router.get(
    "/insumos",
    response_model=list[InsumoOut],
    summary="Insumos que comparten un código exacto",
)
async def insumos_por_codigo(
    codigo: str = Query(min_length=1, max_length=150),
    db: AsyncSession = Depends(get_db),
) -> list[InsumoOut]:
    """Las descripciones que ampara un código, para la captura de recepciones.

    Existe aparte del buscador del catálogo por dos razones. La primera es el
    permiso: aquel exige el módulo `catalogo` y esta es una pantalla de
    `inventario`, así que al almacenista le respondía 403 y la captura leía ese
    fallo como "el código no existe". La segunda es que la búsqueda del
    catálogo es parcial y paginada de 50: un código corto y común podía dejar
    fuera de la primera página justo a los homónimos que aquí importan.
    """
    insumos = await insumo_service.por_codigo(db, codigo)
    return [InsumoOut.model_validate(insumo) for insumo in insumos]


@router.get(
    "/stock",
    response_model=InsumosPaginados,
    summary="Existencias de todos los insumos del catálogo",
)
async def listar_stock(
    busqueda: str | None = Query(default=None, max_length=100),
    categoria: str | None = Query(default=None, max_length=30),
    estado: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
) -> InsumosPaginados:
    """Página de 50, ordenada por código.

    El semáforo y el filtro por estado los resuelve la base (ver
    ``models/insumo.EXPRESIONES_ESTADO``): clasificar en Python rompería el
    total y la paginación.
    """
    if categoria and categoria not in CATEGORIAS_VALIDAS:
        raise ErrorDeNegocio("Esa categoría no existe.")

    if estado and estado not in ESTADOS_FILTRABLES:
        raise ErrorDeNegocio("Ese estado no existe.")

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
