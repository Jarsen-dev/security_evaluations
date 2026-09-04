"""Control de Extintores: fichas, revisión diaria y avisos de vencimiento.

Es el único control con una **ficha por aparato**. La revisión diaria copia la
forma del checklist —doce puntos, observación y foto obligatorias en NO OK— pero
sobre un extintor identificado, no sobre una hoja de la planta.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any, Final

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.controles_catalogo import (
    MAX_EXTINTORES,
    PUNTOS_EXTINTOR,
    TIPOS_EXTINTOR,
    TIPOS_EXTINTOR_VALIDOS,
    etiqueta_punto_extintor,
)
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.core.fechas import sumar_meses
from app.models.admin_user import AdminUser
from app.models.control import CierreHallazgo, FotoControl
from app.models.extintor import (
    ESTADOS_FILTRABLES,
    MESES_CRITICO,
    Extintor,
    PuntoRevisionExtintor,
    RevisionExtintor,
    estado_vencimiento,
    expresiones_estado,
)
from app.services.control_service import (
    Evidencia,
    _construir_fotos,
    _ids_de_fotos,
    validar_cantidad_fotos,
)
from app.services.rondin_service import ahora_local

#: Renglones por pantalla, igual que el catálogo: la tabla se hojea.
TAMANO_PAGINA: Final[int] = 50

#: Caracteres que LIKE interpreta como comodín, para que buscar "EXT-1%" no
#: traiga el inventario entero.
COMODINES_LIKE = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})

NO_EXISTE: Final[str] = "El extintor no existe."
FOLIO_DUPLICADO: Final[str] = (
    "Ya hay un extintor con ese folio. El folio es lo que distingue a dos "
    "aparatos del mismo modelo en la misma área."
)
YA_REVISADO: Final[str] = (
    "Este extintor ya se revisó hoy. Usa «Corregir revisión» si necesitas "
    "cambiar lo capturado."
)
SIN_REVISION_HOY: Final[str] = "Este extintor todavía no se ha revisado hoy."


def etiquetar(extintor: Extintor) -> str:
    """Cómo se nombra un extintor en la bitácora y en los diálogos."""
    return f"{extintor.folio} · {extintor.tipo} · {extintor.ubicacion}"


# --- Fichas -----------------------------------------------------------------


def _condiciones(
    busqueda: str | None, tipo: str | None, estado: str | None, hoy: date
) -> list[Any]:
    """Traduce los filtros de la pantalla a condiciones de SQL.

    El semáforo se resuelve en la base: clasificarlo en Python rompería el
    conteo y la paginación (regla 4).
    """
    condiciones: list[Any] = []

    if busqueda and busqueda.strip():
        patron = f"%{busqueda.strip().translate(COMODINES_LIKE)}%"
        condiciones.append(
            or_(
                Extintor.folio.ilike(patron, escape="\\"),
                Extintor.modelo.ilike(patron, escape="\\"),
                Extintor.ubicacion.ilike(patron, escape="\\"),
            )
        )

    if tipo:
        condiciones.append(Extintor.tipo == tipo)

    if estado:
        condiciones.append(expresiones_estado(hoy)[estado])

    return condiciones


def _consulta_revision_hoy(hoy: date) -> Select:
    """Sub-consulta con la revisión de hoy de cada extintor.

    Va como LEFT JOIN dentro del listado y no como una consulta por renglón:
    con 160 aparatos serían 160 viajes a la base en cada carga de la tabla.
    """
    return (
        select(
            RevisionExtintor.extintor_id.label("extintor_id"),
            RevisionExtintor.id.label("revision_id"),
            RevisionExtintor.anomalias.label("anomalias"),
            CierreHallazgo.id.label("cierre_id"),
        )
        .outerjoin(
            CierreHallazgo,
            CierreHallazgo.revision_extintor_id == RevisionExtintor.id,
        )
        .where(RevisionExtintor.fecha == hoy)
        .subquery()
    )


async def listar(
    db: AsyncSession,
    *,
    busqueda: str | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    revisado: bool | None = None,
    page: int = 1,
    hoy: date | None = None,
) -> dict[str, Any]:
    """Una página del registro de extintores, con lo que la tabla necesita.

    Cada renglón trae además si ya se revisó hoy, cuántas anomalías salieron y
    si el hallazgo está cerrado: son los tres datos que deciden qué botones
    pinta la fila, y pedirlos aparte serían cincuenta peticiones por página.
    """
    dia = hoy or ahora_local().date()
    page = max(1, page)

    condiciones = _condiciones(busqueda, tipo, estado, dia)
    revision = _consulta_revision_hoy(dia)

    if revisado is True:
        condiciones.append(revision.c.revision_id.is_not(None))
    elif revisado is False:
        condiciones.append(revision.c.revision_id.is_(None))

    base = select(Extintor).outerjoin(
        revision, revision.c.extintor_id == Extintor.id
    )

    # El conteo va aparte del listado: traer todas las filas para contarlas
    # sería justo lo que la regla 4 prohíbe.
    total = await db.scalar(
        select(func.count())
        .select_from(Extintor)
        .outerjoin(revision, revision.c.extintor_id == Extintor.id)
        .where(*condiciones)
    )

    filas = await db.execute(
        base.add_columns(
            revision.c.revision_id,
            revision.c.anomalias,
            revision.c.cierre_id,
        )
        .where(*condiciones)
        # El desempate por `id` no es adorno: sin él las filas se repiten o se
        # pierden entre páginas cuando dos comparten folio ordenable.
        .order_by(func.lower(Extintor.folio), Extintor.id)
        .offset((page - 1) * TAMANO_PAGINA)
        .limit(TAMANO_PAGINA)
    )

    items = [
        {
            "extintor": extintor,
            "estado": estado_vencimiento(extintor.vencimiento, dia),
            "revision_id": revision_id,
            "anomalias_hoy": anomalias,
            "revisado_hoy": revision_id is not None,
            "cierre_hecho": cierre_id is not None,
        }
        for extintor, revision_id, anomalias, cierre_id in filas.all()
    ]

    return {
        "total": total or 0,
        "page": page,
        "size": TAMANO_PAGINA,
        "items": items,
        "revisados_hoy": await contar_revisados(db, dia),
        "registrados": await db.scalar(select(func.count(Extintor.id))) or 0,
    }


async def contar_revisados(db: AsyncSession, dia: date) -> int:
    """Cuántos extintores VIVOS llevan revisión hoy.

    Es el «N de 160» de la cabecera. Se cuenta en SQL y se excluye a los de
    ficha eliminada, o el numerador podría pasar al denominador.
    """
    return (
        await db.scalar(
            select(func.count(RevisionExtintor.id))
            .where(RevisionExtintor.fecha == dia)
            .where(RevisionExtintor.extintor_id.is_not(None))
        )
        or 0
    )


async def listar_todas(db: AsyncSession) -> list[Extintor]:
    """El inventario completo, ordenado por folio. Para el Excel.

    Sin paginar a propósito: la primera hoja del reporte es el estado de los
    160 aparatos, y son 160, no un histórico que crezca.
    """
    filas = await db.scalars(
        select(Extintor).order_by(func.lower(Extintor.folio), Extintor.id)
    )
    return list(filas.all())


async def por_ids(db: AsyncSession, ids: list[uuid.UUID]) -> list[Extintor]:
    """Los extintores de la cola de impresión, en orden de folio.

    Se ordena aquí y no por el orden en que se fueron añadiendo: las etiquetas
    salen en la hoja como se leen en el almacén, que es como se van pegando.
    """
    filas = await db.scalars(
        select(Extintor)
        .where(Extintor.id.in_(ids))
        .order_by(func.lower(Extintor.folio), Extintor.id)
    )
    return list(filas.all())


async def obtener(db: AsyncSession, extintor_id: uuid.UUID) -> Extintor:
    extintor = await db.get(Extintor, extintor_id)
    if extintor is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return extintor


def _validar_tipo(tipo: str) -> str:
    if tipo not in TIPOS_EXTINTOR_VALIDOS:
        raise ErrorDeNegocio(
            "El tipo de extintor no es válido. Usa uno de: "
            + ", ".join(TIPOS_EXTINTOR)
            + "."
        )
    return tipo


async def crear(db: AsyncSession, datos: Any) -> Extintor:
    """Da de alta una ficha.

    El tope es la dotación de la planta y no un límite técnico: existe para que
    un alta repetida por error no infle el inventario sin que nadie lo note.
    """
    registrados = await db.scalar(select(func.count(Extintor.id))) or 0
    if registrados >= MAX_EXTINTORES:
        raise ErrorDeNegocio(
            f"Ya hay {MAX_EXTINTORES} extintores registrados, que es la "
            f"dotación de la planta. Elimina alguno o pide que se suba el tope."
        )

    _validar_tipo(datos.tipo)
    extintor = Extintor(**datos.model_dump())
    db.add(extintor)

    try:
        await db.commit()
    except IntegrityError as exc:
        # El folio se comprueba con el choque y no con un SELECT previo: dos
        # altas simultáneas pasarían ambas la prueba.
        await db.rollback()
        raise ConflictoDeNegocio(FOLIO_DUPLICADO) from exc

    await db.refresh(extintor)
    return extintor


async def actualizar(db: AsyncSession, extintor_id: uuid.UUID, datos: Any) -> Extintor:
    """Corrige una ficha. No toca las revisiones ya guardadas."""
    extintor = await obtener(db, extintor_id)
    _validar_tipo(datos.tipo)

    for campo, valor in datos.model_dump().items():
        setattr(extintor, campo, valor)
    extintor.actualizado_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(FOLIO_DUPLICADO) from exc

    await db.refresh(extintor)
    return extintor


async def contar_revisiones(db: AsyncSession, extintor_id: uuid.UUID) -> int:
    """Cuántas revisiones tiene, para avisar antes de eliminar la ficha."""
    return (
        await db.scalar(
            select(func.count(RevisionExtintor.id)).where(
                RevisionExtintor.extintor_id == extintor_id
            )
        )
        or 0
    )


async def eliminar(db: AsyncSession, extintor_id: uuid.UUID) -> str:
    """Borra la ficha y **conserva su histórico**.

    El FK de las revisiones queda en NULL, y como cada una lleva copiados el
    folio, el modelo, el tipo y la ubicación, el Excel de los meses en que se
    revisó sigue diciendo de qué aparato hablaba. Borrar en cascada dejaría el
    reporte que ya se mandó por correo sin manera de cuadrar.
    """
    extintor = await obtener(db, extintor_id)
    etiqueta = etiquetar(extintor)
    await db.delete(extintor)
    await db.commit()
    return etiqueta


# --- Revisión diaria --------------------------------------------------------


async def revision_del_dia(
    db: AsyncSession, extintor_id: uuid.UUID, dia: date
) -> RevisionExtintor | None:
    """La revisión de ese día, con sus puntos cargados."""
    return await db.scalar(
        select(RevisionExtintor)
        .where(RevisionExtintor.extintor_id == extintor_id)
        .where(RevisionExtintor.fecha == dia)
        .options(selectinload(RevisionExtintor.puntos))
    )


async def detalle_revision(
    db: AsyncSession, revision_id: uuid.UUID
) -> tuple[RevisionExtintor, dict[uuid.UUID, list[uuid.UUID]]]:
    """La revisión con sus puntos y los IDENTIFICADORES de sus fotos.

    Los puntos se traen con `selectinload` y las fotos en una consulta aparte
    que **nunca selecciona la columna `imagen`**. Las dos cosas son necesarias:
    navegar la relación perezosa desde una sesión asíncrona revienta con
    `MissingGreenlet` —un 500 con la revisión ya guardada—, y cargar los blobs
    para devolver solo sus ids traería megabytes por cada respuesta.
    """
    revision = await db.scalar(
        select(RevisionExtintor)
        .where(RevisionExtintor.id == revision_id)
        .options(selectinload(RevisionExtintor.puntos))
    )
    if revision is None:
        raise RecursoNoEncontrado("La revisión no existe.")

    fotos = await _ids_de_fotos(
        db, FotoControl.punto_extintor_id, [punto.id for punto in revision.puntos]
    )
    return revision, fotos


def _validar_puntos(puntos: list[Any], fotos: dict[int, list[tuple[bytes, str]]]) -> int:
    """Comprueba la hoja completa y devuelve cuántas anomalías trae.

    Una hoja a medias no sirve como evidencia, así que se exigen los doce
    puntos exactamente una vez cada uno.
    """
    ordenes = sorted(punto.orden for punto in puntos)
    if ordenes != list(range(len(PUNTOS_EXTINTOR))):
        raise ErrorDeNegocio(
            f"Hay que contestar los {len(PUNTOS_EXTINTOR)} puntos de la "
            f"revisión, una sola vez cada uno."
        )

    anomalias = 0
    for punto in puntos:
        etiqueta = etiqueta_punto_extintor(punto.orden)
        del_punto = fotos.get(punto.orden, [])

        if punto.valor == "no_ok":
            anomalias += 1
            if not del_punto:
                raise ErrorDeNegocio(
                    f"{etiqueta}: un punto marcado como INCONFORME necesita al "
                    f"menos una foto de evidencia."
                )
        elif del_punto:
            raise ErrorDeNegocio(
                f"{etiqueta}: solo los puntos marcados como INCONFORME llevan fotos."
            )

        validar_cantidad_fotos(len(del_punto), etiqueta)

    return anomalias


async def registrar_revision(
    db: AsyncSession,
    extintor_id: uuid.UUID,
    *,
    puntos: list[Any],
    fotos: dict[int, list[tuple[bytes, str]]],
    admin: AdminUser,
    corrigiendo: bool = False,
    hoy: date | None = None,
) -> tuple[RevisionExtintor, dict[uuid.UUID, list[uuid.UUID]]]:
    """Guarda la revisión del día.

    `corrigiendo` rehace la de hoy en lugar de crearla, y solo llega desde el
    endpoint que exige permiso de `editar`. Las de días anteriores no se tocan
    nunca: el histórico ya se exportó.
    """
    dia = hoy or ahora_local().date()
    extintor = await obtener(db, extintor_id)
    anomalias = _validar_puntos(puntos, fotos)

    existente = await revision_del_dia(db, extintor_id, dia)

    if corrigiendo:
        if existente is None:
            raise ErrorDeNegocio(SIN_REVISION_HOY)
        # Se borran los puntos y sus fotos cuelgan en cascada; el cierre de
        # hallazgo, si lo hubiera, apunta a la revisión y sobrevive.
        await db.delete(existente)
        await db.flush()
    elif existente is not None:
        raise ConflictoDeNegocio(YA_REVISADO)

    revision = RevisionExtintor(
        extintor_id=extintor.id,
        # Snapshot de la ficha resuelta, para que el histórico sobreviva a su
        # eliminación.
        folio=extintor.folio,
        modelo=extintor.modelo,
        tipo=extintor.tipo,
        ubicacion=extintor.ubicacion,
        # Día de planta: el contenedor corre en UTC y a las 19:00 de la nave
        # `date.today()` ya sería mañana.
        fecha=dia,
        anomalias=anomalias,
        responsable=admin.username,
        admin_id=admin.id,
        puntos=[
            PuntoRevisionExtintor(
                orden=punto.orden,
                clave=PUNTOS_EXTINTOR[punto.orden].clave,
                valor=punto.valor,
                observaciones=punto.observaciones,
                fotos=_construir_fotos(fotos.get(punto.orden, [])),
            )
            for punto in sorted(puntos, key=lambda p: p.orden)
        ],
    )
    db.add(revision)

    try:
        await db.commit()
    except IntegrityError as exc:
        # El UNIQUE (extintor_id, fecha) es el que decide: dos capturas
        # simultáneas pasarían ambas la comprobación de arriba.
        await db.rollback()
        raise ConflictoDeNegocio(YA_REVISADO) from exc

    # Se relee con las relaciones cargadas: `refresh` no las trae, y leerlas
    # después dispararía la carga perezosa que revienta en async.
    return await detalle_revision(db, revision.id)


async def listar_revisiones(
    db: AsyncSession, desde: date, hasta: date
) -> list[RevisionExtintor]:
    """Las revisiones del periodo, con sus puntos, para el Excel."""
    filas = await db.scalars(
        select(RevisionExtintor)
        .where(RevisionExtintor.fecha.between(desde, hasta))
        .order_by(
            RevisionExtintor.fecha.desc(),
            func.lower(RevisionExtintor.folio),
        )
        .options(selectinload(RevisionExtintor.puntos))
    )
    return list(filas.all())


async def evidencias(db: AsyncSession, desde: date, hasta: date) -> list[Evidencia]:
    """Las fotos del periodo, para la hoja de evidencias del Excel.

    Es la única consulta que trae la columna `imagen`, y por eso va acotada al
    periodo: un año de evidencias no cabe en un archivo que se manda por correo.
    """
    filas = await db.execute(
        select(
            RevisionExtintor.fecha,
            RevisionExtintor.folio,
            RevisionExtintor.ubicacion,
            PuntoRevisionExtintor.orden,
            RevisionExtintor.responsable,
            FotoControl.imagen,
        )
        .join(PuntoRevisionExtintor, FotoControl.punto_extintor_id == PuntoRevisionExtintor.id)
        .join(RevisionExtintor, PuntoRevisionExtintor.revision_id == RevisionExtintor.id)
        .where(RevisionExtintor.fecha.between(desde, hasta))
        .order_by(RevisionExtintor.fecha, RevisionExtintor.folio, FotoControl.orden)
    )

    del_hallazgo = [
        Evidencia(
            fecha=fecha,
            detalle=f"{folio} ({ubicacion}) — {etiqueta_punto_extintor(orden)}",
            responsable=responsable,
            imagen=imagen,
        )
        for fecha, folio, ubicacion, orden, responsable, imagen in filas.all()
    ]

    # Las fotos de la verificación van a la MISMA hoja que las del hallazgo:
    # el Excel se comparte y tiene que mostrar el problema y la prueba de que
    # se resolvió, igual que hace el de los controles de lista.
    cierres = await db.execute(
        select(
            RevisionExtintor.fecha,
            RevisionExtintor.folio,
            RevisionExtintor.ubicacion,
            CierreHallazgo.responsable,
            FotoControl.imagen,
        )
        .join(CierreHallazgo, FotoControl.cierre_id == CierreHallazgo.id)
        .join(
            RevisionExtintor,
            CierreHallazgo.revision_extintor_id == RevisionExtintor.id,
        )
        .where(RevisionExtintor.fecha.between(desde, hasta))
        .order_by(RevisionExtintor.fecha, RevisionExtintor.folio, FotoControl.orden)
    )

    del_cierre = [
        Evidencia(
            fecha=fecha,
            detalle=f"{folio} ({ubicacion}) — cierre del hallazgo",
            responsable=responsable,
            imagen=imagen,
        )
        for fecha, folio, ubicacion, responsable, imagen in cierres.all()
    ]

    return del_hallazgo + del_cierre


# --- Avisos de vencimiento --------------------------------------------------


async def avisos_vencimiento(
    db: AsyncSession, hoy: date | None = None
) -> list[dict[str, Any]]:
    """Lo que vence dentro de un mes y lo que ya venció.

    La ventana la decide el backend; el panel solo la dibuja. Se devuelven
    datos y nunca frases: la campana arma el texto con `t()` e `Intl`
    (regla 6).
    """
    dia = hoy or ahora_local().date()
    limite = sumar_meses(dia, MESES_CRITICO)

    filas = await db.execute(
        select(
            Extintor.id,
            Extintor.folio,
            Extintor.ubicacion,
            Extintor.vencimiento,
        )
        # El filtro va en SQL y solo se traen las cuatro columnas que dibuja la
        # campana: es una consulta que corre en cada carga del panel.
        .where(Extintor.vencimiento <= limite)
        .order_by(Extintor.vencimiento)
    )

    return [
        {
            "id": extintor_id,
            "folio": folio,
            "ubicacion": ubicacion,
            "fecha_vencimiento": vencimiento,
            "dias": (vencimiento - dia).days,
            "vencido": vencimiento < dia,
        }
        for extintor_id, folio, ubicacion, vencimiento in filas.all()
    ]


# --- Hallazgos, para el sistema de cierres ---------------------------------


async def hallazgos_de_revision(
    db: AsyncSession, revision_id: uuid.UUID
) -> list[str]:
    """Los puntos INCONFORMES de una revisión, ya redactados.

    La etiqueta sale del catálogo y no de la base: corregir la redacción de un
    punto no debe reescribir lo que dice un cierre de hace tres meses.
    """
    filas = await db.execute(
        select(PuntoRevisionExtintor.orden, PuntoRevisionExtintor.observaciones)
        .where(PuntoRevisionExtintor.revision_id == revision_id)
        .where(PuntoRevisionExtintor.valor == "no_ok")
        .order_by(PuntoRevisionExtintor.orden)
    )

    return [
        f"{etiqueta_punto_extintor(orden)}: {observaciones}"
        for orden, observaciones in filas.all()
    ]
