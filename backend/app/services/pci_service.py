"""Mantenimiento mensual al sistema de protección contra incendios.

Una pregunta al mes —¿se hizo?— y dos caminos: si sí, se exige la fecha, el
reporte del proveedor y evidencia fotográfica; si no, se exige el motivo. Lo
que distingue a este control de los demás es que **no se puede dejar sin
contestar**: cuando un mes cierra sin respuesta, ``cerrar_meses_vencidos()``
levanta la fila con el motivo en blanco y el panel la reclama hasta que alguien
la explique.

Vive en su propio módulo y no dentro de ``control_service`` por el mismo
criterio que ``cierre_service``: aquel ya pasa de mil líneas y esto no comparte
con él ni tablas ni validaciones.
"""

import re
import uuid
from collections import defaultdict
from datetime import date, datetime
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.controles_catalogo import (
    MAX_BYTES_REPORTE_PCI,
    MAX_FOTOS_PCI,
    PCI_PRIMER_MES,
)
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.models.admin_user import AdminUser
from app.models.control import FotoControl, RegistroPciMtto
from app.services.control_service import (
    Evidencia,
    _construir_fotos,
    validar_cantidad_fotos,
)
from app.services.rondin_service import ahora_local

#: Quién figura como responsable cuando la fila la levanta la tarea periódica.
#: Se guarda un nombre y no NULL para no abrir una rama en el Excel ni en la
#: tabla del panel, que esperan siempre un responsable.
RESPONSABLE_SISTEMA = "sistema"

#: Tope de meses que una sola pasada puede cerrar. Si el sistema estuvo años
#: apagado, más vale cerrar de a poco que soltar cien INSERT de golpe.
MAX_MESES_A_CERRAR = 120

#: Nombres de los meses en español. El locale del contenedor es C, así que
#: `strftime("%B")` devolvería "September".
MESES: tuple[str, ...] = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

#: Tipos que se reconocen por la extensión del archivo. Lo que no esté aquí se
#: guarda igual —el control acepta cualquier formato a propósito— pero como
#: `application/octet-stream`.
TIPOS_POR_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".xls": "application/vnd.ms-excel",
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".txt": "text/plain",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

TIPO_GENERICO = "application/octet-stream"

#: Caracteres que no pueden viajar en el nombre de un archivo descargado.
_PROHIBIDOS = re.compile(r'[\x00-\x1f\x7f"\\/]')


def nombre_de_mes(mes: int) -> str:
    """El nombre del mes en español, para los mensajes y el Excel."""
    return MESES[mes - 1] if 1 <= mes <= 12 else str(mes)


def _periodo(anio: int, mes: int) -> str:
    """Cómo se nombra un periodo en los mensajes de error."""
    return f"{nombre_de_mes(mes)} de {anio}"


def sanear_nombre(nombre: str | None) -> str:
    """Deja un nombre de archivo que se pueda poner en una cabecera HTTP.

    **No es cosmético.** El nombre lo pone quien sube el archivo y termina
    dentro del ``Content-Disposition`` de la descarga: sin sanearlo, unas
    comillas o un salto de línea en el nombre permiten inyectar cabeceras en la
    respuesta. Se descarta cualquier ruta —tanto ``/`` como ``\\`` y los
    ``..``—, se quitan los caracteres de control y las comillas, y se recorta a
    lo que cabe en la columna.
    """
    crudo = (nombre or "").replace("\\", "/")
    base = PurePosixPath(crudo).name
    limpio = _PROHIBIDOS.sub("", base).strip().strip(".")
    return limpio[:255] or "reporte"


def validar_reporte(contenido: bytes, nombre: str | None) -> tuple[bytes, str, str]:
    """Comprueba el reporte adjunto y decide con qué tipo se servirá.

    El control acepta **cualquier formato** a propósito: el proveedor entrega lo
    que entrega, y rechazar un ``.odt`` porque no está en una lista solo
    conseguiría que nadie suba nada. Lo que no se hace es confiar en el
    ``Content-Type`` que manda el navegador —en Windows y Android llega
    ``application/octet-stream`` para un ``.docx`` con toda naturalidad—, así
    que el tipo se deriva de la extensión y lo desconocido se guarda como
    genérico.

    Que se acepte cualquier cosa obliga a servirla siempre como ``attachment``
    y con ``nosniff`` (ver la ruta de descarga): el archivo sale del mismo
    origen que el panel y con la cookie de sesión, así que un ``.svg`` o un
    ``.html`` servido *inline* sería XSS almacenado.
    """
    if not contenido:
        raise ErrorDeNegocio("El reporte de mantenimiento llegó vacío.")

    if len(contenido) > MAX_BYTES_REPORTE_PCI:
        tope = MAX_BYTES_REPORTE_PCI // (1024 * 1024)
        raise ErrorDeNegocio(
            f"El reporte de mantenimiento no debe pesar más de {tope} MB."
        )

    limpio = sanear_nombre(nombre)
    extension = PurePosixPath(limpio).suffix.lower()
    return contenido, limpio, TIPOS_POR_EXTENSION.get(extension, TIPO_GENERICO)


def meses_a_cerrar(
    primer_mes: tuple[int, int],
    ahora: datetime,
    existentes: set[tuple[int, int]],
    *,
    margen_horas: int = 1,
) -> list[tuple[int, int]]:
    """Meses ya cerrados que todavía no tienen registro, del más viejo al más nuevo.

    Función pura, y a propósito: es la única parte de la vigilancia automática
    que se puede probar sin esperar a que pase un mes de verdad.

    Dos reglas que parecen detalles y no lo son:

    - **El mes en curso nunca se cierra.** El límite es exclusivo; si no, el día
      primero se cerraría el mes que apenas empieza.
    - **Hay un margen de gracia** de una hora sobre el cambio de mes. Sin él, el
      operador que está subiendo un reporte de 10 MB a las 23:59:40 del último
      día pierde la subida contra el cierre de las 00:00, y ya no podría
      rehacerla sin permiso de edición.

    ``ahora`` tiene que venir en hora de la planta. En UTC, las 23:00 del último
    día del mes ya son el día 1 del siguiente y el mes se cerraría seis horas
    antes de tiempo.
    """
    corte = ahora.timestamp() - margen_horas * 3600
    momento = datetime.fromtimestamp(corte, tz=ahora.tzinfo)

    anio, mes = primer_mes
    pendientes: list[tuple[int, int]] = []

    # Se cierran los meses estrictamente anteriores al del corte: el del corte
    # es "el mes en curso" una vez descontado el margen.
    while (anio, mes) < (momento.year, momento.month):
        if (anio, mes) not in existentes:
            pendientes.append((anio, mes))
            if len(pendientes) >= MAX_MESES_A_CERRAR:
                break
        mes += 1
        if mes > 12:
            anio, mes = anio + 1, 1

    return pendientes


async def _ids_de_fotos(
    db: AsyncSession, registros: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Identificadores de las fotos de cada registro, sin traer las imágenes."""
    if not registros:
        return {}

    filas = await db.execute(
        select(FotoControl.id, FotoControl.pci_id)
        .where(FotoControl.pci_id.in_(registros))
        .order_by(FotoControl.orden)
    )

    agrupadas: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for foto_id, propietario in filas.all():
        agrupadas[propietario].append(foto_id)
    return dict(agrupadas)


# Columnas del listado. Se enumeran a mano para NO arrastrar `reporte`: son
# hasta 10 MB por fila y un año son doce.
_COLUMNAS = (
    RegistroPciMtto.id,
    RegistroPciMtto.anio,
    RegistroPciMtto.mes,
    RegistroPciMtto.fecha,
    RegistroPciMtto.realizado,
    RegistroPciMtto.motivo,
    RegistroPciMtto.automatico,
    RegistroPciMtto.reporte_nombre,
    RegistroPciMtto.reporte_tamano,
    RegistroPciMtto.responsable,
    RegistroPciMtto.creado_at,
    RegistroPciMtto.actualizado_at,
)


async def listar(db: AsyncSession, anio: int) -> list[dict]:
    """Los registros de un año, del mes más nuevo al más viejo."""
    filas = (
        await db.execute(
            select(*_COLUMNAS)
            .where(RegistroPciMtto.anio == anio)
            .order_by(RegistroPciMtto.mes.desc())
        )
    ).all()

    fotos = await _ids_de_fotos(db, [fila.id for fila in filas])

    return [
        {
            "id": fila.id,
            "anio": fila.anio,
            "mes": fila.mes,
            "fecha": fila.fecha,
            "realizado": fila.realizado,
            "motivo": fila.motivo,
            "automatico": fila.automatico,
            "tiene_reporte": fila.reporte_nombre is not None,
            "reporte_nombre": fila.reporte_nombre,
            "reporte_tamano": fila.reporte_tamano,
            "responsable": fila.responsable,
            "fotos": fotos.get(fila.id, []),
            "creado_at": fila.creado_at,
            "actualizado_at": fila.actualizado_at,
        }
        for fila in filas
    ]


async def anios_con_registros(db: AsyncSession) -> list[int]:
    """Años que tienen al menos un registro, para el filtro. En SQL, no en Python."""
    filas = await db.execute(
        select(RegistroPciMtto.anio)
        .distinct()
        .order_by(RegistroPciMtto.anio.desc())
    )
    return [fila[0] for fila in filas.all()]


async def meses_pendientes(db: AsyncSession) -> list[dict]:
    """Meses que el sistema cerró y nadie ha explicado todavía.

    Se devuelven **todos**, de todos los años y del más viejo al más nuevo, y no
    solo el último: con un hueco de tres meses, tratarlos de uno en uno dejaría
    dos invisibles para siempre.
    """
    filas = await db.execute(
        select(RegistroPciMtto.anio, RegistroPciMtto.mes)
        .where(RegistroPciMtto.automatico.is_(True))
        .where(RegistroPciMtto.motivo.is_(None))
        .order_by(RegistroPciMtto.anio, RegistroPciMtto.mes)
    )
    return [{"anio": anio, "mes": mes} for anio, mes in filas.all()]


async def _buscar(
    db: AsyncSession, anio: int, mes: int
) -> RegistroPciMtto | None:
    """El registro de un mes, con sus fotos ya cargadas.

    El ``selectinload`` no es opcional: `corregir()` reemplaza la colección, y
    navegar una relación perezosa desde una sesión asíncrona revienta con
    ``MissingGreenlet``. La columna del reporte sigue diferida, que es lo que
    evita arrastrar diez megabytes en cada corrección.
    """
    return (
        await db.execute(
            select(RegistroPciMtto)
            .options(selectinload(RegistroPciMtto.fotos))
            .where(RegistroPciMtto.anio == anio)
            .where(RegistroPciMtto.mes == mes)
        )
    ).scalar_one_or_none()


def _validar_periodo(anio: int, mes: int, hoy: date) -> None:
    """El mes tiene que existir, haber empezado, y no ser anterior al estreno."""
    if not 1 <= mes <= 12:
        raise ErrorDeNegocio("El mes debe estar entre 1 y 12.")

    if (anio, mes) < PCI_PRIMER_MES:
        primero = _periodo(*PCI_PRIMER_MES)
        raise ErrorDeNegocio(f"El control arranca en {primero}.")

    if (anio, mes) > (hoy.year, hoy.month):
        raise ErrorDeNegocio("Todavía no se puede registrar un mes que no ha llegado.")


def _validar_captura(
    *,
    realizado: bool,
    fecha: date | None,
    motivo: str,
    fotos: list[tuple[bytes, str]],
    reporte: tuple[bytes, str, str] | None,
) -> None:
    """Las dos ramas de la única pregunta del control."""
    if realizado:
        if fecha is None:
            raise ErrorDeNegocio("Captura la fecha en que se realizó el mantenimiento.")
        if reporte is None:
            raise ErrorDeNegocio("Adjunta el reporte de mantenimiento.")
        if not fotos:
            raise ErrorDeNegocio("Agrega al menos una foto de evidencia.")
        if motivo:
            raise ErrorDeNegocio(
                "El motivo solo se captura cuando el mantenimiento no se realizó."
            )
        validar_cantidad_fotos(len(fotos), "Evidencia del mantenimiento")
        return

    if not motivo:
        raise ErrorDeNegocio("Captura el motivo por el que no se realizó.")
    # Se rechaza en lugar de ignorar en silencio: quien adjuntó algo creía que
    # se iba a guardar.
    if reporte is not None:
        raise ErrorDeNegocio(
            "Un mes sin mantenimiento no lleva reporte. Quítalo o marca que sí se realizó."
        )
    if fotos:
        raise ErrorDeNegocio(
            "Un mes sin mantenimiento no lleva evidencia. Quítala o marca que sí se realizó."
        )


async def registrar(
    db: AsyncSession,
    *,
    anio: int,
    mes: int,
    realizado: bool,
    fecha: date | None,
    motivo: str,
    fotos: list[tuple[bytes, str]],
    reporte: tuple[bytes, str, str] | None,
    admin: AdminUser,
    hoy: date,
) -> RegistroPciMtto:
    """Da de alta el registro de un mes.

    Un mes que el sistema ya cerró en automático **no se sobrescribe desde
    aquí**: la solicitud urgente solo captura el motivo, y arreglar un cierre
    que en realidad sí se hizo es tarea de la corrección, que exige permiso de
    edición.
    """
    _validar_periodo(anio, mes, hoy)
    limpio = motivo.strip()
    _validar_captura(
        realizado=realizado, fecha=fecha, motivo=limpio, fotos=fotos, reporte=reporte
    )

    registro = RegistroPciMtto(
        anio=anio,
        mes=mes,
        fecha=fecha if realizado else None,
        realizado=realizado,
        motivo=limpio or None,
        automatico=False,
        reporte=reporte[0] if reporte else None,
        reporte_nombre=reporte[1] if reporte else None,
        reporte_tipo=reporte[2] if reporte else None,
        reporte_tamano=len(reporte[0]) if reporte else None,
        responsable=admin.username,
        admin_id=admin.id,
        fotos=_construir_fotos(fotos),
    )

    db.add(registro)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # uq_pci_anio_mes. Se comprueba con el choque y no con un SELECT previo
        # porque dos capturas simultáneas pasarían ambas la prueba, y porque la
        # tarea automática compite por la misma llave.
        raise ConflictoDeNegocio(
            f"El mantenimiento de {_periodo(anio, mes)} ya está registrado. "
            "Corrígelo si necesitas cambiarlo."
        ) from exc

    return registro


async def guardar_motivo(
    db: AsyncSession,
    *,
    anio: int,
    mes: int,
    motivo: str,
    admin: AdminUser,
    actualizando: bool,
) -> RegistroPciMtto:
    """Explica un mes sin mantenimiento.

    Se parte en dos caminos por la misma razón que el cierre de hallazgos:
    rellenar un hueco vacío es parte de capturar y lo puede hacer cualquiera con
    acceso al módulo, mientras que pisar el texto que escribió otra persona
    exige permiso de edición. Esa distinción la aplica la capa HTTP; aquí solo
    se comprueba que el estado coincida con la intención.
    """
    limpio = motivo.strip()
    if not limpio:
        raise ErrorDeNegocio("Captura el motivo por el que no se realizó.")

    registro = await _buscar(db, anio, mes)
    if registro is None:
        raise RecursoNoEncontrado("No hay registro de ese mes.")

    if registro.realizado:
        raise ErrorDeNegocio(
            f"El mantenimiento de {_periodo(anio, mes)} sí se realizó: no lleva motivo."
        )

    if actualizando and registro.motivo is None:
        raise RecursoNoEncontrado("Ese mes todavía no tiene un motivo que corregir.")

    if not actualizando and registro.motivo is not None:
        raise ConflictoDeNegocio(
            f"El motivo de {_periodo(anio, mes)} ya está capturado."
        )

    registro.motivo = limpio
    registro.actualizado_at = ahora_local()
    registro.responsable = admin.username
    registro.admin_id = admin.id

    await db.commit()
    return registro


async def corregir(
    db: AsyncSession,
    *,
    anio: int,
    mes: int,
    realizado: bool,
    fecha: date | None,
    motivo: str,
    fotos: list[tuple[bytes, str]],
    reporte: tuple[bytes, str, str] | None,
    conserva_reporte: bool,
    admin: AdminUser,
) -> RegistroPciMtto:
    """Rehace el registro de un mes ya capturado.

    Es la única forma de arreglar un mes: **no hay borrado**. Borrar un cierre
    automático no serviría de nada, porque la tarea periódica lo volvería a
    levantar en menos de una hora con el motivo otra vez en blanco.

    Es también la salida para el caso incómodo: el sistema cerró septiembre en
    rojo y resulta que el mantenimiento sí se hizo el día 28. Quien tenga
    permiso de edición puede pasarlo a "sí" con su fecha, su reporte y sus
    fotos.
    """
    registro = await _buscar(db, anio, mes)
    if registro is None:
        raise RecursoNoEncontrado("No hay registro de ese mes.")

    limpio = motivo.strip()

    # Al corregir sin tocar el adjunto, el reporte que ya estaba cuenta como
    # presente: si no, corregir una fecha obligaría a volver a subir el PDF.
    reporte_efectivo = reporte
    if reporte is None and conserva_reporte and registro.reporte_nombre is not None:
        reporte_efectivo = (b"", registro.reporte_nombre, registro.reporte_tipo or "")

    _validar_captura(
        realizado=realizado,
        fecha=fecha,
        motivo=limpio,
        fotos=fotos,
        reporte=reporte_efectivo,
    )

    registro.realizado = realizado
    registro.fecha = fecha if realizado else None
    registro.motivo = limpio or None
    # Deja de ser un cierre del sistema en cuanto una persona lo toca.
    registro.automatico = False
    registro.responsable = admin.username
    registro.admin_id = admin.id
    registro.actualizado_at = ahora_local()

    if reporte is not None:
        registro.reporte, registro.reporte_nombre, registro.reporte_tipo = reporte
        registro.reporte_tamano = len(reporte[0])
    elif not realizado:
        registro.reporte = None
        registro.reporte_nombre = None
        registro.reporte_tipo = None
        registro.reporte_tamano = None

    if fotos:
        registro.fotos = _construir_fotos(fotos)
    elif not realizado:
        registro.fotos = []

    await db.commit()
    return registro


async def obtener_reporte(
    db: AsyncSession, anio: int, mes: int
) -> tuple[bytes, str, str]:
    """El documento adjunto. Único sitio que toca la columna del blob."""
    fila = (
        await db.execute(
            select(
                RegistroPciMtto.reporte,
                RegistroPciMtto.reporte_nombre,
                RegistroPciMtto.reporte_tipo,
            )
            .where(RegistroPciMtto.anio == anio)
            .where(RegistroPciMtto.mes == mes)
        )
    ).one_or_none()

    if fila is None or fila.reporte is None:
        raise RecursoNoEncontrado("Ese mes no tiene reporte adjunto.")

    return fila.reporte, fila.reporte_nombre or "reporte", fila.reporte_tipo or TIPO_GENERICO


async def evidencias(db: AsyncSession, anio: int) -> list[Evidencia]:
    """Las fotos del año, listas para la hoja de evidencias del Excel."""
    filas = await db.execute(
        select(
            RegistroPciMtto.anio,
            RegistroPciMtto.mes,
            RegistroPciMtto.fecha,
            RegistroPciMtto.responsable,
            FotoControl.imagen,
        )
        .join(FotoControl, FotoControl.pci_id == RegistroPciMtto.id)
        .where(RegistroPciMtto.anio == anio)
        .order_by(RegistroPciMtto.mes, FotoControl.orden)
    )

    return [
        Evidencia(
            # El Excel imprime una fecha; el día 1 sirve de ancla del periodo
            # cuando el registro no trae fecha de captura.
            fecha=fila.fecha or date(fila.anio, fila.mes, 1),
            detalle=nombre_de_mes(fila.mes).capitalize(),
            responsable=fila.responsable,
            imagen=fila.imagen,
        )
        for fila in filas.all()
    ]


async def cerrar_meses_vencidos(db: AsyncSession, ahora: datetime) -> int:
    """Levanta el registro de los meses que cerraron sin respuesta.

    Devuelve cuántos cerró. Se inserta **un mes por transacción** a propósito:
    la restricción ``uq_pci_anio_mes`` es el candado que evita que los cuatro
    workers de uvicorn creen la misma fila cuatro veces, y si un choque
    abortara la transacción entera se llevaría por delante los meses que
    todavía faltan por cerrar.
    """
    existentes = {
        (anio, mes)
        for anio, mes in (
            await db.execute(select(RegistroPciMtto.anio, RegistroPciMtto.mes))
        ).all()
    }

    cerrados = 0
    for anio, mes in meses_a_cerrar(PCI_PRIMER_MES, ahora, existentes):
        db.add(
            RegistroPciMtto(
                anio=anio,
                mes=mes,
                fecha=None,
                realizado=False,
                motivo=None,
                automatico=True,
                responsable=RESPONSABLE_SISTEMA,
            )
        )
        try:
            await db.commit()
            cerrados += 1
        except IntegrityError:
            # Otro worker ganó este mes. Se sigue con el siguiente.
            await db.rollback()

    return cerrados


__all__ = [
    "MAX_FOTOS_PCI",
    "PCI_PRIMER_MES",
    "RESPONSABLE_SISTEMA",
    "anios_con_registros",
    "cerrar_meses_vencidos",
    "corregir",
    "evidencias",
    "guardar_motivo",
    "listar",
    "meses_a_cerrar",
    "meses_pendientes",
    "nombre_de_mes",
    "obtener_reporte",
    "registrar",
    "sanear_nombre",
    "validar_reporte",
]
