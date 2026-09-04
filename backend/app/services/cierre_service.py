"""Cierre de hallazgos e incidencias de los controles ESH.

Un control registra que algo salió mal; esto registra qué se hizo al respecto.
El cierre es **uno por hoja**, no uno por problema: reproduce el bloque
"Acción en caso de anomalía" del formato en papel, que cubre la inspección
entera.

Lo que unifica el módulo es `hallazgos_de`: qué cuenta como problema no es
igual en los tres controles —un punto en NO OK, una respuesta en NO, o una
lectura fuera de rango— y esa traducción vive aquí una sola vez, para que el
modal, el Excel y la pestaña de Incidencias vean todos lo mismo.

Igual que el resto de la capa de servicio: no importa FastAPI y lanza las
excepciones de ``app.core.errors``.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.controles_catalogo import (
    CONTROL_EXTINTORES,
    CONTROLES_CHECKLIST,
    PUNTOS_SQP,
    RAYSER_MAXIMO,
    RAYSER_MINIMO,
    definicion_checklist,
    etiqueta_punto_extintor,
    semaforo,
)
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.models.admin_user import AdminUser
from app.services.control_service import Evidencia
from app.models.control import (
    CierreHallazgo,
    FotoControl,
    InspeccionSqp,
    PuntoChecklist,
    RegistroChecklist,
    RegistroRayser,
    RespuestaSqp,
)
from app.models.extintor import RevisionExtintor

#: Claves de control que admiten cierre. Pláticas no: una plática impartida no
#: es una inspección y no puede tener hallazgos.
CONTROL_RAYSER = "rayser"
CONTROL_SQP = "sqp"

Estado = Literal["pendiente", "cerrado"]

NO_EXISTE = "El registro no existe."
SIN_HALLAZGOS = (
    "Este registro no tiene hallazgos, así que no hay nada que cerrar."
)
NO_HAY_CIERRE = "Este registro todavía no tiene cierre de hallazgo."
YA_TIENE_CIERRE = (
    "Este registro ya tiene un cierre de hallazgo. Actualízalo en vez de "
    "crear otro."
)


@dataclass
class Hallazgo:
    """Un problema detectado, ya normalizado entre los tres controles."""

    #: Número del punto dentro de la hoja; ``None`` en Rayser, donde el
    #: hallazgo es del registro completo y no de un punto concreto.
    orden: int | None
    etiqueta: str
    observaciones: str | None
    fotos: list[uuid.UUID]


@dataclass
class Incidencia:
    """Un renglón de la pestaña de Incidencias."""

    control: str
    registro_id: uuid.UUID
    fecha: date
    #: Lo que distingue la hoja: el área en SQP, el tablero y el turno en
    #: tableros. Vacío cuando el control no tiene con qué.
    identificacion: str
    total_hallazgos: int
    responsable: str
    creado_at: datetime
    cierre: CierreHallazgo | None

    @property
    def estado(self) -> Estado:
        return "cerrado" if self.cierre is not None else "pendiente"


def es_control_valido(control: str) -> bool:
    """``True`` si el control admite cierre de hallazgo."""
    return (
        control in CONTROLES_CHECKLIST
        or control in (CONTROL_RAYSER, CONTROL_SQP, CONTROL_EXTINTORES)
    )


def _columna_dueno(control: str):
    """Cuál de las cuatro llaves foráneas del cierre le toca a este control."""
    if control == CONTROL_RAYSER:
        return CierreHallazgo.rayser_id
    if control == CONTROL_SQP:
        return CierreHallazgo.sqp_id
    if control == CONTROL_EXTINTORES:
        return CierreHallazgo.revision_extintor_id
    return CierreHallazgo.checklist_id


# --- Los hallazgos ---------------------------------------------------------


async def _hallazgos_checklist(
    db: AsyncSession, registro: RegistroChecklist
) -> list[Hallazgo]:
    definicion = definicion_checklist(registro.control)
    inconformes = [punto for punto in registro.puntos if punto.valor == "no_ok"]

    fotos = await _ids_de_fotos(
        db, FotoControl.punto_id, [punto.id for punto in inconformes]
    )

    hallazgos: list[Hallazgo] = []
    for punto in inconformes:
        # La etiqueta sale del catálogo, no de la base: cambiar la redacción
        # de un punto no debe obligar a tocar el histórico.
        etiqueta = punto.clave
        if definicion is not None and punto.orden < len(definicion.puntos):
            etiqueta = definicion.puntos[punto.orden].etiqueta

        hallazgos.append(
            Hallazgo(
                orden=punto.orden,
                etiqueta=etiqueta,
                observaciones=punto.observaciones,
                fotos=fotos.get(punto.id, []),
            )
        )

    return hallazgos


async def _hallazgos_rayser(
    db: AsyncSession, registro: RegistroRayser
) -> list[Hallazgo]:
    """En Rayser el hallazgo es del registro, no de un manómetro suelto.

    La hoja guarda una observación y unas fotos para toda la lectura, así que
    sale un único hallazgo cuyo texto nombra los manómetros fuera de rango.

    `fuera_de_rango` no es una columna: se deduce de las cuatro lecturas con el
    mismo `semaforo()` que usa el resto del sistema.
    """
    lecturas = [
        registro.manometro_1,
        registro.manometro_2,
        registro.manometro_3,
        registro.manometro_4,
    ]

    culpables = [
        f"Manómetro {indice}: {valor} psi"
        for indice, valor in enumerate(lecturas, start=1)
        if semaforo(valor) != "verde"
    ]

    if not culpables:
        return []

    fotos = await _ids_de_fotos(db, FotoControl.rayser_id, [registro.id])

    return [
        Hallazgo(
            orden=None,
            etiqueta=f"Lectura fuera del rango normal — {', '.join(culpables)}",
            observaciones=registro.observaciones,
            fotos=fotos.get(registro.id, []),
        )
    ]


async def _hallazgos_sqp(
    db: AsyncSession, inspeccion: InspeccionSqp
) -> list[Hallazgo]:
    """Las respuestas inconformes, con su evidencia."""
    inconformes = [r for r in inspeccion.respuestas if r.valor == "no"]
    fotos = await _ids_de_fotos(
        db, FotoControl.respuesta_id, [r.id for r in inconformes]
    )

    hallazgos: list[Hallazgo] = []

    for respuesta in inspeccion.respuestas:
        if respuesta.valor != "no":
            continue

        etiqueta = respuesta.codigo
        if respuesta.orden < len(PUNTOS_SQP):
            punto = PUNTOS_SQP[respuesta.orden]
            etiqueta = f"{punto.codigo} {punto.texto}"

        hallazgos.append(
            Hallazgo(
                orden=respuesta.orden,
                etiqueta=etiqueta,
                observaciones=respuesta.observaciones,
                fotos=fotos.get(respuesta.id, []),
            )
        )

    return hallazgos


async def _ids_de_fotos(
    db: AsyncSession, columna, propietarios: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Identificadores de las fotos, sin traer las imágenes.

    Copia deliberada del helper de ``control_service``: importarlo cruzaría
    dos servicios solo por seis líneas.
    """
    if not propietarios:
        return {}

    filas = await db.execute(
        select(FotoControl.id, columna)
        .where(columna.in_(propietarios))
        .order_by(FotoControl.orden)
    )

    agrupadas: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for foto_id, propietario in filas.all():
        agrupadas[propietario].append(foto_id)

    return agrupadas


async def _hallazgos_extintor(
    db: AsyncSession, revision: RevisionExtintor
) -> list[Hallazgo]:
    """Los puntos INCONFORMES de la revisión de un extintor."""
    inconformes = [punto for punto in revision.puntos if punto.valor == "no_ok"]

    fotos = await _ids_de_fotos(
        db, FotoControl.punto_extintor_id, [punto.id for punto in inconformes]
    )

    return [
        Hallazgo(
            orden=punto.orden,
            # Del catálogo y no de la base, igual que en los checklist: cambiar
            # la redacción de un punto no debe reescribir un cierre viejo.
            etiqueta=etiqueta_punto_extintor(punto.orden),
            observaciones=punto.observaciones,
            fotos=fotos.get(punto.id, []),
        )
        for punto in inconformes
    ]


async def _registro_de(db: AsyncSession, control: str, registro_id: uuid.UUID):
    """La hoja, con lo necesario para sacarle los hallazgos, o 404."""
    if control == CONTROL_RAYSER:
        registro = await db.scalar(
            select(RegistroRayser).where(RegistroRayser.id == registro_id)
        )
    elif control == CONTROL_SQP:
        registro = await db.scalar(
            select(InspeccionSqp)
            .where(InspeccionSqp.id == registro_id)
            .options(selectinload(InspeccionSqp.respuestas))
        )
    elif control == CONTROL_EXTINTORES:
        registro = await db.scalar(
            select(RevisionExtintor)
            .where(RevisionExtintor.id == registro_id)
            .options(selectinload(RevisionExtintor.puntos))
        )
    else:
        registro = await db.scalar(
            select(RegistroChecklist)
            .where(RegistroChecklist.id == registro_id)
            .options(selectinload(RegistroChecklist.puntos))
        )
        # Se comprueba el control además del id: una liga de otra pestaña no
        # debe poder leer el registro de esta.
        if registro is not None and registro.control != control:
            registro = None

    if registro is None:
        raise RecursoNoEncontrado(NO_EXISTE)

    return registro


async def hallazgos_de(db: AsyncSession, control: str, registro) -> list[Hallazgo]:
    """Los problemas de una hoja, iguales vengan del control que vengan."""
    if control == CONTROL_RAYSER:
        return await _hallazgos_rayser(db, registro)
    if control == CONTROL_SQP:
        return await _hallazgos_sqp(db, registro)
    if control == CONTROL_EXTINTORES:
        return await _hallazgos_extintor(db, registro)
    return await _hallazgos_checklist(db, registro)


# --- El cierre -------------------------------------------------------------


async def obtener_cierre(
    db: AsyncSession, control: str, registro_id: uuid.UUID
) -> CierreHallazgo | None:
    """El cierre de una hoja, o ``None`` si todavía no tiene."""
    return await db.scalar(
        select(CierreHallazgo)
        .where(_columna_dueno(control) == registro_id)
        .options(selectinload(CierreHallazgo.fotos))
    )


async def detalle_cierre(
    db: AsyncSession, control: str, registro_id: uuid.UUID
) -> dict:
    """Lo que necesita el modal: los hallazgos y el cierre, si lo hay."""
    registro = await _registro_de(db, control, registro_id)
    hallazgos = await hallazgos_de(db, control, registro)
    cierre = await obtener_cierre(db, control, registro_id)

    return {
        "control": control,
        "registro_id": registro_id,
        "fecha": registro.fecha,
        "hallazgos": hallazgos,
        "cierre": cierre,
        "fotos_cierre": [foto.id for foto in cierre.fotos] if cierre else [],
    }


@dataclass
class DatosCierre:
    """Lo que llega del formulario, ya validado por el schema."""

    hora_hallazgo: str
    ubicacion: str
    accion_inmediata: str
    responsable_accion: str
    hora_cierre: str
    accion_pendiente: str | None


async def guardar_cierre(
    db: AsyncSession,
    *,
    control: str,
    registro_id: uuid.UUID,
    datos: DatosCierre,
    fotos: list[tuple[bytes, str]],
    admin: AdminUser,
    actualizando: bool,
) -> CierreHallazgo:
    """Da de alta o actualiza el cierre de una hoja.

    Se exige que la hoja tenga hallazgos: cerrar una inspección limpia es un
    error de captura, no un caso de uso.

    Al actualizar, las fotos **reemplazan** a las anteriores solo si vienen:
    reabrir el modal para corregir un dedazo no debe borrar la evidencia que
    ya se había subido.
    """
    registro = await _registro_de(db, control, registro_id)

    hallazgos = await hallazgos_de(db, control, registro)
    if not hallazgos:
        raise ErrorDeNegocio(SIN_HALLAZGOS)

    cierre = await obtener_cierre(db, control, registro_id)

    # El alta y la actualización son caminos distintos a propósito: la ruta
    # que actualiza exige permiso de edición, así que un alta que "actualiza
    # en silencio" dejaría sobrescribir un cierre ajeno sin ese permiso.
    if cierre is not None and not actualizando:
        raise ConflictoDeNegocio(YA_TIENE_CIERRE)

    if cierre is None:
        if actualizando:
            raise RecursoNoEncontrado(NO_HAY_CIERRE)

        # La llave se elige con el MISMO criterio que `_columna_dueno()`, que
        # es quien luego lo busca: si las dos listas se separan, el cierre se
        # guarda en una columna y se lee en otra —y la hoja parece no tenerlo—.
        # Por eso la condición del checklist se escribe como "ninguno de los
        # anteriores" y no enumerando controles.
        propios = (CONTROL_RAYSER, CONTROL_SQP, CONTROL_EXTINTORES)
        cierre = CierreHallazgo(
            checklist_id=registro_id if control not in propios else None,
            rayser_id=registro_id if control == CONTROL_RAYSER else None,
            sqp_id=registro_id if control == CONTROL_SQP else None,
            revision_extintor_id=(
                registro_id if control == CONTROL_EXTINTORES else None
            ),
            responsable=admin.username,
            admin_id=admin.id,
        )
        db.add(cierre)
    else:
        cierre.actualizado_at = datetime.now(UTC)

    cierre.hora_hallazgo = datos.hora_hallazgo
    cierre.ubicacion = datos.ubicacion
    cierre.accion_inmediata = datos.accion_inmediata
    cierre.responsable_accion = datos.responsable_accion
    cierre.hora_cierre = datos.hora_cierre
    cierre.accion_pendiente = datos.accion_pendiente

    if fotos:
        cierre.fotos = [
            FotoControl(imagen=imagen, tipo=tipo, orden=orden)
            for orden, (imagen, tipo) in enumerate(fotos)
        ]

    await db.commit()
    await db.refresh(cierre, ["fotos"])

    return cierre


# --- Incidencias -----------------------------------------------------------


def _identificacion_checklist(registro: RegistroChecklist) -> str:
    """Lo que distingue la hoja: el turno en silos, el tablero en tableros."""
    definicion = definicion_checklist(registro.control)
    if definicion is None:
        return ""

    partes = [
        registro.encabezado[clave]
        for clave in definicion.clave_unicidad
        if registro.encabezado.get(clave)
    ]
    return ", ".join(partes)


def _rayser_fuera_de_rango() -> ColumnElement[bool]:
    """Condición SQL de "alguna lectura salió del rango normal".

    `fuera_de_rango` no es una columna: se deduce de los cuatro manómetros. En
    vez de traerse el mes a memoria para filtrarlo en Python, la comparación se
    arma aquí con los MISMOS límites del catálogo que usa `semaforo()`, así que
    el rango sigue definido en un solo lugar.
    """
    return or_(
        *[
            (columna < RAYSER_MINIMO) | (columna > RAYSER_MAXIMO)
            for columna in (
                RegistroRayser.manometro_1,
                RegistroRayser.manometro_2,
                RegistroRayser.manometro_3,
                RegistroRayser.manometro_4,
            )
        ]
    )


def _consulta_checklist(desde: date, hasta: date) -> Select:
    """Hojas con al menos un punto inconforme, contados en SQL.

    El conteo va con ``GROUP BY`` y no recorriendo registros en Python
    (regla 4): un mes de recorridos son cientos de puntos.
    """
    return (
        select(
            RegistroChecklist,
            func.count(PuntoChecklist.id).label("total"),
        )
        .join(
            PuntoChecklist,
            (PuntoChecklist.registro_id == RegistroChecklist.id)
            & (PuntoChecklist.valor == "no_ok"),
        )
        .where(RegistroChecklist.fecha.between(desde, hasta))
        .group_by(RegistroChecklist.id)
    )


async def listar_incidencias(
    db: AsyncSession,
    *,
    desde: date,
    hasta: date,
    control: str | None = None,
    estado: Estado | None = None,
) -> list[Incidencia]:
    """Todo lo que salió mal en el periodo, de los cuatro controles juntos.

    Son cuatro consultas y no una: las hojas viven en tablas distintas y un
    ``UNION`` entre ellas obligaría a aplanar columnas que no se parecen. El
    filtrado pesado —qué hojas tienen hallazgos y cuántos— sí va en SQL; lo
    único que se hace en Python es intercalar cuatro listas ya cortas y
    ordenarlas por fecha.
    """
    incidencias: list[Incidencia] = []

    quiere = lambda clave: control is None or control == clave  # noqa: E731

    # --- Listas de verificación ---
    if control is None or control in CONTROLES_CHECKLIST:
        consulta = _consulta_checklist(desde, hasta)
        if control is not None:
            consulta = consulta.where(RegistroChecklist.control == control)

        filas = await db.execute(consulta.options(selectinload(RegistroChecklist.puntos)))
        for registro, total in filas.all():
            incidencias.append(
                Incidencia(
                    control=registro.control,
                    registro_id=registro.id,
                    fecha=registro.fecha,
                    identificacion=_identificacion_checklist(registro),
                    total_hallazgos=total,
                    responsable=registro.responsable,
                    creado_at=registro.creado_at,
                    cierre=None,
                )
            )

    # --- Rayser ---
    if quiere(CONTROL_RAYSER):
        filas = await db.execute(
            select(RegistroRayser)
            .where(
                RegistroRayser.fecha.between(desde, hasta),
                _rayser_fuera_de_rango(),
            )
        )
        for registro in filas.scalars().all():
            incidencias.append(
                Incidencia(
                    control=CONTROL_RAYSER,
                    registro_id=registro.id,
                    fecha=registro.fecha,
                    identificacion="",
                    total_hallazgos=1,
                    responsable=registro.responsable,
                    creado_at=registro.creado_at,
                    cierre=None,
                )
            )

    # --- SQP ---
    if quiere(CONTROL_SQP):
        filas = await db.execute(
            select(InspeccionSqp, func.count(RespuestaSqp.id).label("total"))
            .join(
                RespuestaSqp,
                (RespuestaSqp.inspeccion_id == InspeccionSqp.id)
                & (RespuestaSqp.valor == "no"),
            )
            .where(InspeccionSqp.fecha.between(desde, hasta))
            .group_by(InspeccionSqp.id)
        )
        for inspeccion, total in filas.all():
            incidencias.append(
                Incidencia(
                    control=CONTROL_SQP,
                    registro_id=inspeccion.id,
                    fecha=inspeccion.fecha,
                    identificacion=inspeccion.area,
                    total_hallazgos=total,
                    responsable=inspeccion.responsable,
                    creado_at=inspeccion.creado_at,
                    cierre=None,
                )
            )

    # --- Extintores ---
    if quiere(CONTROL_EXTINTORES):
        filas = await db.execute(
            select(RevisionExtintor)
            .where(RevisionExtintor.fecha.between(desde, hasta))
            # `anomalias` es columna: no hace falta el GROUP BY sobre los
            # puntos que sí necesitan los checklist y SQP.
            .where(RevisionExtintor.anomalias > 0)
        )
        for revision in filas.scalars().all():
            incidencias.append(
                Incidencia(
                    control=CONTROL_EXTINTORES,
                    registro_id=revision.id,
                    fecha=revision.fecha,
                    # Qué aparato, que es lo que distingue a dos revisiones del
                    # mismo día.
                    identificacion=f"{revision.folio} — {revision.ubicacion}",
                    total_hallazgos=revision.anomalias,
                    responsable=revision.responsable,
                    creado_at=revision.creado_at,
                    cierre=None,
                )
            )

    await _adjuntar_cierres(db, incidencias)

    if estado is not None:
        incidencias = [
            incidencia for incidencia in incidencias if incidencia.estado == estado
        ]

    # De la más reciente a la más antigua, como el resto de los historiales.
    incidencias.sort(key=lambda i: (i.fecha, i.creado_at), reverse=True)

    return incidencias


async def _adjuntar_cierres(
    db: AsyncSession, incidencias: list[Incidencia]
) -> None:
    """Une los cierres a sus incidencias en UNA consulta, no una por renglón."""
    if not incidencias:
        return

    ids = [incidencia.registro_id for incidencia in incidencias]

    filas = await db.execute(
        select(CierreHallazgo)
        .where(
            CierreHallazgo.checklist_id.in_(ids)
            | CierreHallazgo.rayser_id.in_(ids)
            | CierreHallazgo.sqp_id.in_(ids)
            | CierreHallazgo.revision_extintor_id.in_(ids)
        )
        .options(selectinload(CierreHallazgo.fotos))
    )

    por_registro: dict[uuid.UUID, CierreHallazgo] = {}
    for cierre in filas.scalars().unique().all():
        dueno = (
            cierre.checklist_id
            or cierre.rayser_id
            or cierre.sqp_id
            or cierre.revision_extintor_id
        )
        if dueno is not None:
            por_registro[dueno] = cierre

    for incidencia in incidencias:
        incidencia.cierre = por_registro.get(incidencia.registro_id)


@dataclass
class IncidenciaCompleta:
    """Una incidencia con todo lo que el Excel necesita imprimir."""

    incidencia: Incidencia
    hallazgos: list[Hallazgo]
    #: Las imágenes en crudo, ya listas para incrustarse: las del hallazgo y
    #: las de la verificación, distinguidas por `detalle`.
    evidencias: list[Evidencia]


async def detalles_de_incidencias(
    db: AsyncSession, incidencias: list[Incidencia]
) -> list[IncidenciaCompleta]:
    """Completa las incidencias con sus hallazgos y sus imágenes.

    Las imágenes se piden en **una sola consulta** al final y no una por
    incidencia: son las únicas columnas pesadas de todo el reporte y traerlas
    de a una multiplicaría el tiempo del Excel por el número de renglones.
    """
    completas: list[IncidenciaCompleta] = []
    ids_foto: list[uuid.UUID] = []

    for incidencia in incidencias:
        registro = await _registro_de(db, incidencia.control, incidencia.registro_id)
        hallazgos = await hallazgos_de(db, incidencia.control, registro)

        for hallazgo in hallazgos:
            ids_foto.extend(hallazgo.fotos)
        if incidencia.cierre is not None:
            ids_foto.extend(foto.id for foto in incidencia.cierre.fotos)

        completas.append(
            IncidenciaCompleta(incidencia=incidencia, hallazgos=hallazgos, evidencias=[])
        )

    imagenes = await _imagenes(db, ids_foto)

    for completa in completas:
        evidencias: list[Evidencia] = []
        fecha = completa.incidencia.fecha

        for hallazgo in completa.hallazgos:
            for foto_id in hallazgo.fotos:
                imagen = imagenes.get(foto_id)
                if imagen is not None:
                    evidencias.append(
                        Evidencia(
                            fecha=fecha,
                            detalle=f"Hallazgo — {hallazgo.etiqueta}",
                            responsable=completa.incidencia.responsable,
                            imagen=imagen,
                        )
                    )

        cierre = completa.incidencia.cierre
        if cierre is not None:
            for foto in cierre.fotos:
                imagen = imagenes.get(foto.id)
                if imagen is not None:
                    evidencias.append(
                        Evidencia(
                            fecha=fecha,
                            detalle=f"Verificación — {cierre.ubicacion}",
                            responsable=cierre.responsable,
                            imagen=imagen,
                        )
                    )

        completa.evidencias = evidencias

    return completas


async def _imagenes(
    db: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, bytes]:
    """Los bytes de un lote de fotos, en una sola consulta."""
    if not ids:
        return {}

    filas = await db.execute(
        select(FotoControl.id, FotoControl.imagen).where(FotoControl.id.in_(ids))
    )
    return {foto_id: imagen for foto_id, imagen in filas.all()}


async def cierres_por_registro(
    db: AsyncSession, control: str, ids: list[uuid.UUID]
) -> dict[uuid.UUID, CierreHallazgo]:
    """Los cierres de un lote de hojas, en una sola consulta.

    Lo usan las hojas mensuales de Excel: preguntar por renglón serían 31
    consultas para un mes.
    """
    if not ids:
        return {}

    filas = await db.execute(
        select(CierreHallazgo)
        .where(_columna_dueno(control).in_(ids))
        .options(selectinload(CierreHallazgo.fotos))
    )

    columna = _columna_dueno(control).key
    return {
        getattr(cierre, columna): cierre
        for cierre in filas.scalars().unique().all()
    }


async def evidencias_de_cierres(
    db: AsyncSession, cierres: dict[uuid.UUID, CierreHallazgo], fechas: dict
) -> list[Evidencia]:
    """Las fotos de verificación, listas para la hoja de evidencias.

    Van junto a las del hallazgo en la misma hoja, distinguidas por su
    `detalle`: el Excel se comparte, y quien lo recibe necesita ver tanto el
    problema como la prueba de que se resolvió.
    """
    ids = [foto.id for cierre in cierres.values() for foto in cierre.fotos]
    imagenes = await _imagenes(db, ids)

    evidencias: list[Evidencia] = []
    for registro_id, cierre in cierres.items():
        for foto in cierre.fotos:
            imagen = imagenes.get(foto.id)
            if imagen is not None:
                evidencias.append(
                    Evidencia(
                        fecha=fechas.get(registro_id),
                        detalle=f"Verificación del cierre — {cierre.ubicacion}",
                        responsable=cierre.responsable,
                        imagen=imagen,
                    )
                )

    return evidencias
