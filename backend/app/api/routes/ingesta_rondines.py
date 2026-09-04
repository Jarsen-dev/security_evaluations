"""Webhook de ingesta de los rondines capturados en AppSheet.

Cuelga de ``/api/publico`` **a propósito**, y no de un prefijo nuevo. La regla 7
de CLAUDE.md pide que un endpoint de administración nuevo cuelgue de un prefijo
ya cubierto por Cloudflare Access; este no es de administración: lo llama un Bot
de AppSheet desde la nube de Google, que no puede resolver el SSO de Access.
Estrenar prefijo propio caería justo en el fallo que la regla describe —quedaría
fuera de Access sin que nada falle de forma visible—, y encima fuera de la
bitácora y de las cuotas, las tres cosas sin quedar escritas en ningún lado.
Bajo ``/api/publico`` las tres son explícitas y ya están documentadas:

- fuera de Access, porque ``SEGURIDAD.md`` lo declara público a propósito;
- fuera de bitácora, por ``PREFIJO_EXCLUIDO`` en ``core/bitacora.py`` — y el
  escaneo ya deja su rastro en ``escaneos_rondin``, ahora con ``origen_id`` y
  ``recibido_at``;
- con la cuota holgada de ``/api/publico/rondin``, que ``_regla_para()`` aplica
  por prefijo.

La credencial es el secreto de la cabecera, no un token en la URL, así que va en
su propio módulo en vez de mezclarse con el formulario público.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ip_valida
from app.core.config import settings
from app.db.session import get_db
from app.schemas.rondin import IngestaOut, LoteEscaneosIn
from app.services import appsheet_rondines

logger = logging.getLogger(__name__)

CABECERA_SECRETO = "x-rondines-secreto"

APAGADO = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="La ingesta de rondines no está configurada en este servidor.",
)

SECRETO_INVALIDO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credencial inválida.",
)

router = APIRouter(prefix="/publico/rondin", tags=["publico"])


def _secreto_valido(request: Request) -> bool:
    """Compara el secreto en tiempo constante.

    Sobre bytes y no sobre ``str``: ``compare_digest`` con cadenas revienta con
    ``TypeError`` si llega un carácter no ASCII en la cabecera, y eso saldría
    como un 500 en vez de un 401.
    """
    recibido = request.headers.get(CABECERA_SECRETO, "")
    return hmac.compare_digest(
        recibido.encode("utf-8"), settings.RONDINES_WEBHOOK_SECRETO.encode("utf-8")
    )


@router.post(
    "/escaneos",
    response_model=IngestaOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recibe los escaneos de rondín capturados en AppSheet",
)
async def recibir_escaneos(
    lote: LoteEscaneosIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> IngestaOut:
    """Ingiere un lote de escaneos.

    Responde **202 y no 201** porque parte del lote puede ser duplicado o
    descartado: un ``201 Created`` mentiría. AppSheet solo mira que sea 2xx.

    Los renglones inválidos se cuentan en ``descartados`` y salen al log, pero
    **la respuesta sigue siendo 202**: un 4xx por una fila mala haría que
    AppSheet reintentara el lote entero para siempre, y el 2.6 % de filas
    sucias medido en el histórico garantiza que va a haber filas malas.
    """
    # Antes de comparar nada: un secreto sin capturar significa "apagado",
    # nunca "abierto". Sin esto, un despliegue sin configurar aceptaría
    # escaneos de cualquiera que adivinara la ruta.
    if not settings.ingesta_rondines_activa:
        raise APAGADO

    if not _secreto_valido(request):
        logger.warning("Ingesta de rondines: secreto inválido desde %s", ip_valida(request))
        raise SECRETO_INVALIDO

    if len(lote.escaneos) > settings.RONDINES_WEBHOOK_MAX_LOTE:
        # `client_max_body_size` de Nginx es un tope de bytes, no de filas.
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"El lote trae {len(lote.escaneos)} escaneos y el máximo es "
                f"{settings.RONDINES_WEBHOOK_MAX_LOTE}."
            ),
        )

    resultado = await appsheet_rondines.registrar_lote(
        db,
        [escaneo.a_dict() for escaneo in lote.escaneos],
        origen=appsheet_rondines.ORIGEN_WEBHOOK,
        ip=ip_valida(request),
    )

    return IngestaOut(
        recibidos=resultado.recibidos,
        insertados=resultado.insertados,
        duplicados=resultado.duplicados,
        descartados=resultado.descartados,
    )
