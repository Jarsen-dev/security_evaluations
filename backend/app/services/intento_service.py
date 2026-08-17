"""Lógica de negocio del formulario público: intentos y respuestas."""

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.cuestionario import Cuestionario, Opcion, Pregunta
from app.models.intento import Intento, Respuesta
from app.schemas.publico import IniciarIntentoIn

# Mensaje único para token inexistente y cuestionario inactivo: distinguirlos
# permitiría sondear qué tokens existen.
CUESTIONARIO_NO_DISPONIBLE = (
    "Este cuestionario no está disponible. Verifica la liga con tu supervisor."
)


async def obtener_cuestionario_publico(
    db: AsyncSession, token: str
) -> Cuestionario:
    """Busca el cuestionario por su token público y confirma que esté activo."""
    cuestionario = await db.scalar(
        select(Cuestionario)
        .where(Cuestionario.token_publico == token)
        .options(selectinload(Cuestionario.preguntas).selectinload(Pregunta.opciones))
    )

    if cuestionario is None or not cuestionario.activo:
        raise RecursoNoEncontrado(CUESTIONARIO_NO_DISPONIBLE)

    return cuestionario


async def _ya_tiene_intento_finalizado(
    db: AsyncSession, cuestionario_id: uuid.UUID, numero_empleado: str
) -> bool:
    """Indica si el empleado ya cerró un intento de este cuestionario."""
    existente = await db.scalar(
        select(Intento.id).where(
            Intento.cuestionario_id == cuestionario_id,
            Intento.numero_empleado == numero_empleado,
            Intento.finalizado_at.is_not(None),
        )
    )
    return existente is not None


async def crear_intento(
    db: AsyncSession,
    token: str,
    datos: IniciarIntentoIn,
    ip_origen: str | None,
    user_agent: str | None,
) -> tuple[Intento, Cuestionario]:
    """Crea el intento tras validar la regla de intento único."""
    cuestionario = await obtener_cuestionario_publico(db, token)

    if not cuestionario.permitir_multiples_intentos and await _ya_tiene_intento_finalizado(
        db, cuestionario.id, datos.numero_empleado
    ):
        raise ConflictoDeNegocio(
            f"El número de empleado {datos.numero_empleado} ya contestó este "
            f"cuestionario. Solo se permite un intento."
        )

    intento = Intento(
        cuestionario_id=cuestionario.id,
        nombre=datos.nombre,
        numero_empleado=datos.numero_empleado,
        area=datos.area,
        total_preguntas=len(cuestionario.preguntas),
        # Una IP inválida rompería la columna INET; se guarda NULL antes que
        # perder el intento completo.
        ip_origen=ip_origen,
        user_agent=user_agent,
    )

    db.add(intento)
    await db.commit()
    await db.refresh(intento)

    return intento, cuestionario


async def obtener_intento(db: AsyncSession, intento_id: uuid.UUID) -> Intento:
    """Recupera un intento por id."""
    intento = await db.scalar(select(Intento).where(Intento.id == intento_id))

    if intento is None:
        raise RecursoNoEncontrado("El intento no existe o ya no está disponible.")

    return intento


async def obtener_respuestas(
    db: AsyncSession, intento_id: uuid.UUID
) -> dict[uuid.UUID, uuid.UUID]:
    """Devuelve lo ya contestado como pregunta_id -> opcion_id.

    Permite restaurar el formulario si el operador recarga la página o se le
    cae la conexión. No incluye marcas de acierto.
    """
    filas = (
        await db.execute(
            select(Respuesta.pregunta_id, Respuesta.opcion_id).where(
                Respuesta.intento_id == intento_id,
                Respuesta.opcion_id.is_not(None),
            )
        )
    ).all()

    return {pregunta_id: opcion_id for pregunta_id, opcion_id in filas}


async def guardar_respuesta(
    db: AsyncSession,
    intento_id: uuid.UUID,
    pregunta_id: uuid.UUID,
    opcion_id: uuid.UUID,
) -> None:
    """Autoguardado: inserta o actualiza la respuesta de una pregunta.

    ``es_correcta`` se calcula aquí comparando contra la base de datos. El
    cliente nunca informa si acertó, y la respuesta de este endpoint tampoco
    se lo revela.
    """
    intento = await obtener_intento(db, intento_id)

    if intento.finalizado_at is not None:
        raise ConflictoDeNegocio(
            "Este cuestionario ya fue enviado; no se pueden cambiar las respuestas."
        )

    # La opción debe existir Y pertenecer a la pregunta indicada, y la
    # pregunta al cuestionario del intento: así un id manipulado no puede
    # contestar por otro cuestionario.
    fila = (
        await db.execute(
            select(Opcion.es_correcta)
            .join(Pregunta, Pregunta.id == Opcion.pregunta_id)
            .where(
                Opcion.id == opcion_id,
                Opcion.pregunta_id == pregunta_id,
                Pregunta.cuestionario_id == intento.cuestionario_id,
            )
        )
    ).first()

    if fila is None:
        raise RecursoNoEncontrado("La opción seleccionada no es válida.")

    es_correcta = bool(fila[0])

    # Upsert: el autoguardado reenvía la misma pregunta cada vez que el
    # operador cambia de opinión, y la cola de reintentos puede repetir
    # peticiones tras un corte de red.
    sentencia = (
        pg_insert(Respuesta)
        .values(
            intento_id=intento_id,
            pregunta_id=pregunta_id,
            opcion_id=opcion_id,
            es_correcta=es_correcta,
            respondido_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            constraint="uq_respuestas_intento_pregunta",
            set_={
                "opcion_id": opcion_id,
                "es_correcta": es_correcta,
                "respondido_at": datetime.now(UTC),
            },
        )
    )

    await db.execute(sentencia)
    await db.commit()


async def finalizar_intento(db: AsyncSession, intento_id: uuid.UUID) -> Intento:
    """Cierra el intento y calcula el puntaje.

    El puntaje pondera por los puntos de cada pregunta: con el valor por
    defecto (1 punto) equivale al porcentaje simple de aciertos.
    """
    intento = await obtener_intento(db, intento_id)

    if intento.finalizado_at is not None:
        # Reenviar el formulario (por doble clic o por un reintento de la
        # cola) devuelve el resultado ya calculado en vez de fallar.
        return intento

    cuestionario = await db.scalar(
        select(Cuestionario)
        .where(Cuestionario.id == intento.cuestionario_id)
        .options(selectinload(Cuestionario.preguntas))
    )

    if cuestionario is None:
        raise RecursoNoEncontrado("El cuestionario ya no existe.")

    if not cuestionario.permitir_multiples_intentos and await _ya_tiene_intento_finalizado(
        db, cuestionario.id, intento.numero_empleado
    ):
        raise ConflictoDeNegocio(
            f"El número de empleado {intento.numero_empleado} ya contestó este "
            f"cuestionario. Solo se permite un intento."
        )

    puntos_por_pregunta = {
        pregunta.id: pregunta.puntos for pregunta in cuestionario.preguntas
    }
    puntos_totales = sum(puntos_por_pregunta.values())

    respuestas = (
        await db.scalars(select(Respuesta).where(Respuesta.intento_id == intento_id))
    ).all()

    correctas = sum(1 for respuesta in respuestas if respuesta.es_correcta)
    puntos_obtenidos = sum(
        puntos_por_pregunta.get(respuesta.pregunta_id, 0)
        for respuesta in respuestas
        if respuesta.es_correcta
    )

    if puntos_totales > 0:
        puntaje = (Decimal(puntos_obtenidos) / Decimal(puntos_totales)) * Decimal(100)
    else:
        puntaje = Decimal(0)

    intento.correctas = correctas
    intento.total_preguntas = len(cuestionario.preguntas)
    intento.puntaje = puntaje.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    intento.finalizado_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        # Red de seguridad del índice único parcial `uq_intento_unico`: cubre
        # el caso de dos envíos simultáneos que pasen juntos la validación.
        await db.rollback()
        raise ConflictoDeNegocio(
            f"El número de empleado {intento.numero_empleado} ya contestó este "
            f"cuestionario. Solo se permite un intento."
        ) from exc

    await db.refresh(intento)
    return intento


def calcular_aprobado(puntaje: Decimal | None) -> bool:
    """Compara el puntaje contra el umbral configurado en el entorno."""
    if puntaje is None:
        return False
    return puntaje >= Decimal(settings.UMBRAL_APROBACION)
