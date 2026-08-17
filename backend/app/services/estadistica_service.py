"""Agregaciones del dashboard.

Regla del proyecto: todo se calcula en SQL con GROUP BY / FILTER / AVG. Nunca
se cargan los intentos a memoria para contarlos en Python: con 500 empleados
y varios cuestionarios eso no escala y además duplica lógica que la base de
datos ya hace mejor.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.core.constants import AREAS, AREAS_VALIDAS, etiqueta_area
from app.core.errors import ErrorDeNegocio
from app.models.cuestionario import Opcion, Pregunta
from app.models.intento import Intento, Respuesta
from app.models.meta_area import MetaArea

# Rangos del histograma de calificaciones (spec §8).
RANGOS_DISTRIBUCION: list[tuple[str, int, int]] = [
    ("0-59", 0, 59),
    ("60-69", 60, 69),
    ("70-79", 70, 79),
    ("80-89", 80, 89),
    ("90-100", 90, 100),
]

COLUMNAS_ORDENABLES = {
    "nombre": Intento.nombre,
    "numero_empleado": Intento.numero_empleado,
    "area": Intento.area,
    "finalizado_at": Intento.finalizado_at,
    "puntaje": Intento.puntaje,
}

MAX_TAMANO_PAGINA = 200


@dataclass
class Filtros:
    """Filtros comunes del dashboard."""

    cuestionario_id: uuid.UUID
    area: str | None = None
    desde: date | None = None
    hasta: date | None = None

    def __post_init__(self) -> None:
        if self.area is not None and self.area not in AREAS_VALIDAS:
            raise ErrorDeNegocio(f"El área '{self.area}' no existe en el catálogo.")
        if self.desde is not None and self.hasta is not None and self.desde > self.hasta:
            raise ErrorDeNegocio("La fecha inicial no puede ser posterior a la final.")


def _condiciones(filtros: Filtros, solo_finalizados: bool = True) -> list[ColumnElement[bool]]:
    """Traduce los filtros a condiciones sobre la tabla de intentos."""
    condiciones: list[ColumnElement[bool]] = [
        Intento.cuestionario_id == filtros.cuestionario_id
    ]

    if solo_finalizados:
        condiciones.append(Intento.finalizado_at.is_not(None))

    if filtros.area is not None:
        condiciones.append(Intento.area == filtros.area)

    if filtros.desde is not None:
        condiciones.append(
            Intento.finalizado_at >= datetime.combine(filtros.desde, time.min)
        )

    if filtros.hasta is not None:
        # Se suma un día y se compara con "<": así el rango incluye el día
        # completo de `hasta`, sin depender de la hora.
        condiciones.append(
            Intento.finalizado_at
            < datetime.combine(filtros.hasta + timedelta(days=1), time.min)
        )

    return condiciones


async def _metas_por_area(db: AsyncSession) -> dict[str, int]:
    """Devuelve el headcount configurado por área."""
    filas = (await db.execute(select(MetaArea.area, MetaArea.headcount))).all()
    return {area: headcount for area, headcount in filas}


def _porcentaje(parte: float | int, total: float | int) -> float | None:
    """Porcentaje redondeado, o None si no hay denominador."""
    if not total:
        return None
    return round((parte / total) * 100, 2)


# --- Resumen (KPIs) --------------------------------------------------------


async def resumen(db: AsyncSession, filtros: Filtros) -> dict[str, Any]:
    """Calcula los cuatro KPIs de la fila superior en una sola consulta."""
    umbral = Decimal(settings.UMBRAL_APROBACION)

    fila = (
        await db.execute(
            select(
                func.count(Intento.id).label("total"),
                func.avg(Intento.puntaje).label("promedio"),
                func.count(Intento.id)
                .filter(Intento.puntaje >= umbral)
                .label("aprobados"),
            ).where(and_(*_condiciones(filtros)))
        )
    ).one()

    # Los intentos abandonados se cuentan aparte: son señal de problemas de
    # red o de operadores que no terminaron, y no deben ensuciar el promedio.
    en_progreso = await db.scalar(
        select(func.count(Intento.id)).where(
            and_(*_condiciones(filtros, solo_finalizados=False)),
            Intento.finalizado_at.is_(None),
        )
    )

    metas = await _metas_por_area(db)
    if filtros.area is not None:
        meta_total = metas.get(filtros.area)
    else:
        meta_total = sum(metas.values()) if metas else None

    total = fila.total or 0
    promedio = float(fila.promedio) if fila.promedio is not None else None

    return {
        "total_respuestas": total,
        "total_en_progreso": en_progreso or 0,
        "participacion": {
            "recibidas": total,
            "meta": meta_total,
            "porcentaje": _porcentaje(total, meta_total) if meta_total else None,
        },
        "promedio_general": round(promedio, 2) if promedio is not None else None,
        "tasa_aprobacion": _porcentaje(fila.aprobados or 0, total),
        "aprobados": fila.aprobados or 0,
        "umbral_aprobacion": settings.UMBRAL_APROBACION,
    }


# --- Por área --------------------------------------------------------------


async def por_area(db: AsyncSession, filtros: Filtros) -> list[dict[str, Any]]:
    """Agrega intentos, promedio, mínimo, máximo y aprobación por área."""
    umbral = Decimal(settings.UMBRAL_APROBACION)

    filas = (
        await db.execute(
            select(
                Intento.area,
                func.count(Intento.id).label("intentos"),
                func.avg(Intento.puntaje).label("promedio"),
                func.min(Intento.puntaje).label("minimo"),
                func.max(Intento.puntaje).label("maximo"),
                func.count(Intento.id)
                .filter(Intento.puntaje >= umbral)
                .label("aprobados"),
            )
            .where(and_(*_condiciones(filtros)))
            .group_by(Intento.area)
        )
    ).all()

    por_clave = {fila.area: fila for fila in filas}
    metas = await _metas_por_area(db)

    resultado: list[dict[str, Any]] = []

    # Se recorre el catálogo completo, no solo las áreas con intentos: un área
    # con cero respuestas es justo la que interesa ver en la gráfica de
    # participación.
    for area in AREAS:
        if filtros.area is not None and area.value != filtros.area:
            continue

        fila = por_clave.get(area.value)
        intentos = fila.intentos if fila else 0
        meta = metas.get(area.value)

        resultado.append(
            {
                "area": area.value,
                "label": area.label,
                "intentos": intentos,
                "promedio": round(float(fila.promedio), 2)
                if fila and fila.promedio is not None
                else None,
                "minimo": float(fila.minimo) if fila and fila.minimo is not None else None,
                "maximo": float(fila.maximo) if fila and fila.maximo is not None else None,
                "aprobados": fila.aprobados if fila else 0,
                "porcentaje_aprobacion": _porcentaje(
                    fila.aprobados if fila else 0, intentos
                ),
                "meta": meta,
                "porcentaje_participacion": _porcentaje(intentos, meta) if meta else None,
            }
        )

    return resultado


# --- Por pregunta ----------------------------------------------------------


def _intentos_considerados(filtros: Filtros) -> Select[tuple[uuid.UUID]]:
    """Subconsulta con los ids de intentos que pasan los filtros."""
    return select(Intento.id).where(and_(*_condiciones(filtros)))


async def por_pregunta(db: AsyncSession, filtros: Filtros) -> list[dict[str, Any]]:
    """Índice de acierto y error por pregunta, con el desglose de opciones."""
    intentos = _intentos_considerados(filtros).subquery()

    filas = (
        await db.execute(
            select(
                Pregunta.id,
                Pregunta.orden,
                Pregunta.texto,
                func.count(Respuesta.id).label("total"),
                func.count(Respuesta.id)
                .filter(Respuesta.es_correcta.is_(True))
                .label("correctas"),
            )
            .select_from(Pregunta)
            .outerjoin(
                Respuesta,
                and_(
                    Respuesta.pregunta_id == Pregunta.id,
                    Respuesta.intento_id.in_(select(intentos.c.id)),
                ),
            )
            .where(Pregunta.cuestionario_id == filtros.cuestionario_id)
            .group_by(Pregunta.id, Pregunta.orden, Pregunta.texto)
            .order_by(Pregunta.orden)
        )
    ).all()

    # Desglose de opciones en una sola consulta adicional, no una por pregunta.
    desgloses = (
        await db.execute(
            select(
                Opcion.pregunta_id,
                Opcion.id,
                Opcion.texto,
                Opcion.es_correcta,
                Opcion.orden,
                func.count(Respuesta.id).label("elegida"),
            )
            .select_from(Opcion)
            .join(Pregunta, Pregunta.id == Opcion.pregunta_id)
            .outerjoin(
                Respuesta,
                and_(
                    Respuesta.opcion_id == Opcion.id,
                    Respuesta.intento_id.in_(select(intentos.c.id)),
                ),
            )
            .where(Pregunta.cuestionario_id == filtros.cuestionario_id)
            .group_by(
                Opcion.pregunta_id, Opcion.id, Opcion.texto, Opcion.es_correcta, Opcion.orden
            )
            .order_by(Opcion.pregunta_id, Opcion.orden)
        )
    ).all()

    opciones_por_pregunta: dict[uuid.UUID, list[Any]] = {}
    for desglose in desgloses:
        opciones_por_pregunta.setdefault(desglose.pregunta_id, []).append(desglose)

    resultado: list[dict[str, Any]] = []

    for fila in filas:
        total = fila.total or 0
        correctas = fila.correctas or 0

        resultado.append(
            {
                "pregunta_id": fila.id,
                "orden": fila.orden,
                "texto": fila.texto,
                "total_respuestas": total,
                "correctas": correctas,
                "incorrectas": total - correctas,
                "porcentaje_acierto": _porcentaje(correctas, total),
                "porcentaje_error": _porcentaje(total - correctas, total),
                "opciones": [
                    {
                        "opcion_id": opcion.id,
                        "texto": opcion.texto,
                        "es_correcta": opcion.es_correcta,
                        "elegida": opcion.elegida or 0,
                        "porcentaje": _porcentaje(opcion.elegida or 0, total) or 0.0,
                    }
                    for opcion in opciones_por_pregunta.get(fila.id, [])
                ],
            }
        )

    return resultado


# --- Distribución de calificaciones ---------------------------------------


async def distribucion(db: AsyncSession, filtros: Filtros) -> list[dict[str, Any]]:
    """Histograma por rangos, contado en SQL con FILTER."""
    columnas = [
        func.count(Intento.id)
        .filter(
            and_(
                Intento.puntaje >= Decimal(minimo),
                Intento.puntaje <= Decimal(maximo),
            )
        )
        .label(f"rango_{indice}")
        for indice, (_, minimo, maximo) in enumerate(RANGOS_DISTRIBUCION)
    ]

    fila = (
        await db.execute(select(*columnas).where(and_(*_condiciones(filtros))))
    ).one()

    return [
        {"rango": etiqueta, "cantidad": getattr(fila, f"rango_{indice}") or 0}
        for indice, (etiqueta, _, _) in enumerate(RANGOS_DISTRIBUCION)
    ]


# --- Línea de tiempo -------------------------------------------------------


async def linea_tiempo(db: AsyncSession, filtros: Filtros) -> list[dict[str, Any]]:
    """Respuestas por día, con el promedio de ese día."""
    dia = func.date(Intento.finalizado_at).label("dia")

    filas = (
        await db.execute(
            select(
                dia,
                func.count(Intento.id).label("cantidad"),
                func.avg(Intento.puntaje).label("promedio"),
            )
            .where(and_(*_condiciones(filtros)))
            .group_by(dia)
            .order_by(dia)
        )
    ).all()

    return [
        {
            "fecha": fila.dia,
            "cantidad": fila.cantidad,
            "promedio": round(float(fila.promedio), 2)
            if fila.promedio is not None
            else None,
        }
        for fila in filas
    ]


# --- Tabla de intentos -----------------------------------------------------


async def listar_intentos(
    db: AsyncSession,
    filtros: Filtros,
    page: int = 1,
    size: int = 25,
    orden_por: str = "finalizado_at",
    descendente: bool = True,
) -> dict[str, Any]:
    """Tabla paginada con ordenamiento por columna."""
    if orden_por not in COLUMNAS_ORDENABLES:
        raise ErrorDeNegocio(
            f"No se puede ordenar por '{orden_por}'. "
            f"Columnas válidas: {', '.join(sorted(COLUMNAS_ORDENABLES))}."
        )

    page = max(1, page)
    size = min(max(1, size), MAX_TAMANO_PAGINA)

    condiciones = _condiciones(filtros)

    total = await db.scalar(select(func.count(Intento.id)).where(and_(*condiciones)))

    columna = COLUMNAS_ORDENABLES[orden_por]
    # nulls_last evita que los intentos sin puntaje encabecen la tabla al
    # ordenar de mayor a menor.
    criterio = columna.desc().nulls_last() if descendente else columna.asc().nulls_last()

    duracion = case(
        (
            Intento.finalizado_at.is_not(None),
            func.extract("epoch", Intento.finalizado_at - Intento.iniciado_at),
        ),
        else_=None,
    ).label("duracion")

    filas = (
        await db.execute(
            select(
                Intento.id,
                Intento.nombre,
                Intento.numero_empleado,
                Intento.area,
                Intento.iniciado_at,
                Intento.finalizado_at,
                Intento.correctas,
                Intento.total_preguntas,
                Intento.puntaje,
                duracion,
            )
            .where(and_(*condiciones))
            .order_by(criterio, Intento.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    return {
        "total": total or 0,
        "page": page,
        "size": size,
        "items": [
            {
                "id": fila.id,
                "nombre": fila.nombre,
                "numero_empleado": fila.numero_empleado,
                "area": fila.area,
                "area_label": etiqueta_area(fila.area),
                "iniciado_at": fila.iniciado_at,
                "finalizado_at": fila.finalizado_at,
                "duracion_segundos": int(fila.duracion)
                if fila.duracion is not None
                else None,
                "correctas": fila.correctas,
                "total_preguntas": fila.total_preguntas,
                "puntaje": fila.puntaje,
            }
            for fila in filas
        ],
    }


# --- Detalle para exportaciones -------------------------------------------


async def detalle_intentos(
    db: AsyncSession, filtros: Filtros
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Devuelve las preguntas del cuestionario y un renglón por intento.

    Cada renglón trae la opción elegida en cada pregunta, que es lo que pide
    la hoja "Respuestas detalladas" del Excel. La consulta trae las respuestas
    planas y el pivote se arma en Python: es presentación, no agregación, y
    hacerlo en SQL exigiría columnas dinámicas.
    """
    preguntas = (
        await db.execute(
            select(Pregunta.id, Pregunta.orden, Pregunta.texto)
            .where(Pregunta.cuestionario_id == filtros.cuestionario_id)
            .order_by(Pregunta.orden)
        )
    ).all()

    duracion = func.extract(
        "epoch", Intento.finalizado_at - Intento.iniciado_at
    ).label("duracion")

    intentos = (
        await db.execute(
            select(
                Intento.id,
                Intento.nombre,
                Intento.numero_empleado,
                Intento.area,
                Intento.iniciado_at,
                Intento.finalizado_at,
                Intento.correctas,
                Intento.total_preguntas,
                Intento.puntaje,
                duracion,
            )
            .where(and_(*_condiciones(filtros)))
            .order_by(Intento.area, Intento.nombre)
        )
    ).all()

    respuestas = (
        await db.execute(
            select(
                Respuesta.intento_id,
                Respuesta.pregunta_id,
                Respuesta.es_correcta,
                Opcion.texto,
            )
            .join(Opcion, Opcion.id == Respuesta.opcion_id)
            .where(Respuesta.intento_id.in_(select(Intento.id).where(and_(*_condiciones(filtros)))))
        )
    ).all()

    elegidas: dict[uuid.UUID, dict[uuid.UUID, tuple[str, bool]]] = {}
    for fila in respuestas:
        elegidas.setdefault(fila.intento_id, {})[fila.pregunta_id] = (
            fila.texto,
            fila.es_correcta,
        )

    filas = [
        {
            "nombre": intento.nombre,
            "numero_empleado": intento.numero_empleado,
            "area": etiqueta_area(intento.area),
            "iniciado_at": intento.iniciado_at,
            "finalizado_at": intento.finalizado_at,
            "duracion_segundos": int(intento.duracion)
            if intento.duracion is not None
            else None,
            "correctas": intento.correctas,
            "total_preguntas": intento.total_preguntas,
            "puntaje": float(intento.puntaje) if intento.puntaje is not None else None,
            "respuestas": elegidas.get(intento.id, {}),
        }
        for intento in intentos
    ]

    columnas = [
        {"id": pregunta.id, "orden": pregunta.orden, "texto": pregunta.texto}
        for pregunta in preguntas
    ]

    return columnas, filas


# --- Metas por área --------------------------------------------------------


async def listar_metas(db: AsyncSession) -> list[dict[str, Any]]:
    """Devuelve el catálogo completo con su meta, o None si no se capturó."""
    metas = await _metas_por_area(db)

    return [
        {"area": area.value, "label": area.label, "headcount": metas.get(area.value)}
        for area in AREAS
    ]


async def guardar_metas(
    db: AsyncSession, metas: list[tuple[str, int]]
) -> list[dict[str, Any]]:
    """Guarda las metas en lote, validando contra el catálogo de áreas."""
    desconocidas = [area for area, _ in metas if area not in AREAS_VALIDAS]
    if desconocidas:
        raise ErrorDeNegocio(
            f"Estas áreas no existen en el catálogo: {', '.join(desconocidas)}."
        )

    existentes = {
        meta.area: meta for meta in (await db.scalars(select(MetaArea))).all()
    }

    for area, headcount in metas:
        if area in existentes:
            existentes[area].headcount = headcount
        else:
            db.add(MetaArea(area=area, headcount=headcount))

    await db.commit()

    return await listar_metas(db)
