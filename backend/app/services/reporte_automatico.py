"""Reporte automático de rondines al cambio de turno.

En producción uvicorn corre con cuatro workers y esta tarea vive en **todos**:
sin candado saldrían cuatro correos idénticos cada doce horas. El candado es
una fila en ``envios_reporte_rondin`` cuya llave primaria es la clave del
turno; el primer worker que gana el ``INSERT`` envía y los demás chocan y se
callan.

Va en la base y no en memoria para que también sobreviva a un reinicio del
contenedor dentro de la ventana de envío, que es justo cuando un despliegue
suele coincidir con el cambio de turno.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.rondin import EnvioReporteRondin
from app.services import correo_service, rondin_service

logger = logging.getLogger(__name__)

#: Cada cuánto despierta la tarea. Un minuto basta para no perder la ventana.
INTERVALO_SEGUNDOS = 60

#: Minutos después del cambio de turno en los que se acepta enviar. Da margen
#: para que el contenedor arranque tras un despliegue sin saltarse el reporte.
VENTANA_MINUTOS = 5


def _turno_que_termina(ahora: datetime) -> tuple[date, str] | None:
    """Turno recién cerrado si estamos en la ventana de envío, o ``None``.

    A las 07:30 termina la noche que arrancó **el día anterior**; a las 19:30
    termina el día de hoy. Devolver la fecha de INICIO es importante: es la
    que entiende el resto del módulo.
    """
    if ahora.minute < rondin_service.MINUTO_INICIO_TURNO:
        return None
    if ahora.minute >= rondin_service.MINUTO_INICIO_TURNO + VENTANA_MINUTOS:
        return None

    if ahora.hour == rondin_service.HORA_INICIO_TURNO:
        # 07:30 — cierra la noche que empezó ayer a las 19:30.
        return (ahora.date() - timedelta(days=1)), rondin_service.TURNO_NOCHE

    if ahora.hour == rondin_service.HORA_INICIO_TURNO + rondin_service.HORAS_TURNO:
        # 19:30 — cierra el día de hoy.
        return ahora.date(), rondin_service.TURNO_DIA

    return None


async def _ganar_candado(db: AsyncSession, clave: str) -> bool:
    """Intenta reservar el envío. ``True`` solo para el primero que llega."""
    db.add(EnvioReporteRondin(clave=clave))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return False
    return True


async def _revisar() -> None:
    """Un ciclo: mira el reloj y envía si toca."""
    ahora = datetime.now(tz=rondin_service.zona())
    pendiente = _turno_que_termina(ahora)
    if pendiente is None:
        return

    fecha, turno = pendiente
    clave = f"{fecha:%Y-%m-%d}:{turno}"

    async with SessionLocal() as db:
        # Se consulta ANTES de tomar el candado: un turno sin un solo escaneo
        # (planta parada, festivo, caseta sin guardia) no merece un correo con
        # la matriz entera en rojo al 0 %, y tomar el candado para no enviar
        # nada impediría reintentarlo si más tarde sí aparecen escaneos.
        if await rondin_service.contar_escaneos(db, fecha, turno) == 0:
            logger.info("Turno %s sin escaneos: no se manda reporte", clave)
            return

        if not await _ganar_candado(db, clave):
            return

        logger.info("Enviando el reporte automático del turno %s", clave)
        try:
            await correo_service.enviar_reporte_rondines(
                db, fecha, turno, destinatarios=settings.rondines_destinatarios
            )
        except Exception:
            # El candado se queda puesto a propósito. Reintentar dentro de la
            # misma ventana volvería a fallar por lo mismo (SMTP mal
            # configurado, contraseña vencida) y llenaría el log; el fallo
            # queda registrado para revisarlo.
            logger.exception("No se pudo enviar el reporte automático %s", clave)


async def ejecutar() -> None:
    """Bucle de la tarea. Se cancela al apagar la aplicación."""
    logger.info(
        "Reporte automático de rondines activo (destinatarios: %s)",
        ", ".join(settings.rondines_destinatarios),
    )

    while True:
        try:
            await _revisar()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Cualquier fallo inesperado se registra y el bucle sigue: esta
            # tarea nunca debe tumbar el backend.
            logger.exception("Fallo en el ciclo del reporte automático")

        await asyncio.sleep(INTERVALO_SEGUNDOS)


def debe_arrancar() -> tuple[bool, str]:
    """Indica si la tarea tiene sentido, y por qué no si no lo tiene."""
    if not settings.RONDINES_REPORTE_AUTOMATICO:
        return False, "RONDINES_REPORTE_AUTOMATICO está apagado"
    if not settings.correo_configurado:
        return False, "falta configurar el servidor de correo (SMTP_*)"
    if not settings.rondines_destinatarios:
        return False, "no hay destinatarios en RONDINES_DESTINATARIOS"
    return True, ""
