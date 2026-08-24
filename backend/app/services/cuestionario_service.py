"""Lógica de negocio de cuestionarios, preguntas y opciones."""

import secrets
import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ErrorDeNegocio, RecursoNoEncontrado
from app.models.cuestionario import Cuestionario, Opcion, Pregunta
from app.models.intento import Intento
from app.schemas.cuestionario import (
    CuestionarioActualizar,
    CuestionarioCrear,
    OpcionIn,
    OrdenPregunta,
    PreguntaIn,
)

MIN_OPCIONES = 2
MAX_INTENTOS_TOKEN = 5


# --- Validación de reglas de negocio ---------------------------------------


def validar_preguntas(preguntas: Sequence[PreguntaIn]) -> None:
    """Aplica las reglas de negocio de las preguntas.

    Cada pregunta necesita texto, mínimo 2 opciones con texto y exactamente
    una marcada como correcta. Se acumulan todos los errores para que el
    usuario los corrija de una sola vez, en lugar de descubrirlos uno a uno.
    """
    errores: list[str] = []

    for indice, pregunta in enumerate(preguntas, start=1):
        if not pregunta.texto.strip():
            errores.append(f"La pregunta {indice} no tiene texto.")

        opciones_con_texto = [op for op in pregunta.opciones if op.texto.strip()]
        if len(opciones_con_texto) < MIN_OPCIONES:
            errores.append(
                f"La pregunta {indice} tiene {len(opciones_con_texto)} opción(es); "
                f"se requieren mínimo {MIN_OPCIONES}."
            )

        correctas = sum(1 for op in opciones_con_texto if op.es_correcta)
        if correctas == 0:
            errores.append(
                f"La pregunta {indice} no tiene ninguna opción marcada como correcta."
            )
        elif correctas > 1:
            errores.append(
                f"La pregunta {indice} tiene {correctas} opciones marcadas como "
                f"correctas; debe haber exactamente una."
            )

    if errores:
        raise ErrorDeNegocio(
            "El cuestionario tiene preguntas incompletas.", errores=errores
        )


async def _generar_token_publico(db: AsyncSession) -> str:
    """Genera un token URL-safe aleatorio y único.

    ``token_urlsafe(24)`` produce 32 caracteres, que es justo el ancho de la
    columna. La colisión es prácticamente imposible, pero se reintenta por si
    acaso en lugar de dejar que reviente el índice único.
    """
    for _ in range(MAX_INTENTOS_TOKEN):
        token = secrets.token_urlsafe(24)
        existe = await db.scalar(
            select(Cuestionario.id).where(Cuestionario.token_publico == token)
        )
        if existe is None:
            return token

    raise ErrorDeNegocio("No se pudo generar una liga única. Intenta de nuevo.")


# --- Consultas -------------------------------------------------------------


def _consulta_listado() -> Select[tuple[Cuestionario, int, int]]:
    """Listado con conteos calculados en SQL, no en Python.

    Se usan subconsultas escalares en lugar de JOIN + GROUP BY porque contar
    dos relaciones distintas en un mismo JOIN multiplica las filas.
    """
    total_preguntas = (
        select(func.count(Pregunta.id))
        .where(Pregunta.cuestionario_id == Cuestionario.id)
        .correlate(Cuestionario)
        .scalar_subquery()
    )
    # Solo cuentan los intentos finalizados: los abandonados no son respuestas.
    total_respuestas = (
        select(func.count(Intento.id))
        .where(
            Intento.cuestionario_id == Cuestionario.id,
            Intento.finalizado_at.is_not(None),
        )
        .correlate(Cuestionario)
        .scalar_subquery()
    )

    return (
        select(
            Cuestionario,
            total_preguntas.label("total_preguntas"),
            total_respuestas.label("total_respuestas"),
        )
        .order_by(Cuestionario.created_at.desc())
    )


async def listar_cuestionarios(db: AsyncSession) -> list[dict[str, object]]:
    """Devuelve los cuestionarios con su conteo de preguntas y respuestas."""
    filas = (await db.execute(_consulta_listado())).all()

    return [
        {
            **{
                columna: getattr(cuestionario, columna)
                for columna in (
                    "id",
                    "nombre",
                    "descripcion",
                    "token_publico",
                    "activo",
                    "permitir_multiples_intentos",
                    "created_at",
                    "updated_at",
                )
            },
            "total_preguntas": total_preguntas,
            "total_respuestas": total_respuestas,
        }
        for cuestionario, total_preguntas, total_respuestas in filas
    ]


async def obtener_cuestionario(
    db: AsyncSession, cuestionario_id: uuid.UUID
) -> Cuestionario:
    """Devuelve el cuestionario con preguntas y opciones ya cargadas.

    ``selectinload`` evita el problema N+1: dos consultas en total en lugar
    de una por pregunta.
    """
    cuestionario = await db.scalar(
        select(Cuestionario)
        .where(Cuestionario.id == cuestionario_id)
        .options(selectinload(Cuestionario.preguntas).selectinload(Pregunta.opciones))
        # populate_existing fuerza a releer las colecciones ya cargadas en la
        # sesión. Sin esto, tras reordenar o editar, la respuesta trae las
        # preguntas en su posición anterior aunque el campo `orden` sí venga
        # actualizado.
        .execution_options(populate_existing=True)
    )

    if cuestionario is None:
        raise RecursoNoEncontrado("El cuestionario no existe.")

    return cuestionario


async def obtener_pregunta(db: AsyncSession, pregunta_id: uuid.UUID) -> Pregunta:
    """Devuelve una pregunta con sus opciones."""
    pregunta = await db.scalar(
        select(Pregunta)
        .where(Pregunta.id == pregunta_id)
        .options(selectinload(Pregunta.opciones))
        .execution_options(populate_existing=True)
    )

    if pregunta is None:
        raise RecursoNoEncontrado("La pregunta no existe.")

    return pregunta


# --- Escritura -------------------------------------------------------------


def _construir_opciones(pregunta_in: PreguntaIn) -> list[Opcion]:
    """Crea las opciones de una pregunta, descartando las vacías."""
    return [
        Opcion(orden=orden, texto=opcion.texto, es_correcta=opcion.es_correcta)
        for orden, opcion in enumerate(
            (op for op in pregunta_in.opciones if op.texto.strip())
        )
    ]


def _sincronizar_opciones(pregunta: Pregunta, opciones_in: list[OpcionIn]) -> None:
    """Reconcilia las opciones de una pregunta emparejándolas por ``id``.

    CRÍTICO: no se pueden reemplazar en bloque. ``respuestas.opcion_id``
    apunta a estas filas con ON DELETE SET NULL, así que borrarlas y
    recrearlas deja en NULL la opción elegida de todas las respuestas
    históricas: se pierde para siempre qué contestó cada persona, aunque el
    texto de la opción no haya cambiado.

    Solo se elimina lo que el usuario realmente quitó del constructor.
    """
    con_texto = [opcion for opcion in opciones_in if opcion.texto.strip()]
    existentes = {opcion.id: opcion for opcion in pregunta.opciones}
    conservadas: set[uuid.UUID] = set()

    for orden, opcion_in in enumerate(con_texto):
        if opcion_in.id is not None and opcion_in.id in existentes:
            opcion = existentes[opcion_in.id]
            opcion.orden = orden
            opcion.texto = opcion_in.texto
            opcion.es_correcta = opcion_in.es_correcta
            conservadas.add(opcion.id)
        else:
            pregunta.opciones.append(
                Opcion(
                    orden=orden,
                    texto=opcion_in.texto,
                    es_correcta=opcion_in.es_correcta,
                )
            )

    for opcion_id, opcion in existentes.items():
        if opcion_id not in conservadas:
            pregunta.opciones.remove(opcion)


async def crear_cuestionario(
    db: AsyncSession, datos: CuestionarioCrear
) -> Cuestionario:
    """Crea un cuestionario con sus preguntas y opciones."""
    validar_preguntas(datos.preguntas)

    cuestionario = Cuestionario(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        token_publico=await _generar_token_publico(db),
        permitir_multiples_intentos=datos.permitir_multiples_intentos,
        preguntas=[
            Pregunta(
                orden=orden,
                texto=pregunta.texto,
                puntos=pregunta.puntos,
                opciones=_construir_opciones(pregunta),
            )
            for orden, pregunta in enumerate(datos.preguntas)
        ],
    )

    db.add(cuestionario)
    await db.commit()

    return await obtener_cuestionario(db, cuestionario.id)


async def _sincronizar_preguntas(
    db: AsyncSession, cuestionario: Cuestionario, preguntas: Sequence[PreguntaIn]
) -> None:
    """Reconcilia las preguntas del cuestionario contra las recibidas.

    Se emparejan por ``id`` en lugar de borrar y recrear todo: así las
    preguntas que no cambiaron conservan su identidad y las respuestas ya
    registradas sobreviven a una edición. Las preguntas que el usuario quitó
    del constructor sí se eliminan, y con ellas sus respuestas (cascada).
    """
    existentes = {pregunta.id: pregunta for pregunta in cuestionario.preguntas}
    conservadas: set[uuid.UUID] = set()

    for orden, pregunta_in in enumerate(preguntas):
        opciones_validas = [op for op in pregunta_in.opciones if op.texto.strip()]

        if pregunta_in.id is not None and pregunta_in.id in existentes:
            pregunta = existentes[pregunta_in.id]
            pregunta.orden = orden
            pregunta.texto = pregunta_in.texto
            pregunta.puntos = pregunta_in.puntos

            _sincronizar_opciones(pregunta, pregunta_in.opciones)
            conservadas.add(pregunta.id)
        else:
            cuestionario.preguntas.append(
                Pregunta(
                    orden=orden,
                    texto=pregunta_in.texto,
                    puntos=pregunta_in.puntos,
                    opciones=[
                        Opcion(
                            orden=indice,
                            texto=opcion.texto,
                            es_correcta=opcion.es_correcta,
                        )
                        for indice, opcion in enumerate(opciones_validas)
                    ],
                )
            )

    for pregunta_id, pregunta in existentes.items():
        if pregunta_id not in conservadas:
            cuestionario.preguntas.remove(pregunta)


async def actualizar_cuestionario(
    db: AsyncSession, cuestionario_id: uuid.UUID, datos: CuestionarioActualizar
) -> Cuestionario:
    """Actualiza metadatos y, si vienen, el conjunto de preguntas."""
    cuestionario = await obtener_cuestionario(db, cuestionario_id)

    if datos.nombre is not None:
        cuestionario.nombre = datos.nombre
    if datos.descripcion is not None:
        cuestionario.descripcion = datos.descripcion
    if datos.activo is not None:
        cuestionario.activo = datos.activo
    if datos.permitir_multiples_intentos is not None:
        cuestionario.permitir_multiples_intentos = datos.permitir_multiples_intentos

    if datos.preguntas is not None:
        validar_preguntas(datos.preguntas)
        await _sincronizar_preguntas(db, cuestionario, datos.preguntas)

    await db.commit()

    return await obtener_cuestionario(db, cuestionario_id)


async def eliminar_cuestionario(db: AsyncSession, cuestionario_id: uuid.UUID) -> str:
    """Elimina el cuestionario y, en cascada, sus preguntas e intentos.

    Devuelve el nombre de lo que borró: una vez hecho el ``DELETE`` ya no hay
    de dónde sacarlo, y la bitácora necesita decir *qué* se eliminó.
    """
    cuestionario = await obtener_cuestionario(db, cuestionario_id)
    nombre = cuestionario.nombre
    await db.delete(cuestionario)
    await db.commit()
    return nombre


async def agregar_pregunta(
    db: AsyncSession, cuestionario_id: uuid.UUID, datos: PreguntaIn
) -> Pregunta:
    """Agrega una pregunta al final del cuestionario."""
    validar_preguntas([datos])

    cuestionario = await obtener_cuestionario(db, cuestionario_id)
    siguiente_orden = len(cuestionario.preguntas)

    pregunta = Pregunta(
        cuestionario_id=cuestionario.id,
        orden=siguiente_orden,
        texto=datos.texto,
        puntos=datos.puntos,
        opciones=_construir_opciones(datos),
    )

    db.add(pregunta)
    await db.commit()

    return await obtener_pregunta(db, pregunta.id)


async def actualizar_pregunta(
    db: AsyncSession, pregunta_id: uuid.UUID, datos: PreguntaIn
) -> Pregunta:
    """Actualiza el texto, los puntos y las opciones de una pregunta."""
    validar_preguntas([datos])

    pregunta = await obtener_pregunta(db, pregunta_id)
    pregunta.texto = datos.texto
    pregunta.puntos = datos.puntos
    # Se reconcilian por id, no se reemplazan: ver _sincronizar_opciones.
    _sincronizar_opciones(pregunta, datos.opciones)

    await db.commit()

    return await obtener_pregunta(db, pregunta_id)


async def eliminar_pregunta(db: AsyncSession, pregunta_id: uuid.UUID) -> None:
    """Elimina una pregunta y compacta el orden de las restantes."""
    pregunta = await obtener_pregunta(db, pregunta_id)
    cuestionario_id = pregunta.cuestionario_id

    await db.delete(pregunta)
    await db.flush()

    # Sin compactar, quedarían huecos en la secuencia de orden y el siguiente
    # "agregar pregunta" chocaría contra el índice único.
    restantes = (
        await db.scalars(
            select(Pregunta)
            .where(Pregunta.cuestionario_id == cuestionario_id)
            .order_by(Pregunta.orden)
        )
    ).all()

    for nuevo_orden, restante in enumerate(restantes):
        restante.orden = nuevo_orden

    await db.commit()


async def reordenar_preguntas(
    db: AsyncSession, cuestionario_id: uuid.UUID, ordenes: Sequence[OrdenPregunta]
) -> Cuestionario:
    """Reordena las preguntas en lote.

    La restricción ``uq_preguntas_cuestionario_orden`` es DEFERRABLE
    INITIALLY DEFERRED, así que los órdenes duplicados intermedios no fallan:
    solo se evalúa al hacer commit.
    """
    cuestionario = await obtener_cuestionario(db, cuestionario_id)
    por_id = {pregunta.id: pregunta for pregunta in cuestionario.preguntas}

    desconocidas = [str(item.id) for item in ordenes if item.id not in por_id]
    if desconocidas:
        raise ErrorDeNegocio(
            "Algunas preguntas no pertenecen a este cuestionario.",
            errores=desconocidas,
        )

    if len(ordenes) != len(por_id):
        raise ErrorDeNegocio(
            "El reordenamiento debe incluir todas las preguntas del cuestionario."
        )

    for item in ordenes:
        por_id[item.id].orden = item.orden

    await db.commit()

    return await obtener_cuestionario(db, cuestionario_id)


async def duplicar_cuestionario(
    db: AsyncSession, cuestionario_id: uuid.UUID
) -> Cuestionario:
    """Clona el cuestionario con sus preguntas y opciones, sin respuestas.

    La copia nace con token propio e inactiva: evita que una duplicación
    accidental empiece a recibir respuestas antes de revisarla.
    """
    original = await obtener_cuestionario(db, cuestionario_id)

    copia = Cuestionario(
        nombre=f"{original.nombre} (copia)"[:200],
        descripcion=original.descripcion,
        token_publico=await _generar_token_publico(db),
        activo=False,
        permitir_multiples_intentos=original.permitir_multiples_intentos,
        preguntas=[
            Pregunta(
                orden=pregunta.orden,
                texto=pregunta.texto,
                puntos=pregunta.puntos,
                opciones=[
                    Opcion(
                        orden=opcion.orden,
                        texto=opcion.texto,
                        es_correcta=opcion.es_correcta,
                    )
                    for opcion in pregunta.opciones
                ],
            )
            for pregunta in original.preguntas
        ],
    )

    db.add(copia)
    await db.commit()

    return await obtener_cuestionario(db, copia.id)
