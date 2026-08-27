"""Catálogo de insumos de seguridad.

Es un catálogo, no un almacén: la existencia se captura a mano tras el conteo.
El sistema de recepciones y salidas se construirá encima más adelante.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.insumo import ESTADO_BAJO, ESTADO_EXCEDIDO, Insumo
from app.schemas.catalogo import InsumoActualizar, InsumoCrear

#: Renglones por pantalla. Fijo: el catálogo se hojea, no se configura.
TAMANO_PAGINA: int = 50

# Caracteres que LIKE interpreta como comodín. Si alguien busca "100%" sin
# escaparlos, traería todo lo que empieza con "100" en vez del texto literal.
COMODINES_LIKE = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})

CODIGO_DUPLICADO = (
    "Ya existe un insumo con ese código. Los códigos no distinguen mayúsculas."
)
NO_EXISTE = "El insumo no existe."


def _condiciones(
    busqueda: str | None, categoria: str | None, estado: str | None
) -> list[Any]:
    """Traduce los filtros de la pantalla a condiciones de SQL.

    Todo se resuelve en la base, incluido el semáforo: traer las filas a
    Python para clasificarlas rompería la paginación y el conteo.
    """
    condiciones: list[Any] = []

    if busqueda and busqueda.strip():
        patron = f"%{busqueda.strip().translate(COMODINES_LIKE)}%"
        # ILIKE: quien busca en planta no distingue mayúsculas.
        condiciones.append(
            or_(
                Insumo.codigo.ilike(patron, escape="\\"),
                Insumo.descripcion.ilike(patron, escape="\\"),
                Insumo.proveedor.ilike(patron, escape="\\"),
                Insumo.ubicacion.ilike(patron, escape="\\"),
            )
        )

    if categoria:
        condiciones.append(Insumo.categoria == categoria)

    if estado == ESTADO_BAJO:
        condiciones.append(Insumo.cantidad < Insumo.minimo)
    elif estado == ESTADO_EXCEDIDO:
        condiciones.append(Insumo.cantidad > Insumo.maximo)

    return condiciones


async def _obtener(db: AsyncSession, insumo_id: uuid.UUID) -> Insumo:
    """Busca un insumo o lanza 404."""
    insumo = await db.scalar(select(Insumo).where(Insumo.id == insumo_id))
    if insumo is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return insumo


async def mapa_por_codigo(
    db: AsyncSession, codigos: set[str]
) -> dict[str, Insumo]:
    """Busca varios insumos por código en **una sola** consulta.

    La clave del diccionario es el código en minúsculas, porque así es el
    índice único: quien llama debe buscar con ``codigo.lower()``. Se resuelve
    de un golpe y no uno por uno para poder decirle al usuario **todos** los
    códigos que faltan de una vez, en lugar de hacerle corregir de a uno.
    """
    if not codigos:
        return {}

    filas = await db.scalars(
        select(Insumo).where(func.lower(Insumo.codigo).in_(codigos))
    )
    return {insumo.codigo.lower(): insumo for insumo in filas.all()}


async def listar(
    db: AsyncSession,
    *,
    busqueda: str | None = None,
    categoria: str | None = None,
    estado: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    """Devuelve una página del catálogo, en orden alfabético."""
    page = max(1, page)
    condiciones = _condiciones(busqueda, categoria, estado)

    # El conteo va aparte del listado: es lo que necesita el paginador, y
    # traer todas las filas para contarlas sería justo lo que la regla 4
    # prohíbe.
    total = await db.scalar(select(func.count(Insumo.id)).where(*condiciones))

    filas = await db.scalars(
        select(Insumo)
        .where(*condiciones)
        .order_by(func.lower(Insumo.codigo))
        .offset((page - 1) * TAMANO_PAGINA)
        .limit(TAMANO_PAGINA)
    )

    return {
        "total": total or 0,
        "page": page,
        "size": TAMANO_PAGINA,
        "items": list(filas.all()),
    }


async def crear(db: AsyncSession, datos: InsumoCrear) -> Insumo:
    """Da de alta un insumo."""
    insumo = Insumo(**datos.model_dump())
    db.add(insumo)

    # Se deja que la base decida la unicidad en lugar de consultarla antes:
    # entre el SELECT y el INSERT cabe otra alta con el mismo nombre.
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(CODIGO_DUPLICADO) from exc

    await db.refresh(insumo)
    return insumo


async def actualizar(
    db: AsyncSession, insumo_id: uuid.UUID, datos: InsumoActualizar
) -> Insumo:
    """Actualiza un insumo completo."""
    insumo = await _obtener(db, insumo_id)

    for campo, valor in datos.model_dump().items():
        setattr(insumo, campo, valor)
    insumo.actualizado_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(CODIGO_DUPLICADO) from exc

    await db.refresh(insumo)
    return insumo


async def eliminar(db: AsyncSession, insumo_id: uuid.UUID) -> str:
    """Borra un insumo y devuelve su código.

    Después del DELETE ya no hay de dónde leerlo, y la bitácora necesita
    decir qué se eliminó.
    """
    insumo = await _obtener(db, insumo_id)
    codigo = insumo.codigo
    await db.delete(insumo)
    await db.commit()
    return codigo


async def importar(db: AsyncSession, filas: list[InsumoCrear]) -> tuple[int, int]:
    """Da de alta las filas nuevas y omite las que ya existen.

    Devuelve ``(creados, omitidos)``. Los repetidos se omiten en vez de
    actualizarse a propósito: así un archivo viejo no puede pisar existencias
    que ya se corrigieron en el panel.

    Los códigos ya presentes se resuelven con **una** consulta, no una por
    fila, y se compara en minúsculas porque así es el índice único.
    """
    if not filas:
        return 0, 0

    codigos = {fila.codigo.lower() for fila in filas}
    existentes = set(
        (
            await db.scalars(
                select(func.lower(Insumo.codigo)).where(
                    func.lower(Insumo.codigo).in_(codigos)
                )
            )
        ).all()
    )

    creados = 0
    omitidos = 0
    vistos: set[str] = set()

    for fila in filas:
        clave = fila.codigo.lower()
        # `vistos` atrapa los repetidos DENTRO del mismo archivo, que la
        # consulta de arriba no puede ver todavía.
        if clave in existentes or clave in vistos:
            omitidos += 1
            continue

        db.add(Insumo(**fila.model_dump()))
        vistos.add(clave)
        creados += 1

    await db.commit()
    return creados, omitidos
