"""Endpoints del formulario público.

Sin autenticación: la única credencial es el token de la URL. Ver
``app.schemas.publico`` para la regla de no exponer nunca ``es_correcta``.
"""

import ipaddress
import logging
import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictoDeNegocio
from app.core.ratelimit import obtener_ip_cliente
from app.db.session import get_db
from app.schemas.publico import (
    CuestionarioPublico,
    EstadoIntento,
    GuardarRespuestaIn,
    IniciarIntentoIn,
    IntentoIniciado,
    PreguntaPublica,
    RespuestaGuardada,
    ResultadoIntento,
)
from app.services import intento_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publico", tags=["publico"])

MAX_USER_AGENT = 500


def _ip_valida(request: Request) -> str | None:
    """Devuelve la IP del cliente solo si es una dirección válida.

    La columna ``ip_origen`` es de tipo INET: un valor con formato inválido
    (por una cabecera manipulada) abortaría el insert completo.
    """
    crudo = obtener_ip_cliente(request)
    try:
        return str(ipaddress.ip_address(crudo))
    except ValueError:
        return None


@router.get(
    "/{token}",
    response_model=CuestionarioPublico,
    summary="Cuestionario para responder, sin las respuestas correctas",
)
async def obtener_cuestionario(
    token: str, db: AsyncSession = Depends(get_db)
) -> CuestionarioPublico:
    """Devuelve el cuestionario si existe y está activo."""
    cuestionario = await intento_service.obtener_cuestionario_publico(db, token)

    return CuestionarioPublico(
        nombre=cuestionario.nombre,
        descripcion=cuestionario.descripcion,
        total_preguntas=len(cuestionario.preguntas),
        preguntas=[
            PreguntaPublica.model_validate(pregunta)
            for pregunta in cuestionario.preguntas
        ],
    )


@router.post(
    "/{token}/intento",
    response_model=IntentoIniciado,
    status_code=status.HTTP_201_CREATED,
    summary="Inicia un intento con los datos de identidad",
)
async def iniciar_intento(
    token: str,
    datos: IniciarIntentoIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> IntentoIniciado:
    """Crea el intento y devuelve su id, que el cliente guarda localmente."""
    user_agent = request.headers.get("user-agent")

    intento, cuestionario = await intento_service.crear_intento(
        db,
        token,
        datos,
        ip_origen=_ip_valida(request),
        user_agent=user_agent[:MAX_USER_AGENT] if user_agent else None,
    )

    logger.info(
        "Intento iniciado: empleado=%s area=%s cuestionario=%s",
        datos.numero_empleado,
        datos.area,
        cuestionario.nombre,
    )

    return IntentoIniciado(
        intento_id=intento.id,
        nombre=intento.nombre,
        total_preguntas=intento.total_preguntas,
    )


@router.get(
    "/intento/{intento_id}",
    response_model=EstadoIntento,
    summary="Estado del intento para restaurarlo tras recargar",
)
async def estado_intento(
    intento_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> EstadoIntento:
    """Devuelve las respuestas ya guardadas, sin marcas de acierto.

    Lo necesita el formulario para reconstruir lo contestado cuando el
    operador recarga la página o pierde la conexión a media evaluación.
    """
    intento = await intento_service.obtener_intento(db, intento_id)
    respuestas = await intento_service.obtener_respuestas(db, intento_id)

    return EstadoIntento(
        intento_id=intento.id,
        nombre=intento.nombre,
        numero_empleado=intento.numero_empleado,
        area=intento.area,
        finalizado=intento.finalizado_at is not None,
        respuestas=respuestas,
    )


@router.patch(
    "/intento/{intento_id}",
    response_model=RespuestaGuardada,
    summary="Autoguardado de una respuesta",
)
async def guardar_respuesta(
    intento_id: uuid.UUID,
    datos: GuardarRespuestaIn,
    db: AsyncSession = Depends(get_db),
) -> RespuestaGuardada:
    """Guarda la opción elegida. La respuesta no revela si fue correcta."""
    await intento_service.guardar_respuesta(
        db, intento_id, datos.pregunta_id, datos.opcion_id
    )

    return RespuestaGuardada(
        pregunta_id=datos.pregunta_id, opcion_id=datos.opcion_id
    )


@router.post(
    "/intento/{intento_id}/finalizar",
    response_model=ResultadoIntento,
    summary="Cierra el intento y calcula el puntaje",
)
async def finalizar_intento(
    intento_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ResultadoIntento:
    """Calcula el resultado en el servidor y lo devuelve."""
    intento = await intento_service.finalizar_intento(db, intento_id)

    logger.info(
        "Intento finalizado: empleado=%s puntaje=%s",
        intento.numero_empleado,
        intento.puntaje,
    )

    if intento.finalizado_at is None:
        # No debería ocurrir: finalizar_intento siempre lo asigna. Se maneja
        # de forma explícita en lugar de con un assert, que desaparece al
        # ejecutar Python optimizado.
        raise ConflictoDeNegocio("No se pudo cerrar el intento. Intenta de nuevo.")

    return ResultadoIntento(
        intento_id=intento.id,
        nombre=intento.nombre,
        total_preguntas=intento.total_preguntas,
        correctas=intento.correctas,
        puntaje=intento.puntaje if intento.puntaje is not None else 0,
        aprobado=intento_service.calcular_aprobado(intento.puntaje),
        umbral_aprobacion=settings.UMBRAL_APROBACION,
        finalizado_at=intento.finalizado_at,
    )
