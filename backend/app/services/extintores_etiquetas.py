"""Etiquetas QR de los extintores, en PDF.

Se genera aquí y no en el navegador porque la etiqueta mide **3 × 3 cm
exactos**: es una medida física, y el tamaño de lo que sale de un
`window.print()` depende de la impresora y de los márgenes que traiga el
navegador. reportlab trabaja en milímetros y no admite discusión.

El QR lleva la URL que abre la revisión de ESE extintor. Es una etiqueta que se
pega al aparato y tiene que seguir funcionando dentro de un año, así que apunta
al dominio público (`NEXT_PUBLIC_BASE_URL`) y no al origen desde el que se imprimió
—que es el criterio contrario al del QR efímero de las recepciones—.
"""

from io import BytesIO

import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as reportlab_canvas

from app.core.config import settings
from app.models.extintor import Extintor

#: Lo que pidió el área: tres centímetros de lado.
LADO_QR = 30 * mm

#: Espacio del pie con el folio y la ubicación, para poder pegar la etiqueta en
#: el aparato correcto sin tener que escanearla.
ALTO_PIE = 9 * mm
MARGEN = 12 * mm
SEPARACION = 5 * mm

ANCHO_ETIQUETA = LADO_QR
ALTO_ETIQUETA = LADO_QR + ALTO_PIE


def url_de(extintor: Extintor) -> str:
    """A dónde lleva el QR pegado en el aparato."""
    base = settings.NEXT_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/controles?control=extintores&extintor={extintor.id}"


def _imagen_qr(contenido: str) -> BytesIO:
    """La matriz del QR como PNG en memoria.

    Corrección de errores media: la etiqueta vive pegada a un extintor, en una
    nave con polvo y golpes, y un QR con un roce tiene que seguir leyéndose.
    """
    codigo = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    codigo.add_data(contenido)
    codigo.make(fit=True)

    flujo = BytesIO()
    codigo.make_image(fill_color="black", back_color="white").save(flujo, format="PNG")
    flujo.seek(0)
    return flujo


def _recortar(texto: str, largo: int) -> str:
    """El pie no puede desbordar los 3 cm de ancho de la etiqueta."""
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def generar_etiquetas(extintores: list[Extintor]) -> BytesIO:
    """Una hoja carta con las etiquetas de los extintores pedidos.

    Sirve igual para una sola —«impresión individual»— que para la cola: la
    diferencia está en cuántos identificadores manda el panel, no aquí. La
    cola existe justamente para no gastar una hoja entera en un QR.
    """
    flujo = BytesIO()
    lienzo = reportlab_canvas.Canvas(flujo, pagesize=letter)
    ancho_pagina, alto_pagina = letter

    columnas = max(
        1, int((ancho_pagina - 2 * MARGEN + SEPARACION) // (ANCHO_ETIQUETA + SEPARACION))
    )
    filas = max(
        1, int((alto_pagina - 2 * MARGEN + SEPARACION) // (ALTO_ETIQUETA + SEPARACION))
    )
    por_hoja = columnas * filas

    for indice, extintor in enumerate(extintores):
        if indice > 0 and indice % por_hoja == 0:
            lienzo.showPage()

        posicion = indice % por_hoja
        columna = posicion % columnas
        fila = posicion // columnas

        x = MARGEN + columna * (ANCHO_ETIQUETA + SEPARACION)
        # reportlab cuenta desde abajo; las etiquetas se llenan de arriba abajo.
        y = alto_pagina - MARGEN - (fila + 1) * ALTO_ETIQUETA - fila * SEPARACION

        lienzo.drawImage(
            reportlab_canvas.ImageReader(_imagen_qr(url_de(extintor))),
            x,
            y + ALTO_PIE,
            width=LADO_QR,
            height=LADO_QR,
        )

        lienzo.setFont("Helvetica-Bold", 8)
        lienzo.drawCentredString(
            x + ANCHO_ETIQUETA / 2, y + ALTO_PIE - 4 * mm, _recortar(extintor.folio, 18)
        )
        lienzo.setFont("Helvetica", 6)
        lienzo.drawCentredString(
            x + ANCHO_ETIQUETA / 2,
            y + ALTO_PIE - 7 * mm,
            _recortar(f"{extintor.tipo} · {extintor.ubicacion}", 34),
        )

    lienzo.showPage()
    lienzo.save()
    flujo.seek(0)
    return flujo
