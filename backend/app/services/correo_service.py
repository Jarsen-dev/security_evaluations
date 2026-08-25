"""Envío de correo saliente.

Se usa ``aiosmtplib`` y no el ``smtplib`` de la biblioteca estándar porque este
último es bloqueante: mientras negocia TLS y espera al servidor de correo
detendría el bucle de eventos y con él toda la API.
"""

import logging
from datetime import date
from email.message import EmailMessage
from io import BytesIO

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ErrorDeNegocio
from app.services import rondin_service, rondines_excel

logger = logging.getLogger(__name__)

TIPO_EXCEL_PRINCIPAL = "application"
TIPO_EXCEL_SUB = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CORREO_NO_CONFIGURADO = (
    "El envío de correo no está configurado. Captura las variables SMTP_* "
    "en el archivo .env del proyecto."
)


async def enviar(
    *,
    destinatarios: list[str],
    asunto: str,
    cuerpo: str,
    adjunto: BytesIO | None = None,
    nombre_adjunto: str | None = None,
) -> None:
    """Manda un correo con un adjunto opcional.

    Lanza ``ErrorDeNegocio`` si falta configuración o si el servidor rechaza
    el envío, para que la ruta lo traduzca a un 422 con el motivo en español
    en vez de un 500 sin explicación.
    """
    if not settings.correo_configurado:
        raise ErrorDeNegocio(CORREO_NO_CONFIGURADO)

    if not destinatarios:
        raise ErrorDeNegocio("No hay destinatarios a quién enviar el reporte.")

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = settings.remitente
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(cuerpo)

    if adjunto is not None and nombre_adjunto:
        mensaje.add_attachment(
            adjunto.getvalue(),
            maintype=TIPO_EXCEL_PRINCIPAL,
            subtype=TIPO_EXCEL_SUB,
            filename=nombre_adjunto,
        )

    try:
        await aiosmtplib.send(
            mensaje,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PUERTO,
            username=settings.SMTP_USUARIO or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=settings.SMTP_SSL,
            start_tls=not settings.SMTP_SSL,
        )
    except Exception as exc:
        # El detalle técnico va al log; al usuario se le da algo accionable.
        logger.exception("Fallo al enviar correo a %s", destinatarios)
        raise ErrorDeNegocio(
            "No se pudo enviar el correo. Revisa la configuración del "
            "servidor y que la contraseña de aplicación siga vigente."
        ) from exc

    logger.info("Correo enviado a %s: %s", destinatarios, asunto)


async def enviar_reporte_rondines(
    db: AsyncSession,
    fecha: date,
    turno: str,
    *,
    destinatarios: list[str],
) -> None:
    """Arma el Excel del turno y lo manda adjunto."""
    tablero = await rondin_service.construir_tablero(db, fecha, turno)
    flujo = rondines_excel.generar_excel(tablero)

    etiqueta = rondines_excel.ETIQUETAS_TURNO.get(turno, turno)
    inicio = tablero["inicio"]
    fin = tablero["fin"]

    await enviar(
        destinatarios=destinatarios,
        asunto=f"Reporte de rondines — {fecha:%d/%m/%Y} turno {etiqueta}",
        cuerpo=(
            f"Reporte de rondines de seguridad.\n\n"
            f"Turno {etiqueta}: {inicio:%d/%m/%Y %H:%M} a {fin:%d/%m/%Y %H:%M}\n"
            f"Cumplimiento: {tablero['cumplimiento']:.1f}% "
            f"({tablero['visitados']} de {tablero['total']} visitas)\n"
            f"Puntos de control activos: {tablero['puntos_activos']}\n\n"
            f"Se adjunta el detalle punto por punto.\n"
        ),
        adjunto=flujo,
        nombre_adjunto=rondines_excel.nombre_reporte(fecha, turno),
    )
