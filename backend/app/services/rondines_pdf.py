"""Hoja imprimible con los códigos QR de los puntos de control.

Se imprime, se recorta y se pega una etiqueta en cada punto de la planta. Cada
una lleva el QR, el número en grande y el nombre del punto: si alguien escanea
la etiqueta equivocada, el número le salta a la vista antes que la pantalla.
"""

from io import BytesIO

import segno
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.models.rondin import PuntoRondin

#: Etiquetas por hoja: 2 columnas × 4 filas.
COLUMNAS = 2
FILAS = 4

MARGEN = 12 * mm
LADO_QR = 45 * mm

#: Escala del QR generado por segno. Un módulo de 8 px da un PNG con
#: resolución de sobra para imprimir a 45 mm sin que se vea pixelado.
ESCALA_QR = 8


def _url_del_punto(punto: PuntoRondin) -> str:
    """La URL que lleva el código QR.

    Es corta a propósito (``/p/<token>``): cuanto menos texto, menos denso el
    código y más fácil de leer con una cámara mediocre y poca luz.
    """
    base = settings.NEXT_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/p/{punto.token_publico}"


def _dibujar_etiqueta(
    lienzo: canvas.Canvas, punto: PuntoRondin, x: float, y: float, ancho: float
) -> None:
    """Dibuja una etiqueta con su marco de recorte."""
    alto = LADO_QR + 26 * mm

    lienzo.setLineWidth(0.5)
    lienzo.setDash(2, 2)
    lienzo.rect(x, y, ancho, alto)
    lienzo.setDash()

    codigo = segno.make(_url_del_punto(punto), error="m")
    imagen = BytesIO()
    codigo.save(imagen, kind="png", scale=ESCALA_QR, border=2)
    imagen.seek(0)

    lienzo.drawImage(
        ImageReader(imagen),
        x + (ancho - LADO_QR) / 2,
        y + 20 * mm,
        width=LADO_QR,
        height=LADO_QR,
    )

    centro = x + ancho / 2

    lienzo.setFont("Helvetica-Bold", 22)
    lienzo.drawCentredString(centro, y + 11 * mm, f"PUNTO {punto.numero}")

    lienzo.setFont("Helvetica", 10)
    lienzo.drawCentredString(centro, y + 5.5 * mm, punto.nombre[:42])

    if punto.ubicacion:
        lienzo.setFont("Helvetica-Oblique", 8)
        lienzo.drawCentredString(centro, y + 1.5 * mm, punto.ubicacion[:48])


def generar_hoja_qr(puntos: list[PuntoRondin]) -> BytesIO:
    """Arma el PDF con una etiqueta por punto activo."""
    flujo = BytesIO()
    lienzo = canvas.Canvas(flujo, pagesize=letter)
    ancho_pagina, alto_pagina = letter

    ancho_celda = (ancho_pagina - 2 * MARGEN) / COLUMNAS
    alto_celda = (alto_pagina - 2 * MARGEN) / FILAS
    por_hoja = COLUMNAS * FILAS

    for indice, punto in enumerate(puntos):
        if indice and indice % por_hoja == 0:
            lienzo.showPage()

        posicion = indice % por_hoja
        columna = posicion % COLUMNAS
        fila = posicion // COLUMNAS

        x = MARGEN + columna * ancho_celda
        # ReportLab mide desde abajo; las filas se llenan de arriba hacia abajo.
        y = alto_pagina - MARGEN - (fila + 1) * alto_celda

        _dibujar_etiqueta(lienzo, punto, x, y, ancho_celda)

    lienzo.save()
    flujo.seek(0)
    return flujo
