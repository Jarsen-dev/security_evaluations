"""Catálogo de insumos de seguridad.

Cada renglón lleva dos números que se confunden fácil: ``piezas_por_empaque``
es lo que trae una caja del producto, y ``existencia`` es el inventario real en
piezas. La existencia la suman las recepciones y se corrige a mano tras el
conteo físico; las piezas por empaque solo cambian si cambia la presentación.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.insumo import EXPRESIONES_ESTADO, Insumo
from app.schemas.catalogo import InsumoActualizar, InsumoCrear

#: Renglones por pantalla. Fijo: el catálogo se hojea, no se configura.
TAMANO_PAGINA: int = 50

# Caracteres que LIKE interpreta como comodín. Si alguien busca "100%" sin
# escaparlos, traería todo lo que empieza con "100" en vez del texto literal.
COMODINES_LIKE = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})

CODIGO_DUPLICADO = (
    "Ya existe un insumo con ese código y esa misma descripción. Un código "
    "puede repetirse, pero la descripción tiene que distinguirlos. Ni el "
    "código ni la descripción distinguen mayúsculas."
)
NO_EXISTE = "El insumo no existe."

#: Cuánto de la descripción cabe en un renglón de bitácora. El middleware
#: recorta en 300 contando el prefijo del catálogo ("Editó un insumo: "), así
#: que una descripción larga se comería el resto del renglón.
LARGO_ETIQUETA_BITACORA = 80


def etiquetar(insumo: Insumo) -> str:
    """Cómo se nombra un insumo en la bitácora y en los diálogos.

    Con el código repetible, `codigo` por sí solo ya no dice cuál fue.
    """
    return f"{insumo.codigo} · {insumo.descripcion[:LARGO_ETIQUETA_BITACORA]}"


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

    # El semáforo se arma en `models/insumo.py`, pegado a `estado_insumo()`:
    # la regla es una cascada de cinco ramas y tenerla escrita dos veces la
    # condenaba a divergir. La ruta ya validó que el estado exista.
    if estado:
        condiciones.append(EXPRESIONES_ESTADO[estado])

    return condiciones


async def _obtener(db: AsyncSession, insumo_id: uuid.UUID) -> Insumo:
    """Busca un insumo o lanza 404."""
    insumo = await db.scalar(select(Insumo).where(Insumo.id == insumo_id))
    if insumo is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return insumo


async def mapa_por_codigo(
    db: AsyncSession, codigos: set[str]
) -> dict[str, list[Insumo]]:
    """Busca varios insumos por código en **una sola** consulta.

    Cada código trae una **lista**: un mismo código de proveedor ampara varios
    productos y lo que los distingue es la descripción. Devolver uno solo haría
    que la recepción le sumara la existencia al primero que apareciera, sin que
    nada avisara.

    La clave del diccionario es el código en minúsculas, porque así es el
    índice único: quien llama debe buscar con ``codigo.lower()``. Se resuelve
    de un golpe y no uno por uno para poder decirle al usuario **todos** los
    códigos que faltan de una vez, en lugar de hacerle corregir de a uno.
    """
    if not codigos:
        return {}

    filas = await db.scalars(
        select(Insumo)
        .where(func.lower(Insumo.codigo).in_(codigos))
        .order_by(func.lower(Insumo.descripcion))
    )

    mapa: dict[str, list[Insumo]] = defaultdict(list)
    for insumo in filas.all():
        mapa[insumo.codigo.lower()].append(insumo)
    return dict(mapa)


async def por_codigo(db: AsyncSession, codigo: str) -> list[Insumo]:
    """Todos los insumos que comparten un código exacto.

    Es lo que necesita la captura de recepciones para ofrecer las descripciones
    de un código. Coincidencia exacta, no parcial: el buscador del catálogo
    hace otra cosa.
    """
    filas = await db.scalars(
        select(Insumo)
        .where(func.lower(Insumo.codigo) == codigo.strip().lower())
        .order_by(func.lower(Insumo.descripcion))
    )
    return list(filas.all())


#: Cuántos insumos ofrece el desplegable de captura. Corto a propósito: es una
#: lista que se elige con el dedo, no un catálogo que se hojea.
TOPE_SUGERENCIAS: Final[int] = 20

#: Mínimo para buscar. Con una sola letra el desplegable barre el catálogo
#: entero en cada tecla y devuelve veinte filas al azar.
MINIMO_BUSQUEDA: Final[int] = 2


async def buscar(
    db: AsyncSession, texto: str, *, limite: int = TOPE_SUGERENCIAS
) -> list[Insumo]:
    """Insumos cuyo código o descripción contienen `texto`.

    Es el desplegable de captura del control de insumos, y por eso NO mira
    proveedor ni ubicación como el buscador del catálogo: ahí son columnas que
    ayudan a encontrar una ficha, pero aquí meterían en la lista productos que
    no se parecen en nada a lo que se tecleó.

    **El orden no es alfabético, y esa es la parte que importa.** Primero van
    los del código exacto, luego los que empiezan por lo tecleado y al final el
    resto. Con un `ILIKE %x%` a secas y un tope de veinte, teclear un código
    corto podía dejar fuera de la lista justo a los insumos que lo comparten
    —que son los que hay que poder distinguir— porque otro producto los
    adelantaba por orden alfabético. Dentro de cada grupo el desempate es
    `codigo, descripcion`, así que los homónimos salen juntos y seguidos.
    """
    limpio = texto.strip()
    if len(limpio) < MINIMO_BUSQUEDA:
        return []

    escapado = limpio.translate(COMODINES_LIKE)
    codigo = func.lower(Insumo.codigo)

    filas = await db.scalars(
        select(Insumo)
        .where(
            or_(
                Insumo.codigo.ilike(f"%{escapado}%", escape="\\"),
                Insumo.descripcion.ilike(f"%{escapado}%", escape="\\"),
            )
        )
        .order_by(
            case(
                (codigo == limpio.lower(), 0),
                (codigo.startswith(limpio.lower()), 1),
                else_=2,
            ),
            codigo,
            func.lower(Insumo.descripcion),
            Insumo.id,
        )
        .limit(limite)
    )
    return list(filas.all())


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
        # El código ya no es único: sin desempate, dos insumos que lo comparten
        # pueden salir en distinto orden entre páginas, repetirse en una y
        # perderse en otra.
        .order_by(func.lower(Insumo.codigo), func.lower(Insumo.descripcion), Insumo.id)
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
    """Borra un insumo y devuelve cómo se llamaba.

    Después del DELETE ya no hay de dónde leerlo, y la bitácora necesita
    decir qué se eliminó. Va con la descripción y no solo con el código: el
    código puede repetirse y por sí solo ya no identifica la fila.
    """
    insumo = await _obtener(db, insumo_id)
    etiqueta = etiquetar(insumo)
    await db.delete(insumo)
    await db.commit()
    return etiqueta


#: Lo que una reimportación puede corregir sobre un insumo que YA existe.
#:
#: `codigo` y `descripcion` quedan fuera porque **son** la identidad: cambiarlos
#: no sería corregir esta fila, sería apuntar a otra distinta.
#:
#: `existencia` queda fuera por un motivo más fuerte: es el único número que
#: mueve el propio sistema —confirmar una recepción le suma piezas con un
#: ``UPDATE ... existencia + :n``—, así que dejar que el archivo la pisara
#: borraría en silencio todas las entradas de almacén posteriores a la
#: exportación de ese Excel, que es justo lo que nadie revisa. Corregir una
#: existencia sigue siendo del formulario del panel, con su propio permiso.
CAMPOS_ACTUALIZABLES: Final[tuple[str, ...]] = (
    "categoria",
    "unidad_medida",
    "proveedor",
    "ubicacion",
    "piezas_por_empaque",
    "minimo",
    "maximo",
)


@dataclass(frozen=True)
class ResumenImportacion:
    """Qué le pasó al catálogo, contado por INSUMO y no por renglón.

    Un archivo que repite la misma pareja código + descripción dos veces habla
    de un solo insumo, y contarlo dos veces haría que los números no cuadraran
    con lo que la pantalla muestra después.
    """

    creados: int
    actualizados: int
    sin_cambios: int


def _aplicar_cambios(
    insumo: Insumo, fila: InsumoCrear, campos: tuple[str, ...]
) -> bool:
    """Copia a `insumo` lo que la fila trae DISTINTO. Dice si tocó algo.

    Compara antes de asignar para no marcar como actualizado —ni sellar
    `actualizado_at`— un insumo que llegó idéntico: reimportar el mismo
    archivo dos veces seguidas tiene que ser inocuo la segunda vez.
    """
    cambio = False
    for campo in campos:
        valor = getattr(fila, campo)
        if getattr(insumo, campo) != valor:
            setattr(insumo, campo, valor)
            cambio = True

    if cambio:
        insumo.actualizado_at = datetime.now(UTC)
    return cambio


async def importar(
    db: AsyncSession,
    filas: list[InsumoCrear],
    columnas: frozenset[str] | None = None,
) -> ResumenImportacion:
    """Da de alta las filas nuevas y corrige las que ya existen.

    Lo que decide si una fila "ya existe" es la pareja **código +
    descripción**, igual que el índice único: un mismo código puede traer
    varias descripciones y todas son insumos distintos.

    De un insumo que ya está solo se toca **lo que el archivo trae distinto**
    (ver `CAMPOS_ACTUALIZABLES`), y solo entre las columnas que el archivo
    realmente traía: `columnas` son las que el lector encontró en el
    encabezado, y sin ese filtro un Excel recortado a las cuatro obligatorias
    borraría el proveedor y la ubicación de todo el catálogo, porque las filas
    salen del lector con esas claves en su valor por omisión.

    Las parejas ya presentes se resuelven con **una** consulta, no una por
    fila, y se comparan en minúsculas porque así es el índice único.
    """
    if not filas:
        return ResumenImportacion(creados=0, actualizados=0, sin_cambios=0)

    campos = tuple(
        campo
        for campo in CAMPOS_ACTUALIZABLES
        if columnas is None or campo in columnas
    )

    codigos = {fila.codigo.lower() for fila in filas}
    # Se traen los insumos completos y no solo la pareja: para saber si una
    # fila cambia algo hay que comparar campo por campo.
    existentes: dict[tuple[str, str], Insumo] = {
        (insumo.codigo.lower(), insumo.descripcion.lower()): insumo
        for insumo in (
            await db.execute(
                select(Insumo).where(func.lower(Insumo.codigo).in_(codigos))
            )
        )
        .scalars()
        .all()
    }

    nuevos: dict[tuple[str, str], Insumo] = {}
    actualizados: set[tuple[str, str]] = set()
    intactos: set[tuple[str, str]] = set()

    for fila in filas:
        # La clave es la pareja, no el código: un archivo con dos descripciones
        # del mismo código tiene que dar de alta las dos.
        clave = (fila.codigo.lower(), fila.descripcion.lower())

        existente = existentes.get(clave)
        if existente is not None:
            if _aplicar_cambios(existente, fila, campos):
                actualizados.add(clave)
                intactos.discard(clave)
            elif clave not in actualizados:
                intactos.add(clave)
            continue

        repetido = nuevos.get(clave)
        if repetido is not None:
            # La misma pareja dos veces DENTRO del archivo, que la consulta de
            # arriba todavía no podía ver. Manda el último renglón y se copia
            # entero —incluida la existencia—: sigue siendo un alta, y para un
            # insumo que no existía el archivo es la única fuente que hay.
            for campo, valor in fila.model_dump().items():
                setattr(repetido, campo, valor)
            continue

        alta = Insumo(**fila.model_dump())
        db.add(alta)
        nuevos[clave] = alta

    try:
        await db.commit()
    except IntegrityError as exc:
        # No debería ocurrir —los repetidos ya se resolvieron arriba—, pero
        # entre el SELECT y el COMMIT cabe otra alta con la misma pareja.
        await db.rollback()
        raise ConflictoDeNegocio(CODIGO_DUPLICADO) from exc

    return ResumenImportacion(
        creados=len(nuevos),
        actualizados=len(actualizados),
        sin_cambios=len(intactos),
    )
