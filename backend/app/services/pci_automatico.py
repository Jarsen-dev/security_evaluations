"""Cierre automático de los meses sin respuesta del control PCI MTTO.

Cuando un mes termina sin que nadie conteste si se hizo el mantenimiento al
sistema contra incendios, esta tarea levanta el registro con ``realizado =
false`` y el motivo en blanco. Ese hueco es lo que el panel reclama con la
solicitud urgente y lo que anuncia la campana del encabezado, hasta que alguien
lo explique.

**Diferencia de fondo con el reporte automático de rondines**, del que copia la
estructura: aquel se dispara por un *instante* —el cambio de turno, a las 07:30
y a las 19:30— y por eso necesita una ventana de minutos para no perderse el
momento tras un despliegue. Este se dispara por un *estado*: "hay meses cerrados
sin fila". Comprobarlo es idempotente y reconciliable, así que no hay ventana
que acertar y una pasada perdida se recupera sola en la siguiente.

**El candado es la restricción ``uq_pci_anio_mes``**, no una tabla aparte como
la de rondines. Ahí hace falta reservar antes de mandar un correo, que no es una
operación transaccional; aquí la reserva y el trabajo son el mismo ``INSERT``,
así que el primero de los cuatro workers de uvicorn que lo consigue cierra el
mes y los demás chocan y siguen.

**Hueco de auditoría, consciente**: este cierre no deja renglón en la bitácora.
No pasa por HTTP, y el middleware de ``core/bitacora.py`` es la única vía —
escribir desde aquí rompería esa regla y abriría la puerta a que cada servicio
audite por su cuenta. La evidencia queda en la propia fila (``automatico =
true`` y ``responsable = 'sistema'``), que es consultable, y en estos logs.
"""

import asyncio
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import pci_service
from app.services.rondin_service import ahora_local

logger = logging.getLogger(__name__)

#: Cada cuánto despierta. Una hora basta de sobra: el trabajo es idempotente y
#: el margen para cerrar un mes es de días, no de minutos.
INTERVALO_SEGUNDOS = 3600


async def _revisar() -> None:
    """Un ciclo: cierra los meses que ya vencieron y no tienen registro."""
    async with SessionLocal() as db:
        cerrados = await pci_service.cerrar_meses_vencidos(db, ahora_local())

    if cerrados:
        logger.info(
            "Cierre automático de PCI MTTO: %d mes(es) sin respuesta", cerrados
        )


async def ejecutar() -> None:
    """Bucle de la tarea. Se cancela al apagar la aplicación.

    La primera pasada va **antes** del primer ``sleep``, y es lo que cubre el
    caso de que el contenedor haya estado apagado varios meses: una tarea que
    esperara a su ventana los habría perdido para siempre.
    """
    logger.info(
        "Cierre automático de PCI MTTO activo (vigila desde %s)",
        "%d-%02d" % pci_service.PCI_PRIMER_MES,
    )

    while True:
        try:
            await _revisar()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Igual que el reporte de rondines: esta tarea nunca debe tumbar el
            # backend. Se registra y se reintenta en el siguiente ciclo.
            logger.exception("Fallo en el ciclo del cierre automático de PCI MTTO")

        await asyncio.sleep(INTERVALO_SEGUNDOS)


def debe_arrancar() -> tuple[bool, str]:
    """Si la tarea corre, y el motivo cuando no, para que el lifespan lo diga."""
    if not settings.PCI_CIERRE_AUTOMATICO:
        return False, "PCI_CIERRE_AUTOMATICO está apagado"
    return True, ""
