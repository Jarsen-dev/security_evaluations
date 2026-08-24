"""Versión imprimible del cuestionario, para contestarlo en papel.

Sirve para quien no trae celular a su turno. El PDF sale en blanco: **no
marca cuál es la respuesta correcta**, porque la hoja se le entrega a quien
va a contestar.

Se genera con reportlab, que es Python puro y no arrastra dependencias del
sistema al contenedor.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import RUTA_LOGO, hay_logo
from app.core.constants import AREAS
from app.models.cuestionario import Cuestionario

AZUL = colors.HexColor("#1F4E79")
GRIS = colors.HexColor("#6B7683")
GRIS_LINEA = colors.HexColor("#B8C0C8")

MARGEN = 18 * mm
# Cuadro vacío que se marca con lápiz. El carácter ☐ no existe en las fuentes
# base de reportlab, así que se dibuja con un Table de una celda.
LADO_CASILLA = 3.6 * mm


def _estilos() -> dict[str, ParagraphStyle]:
    """Estilos del documento, derivados de los de reportlab."""
    base = getSampleStyleSheet()

    return {
        "titulo": ParagraphStyle(
            "titulo",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=AZUL,
            spaceAfter=2,
            alignment=TA_LEFT,
        ),
        "descripcion": ParagraphStyle(
            "descripcion",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=GRIS,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "instrucciones": ParagraphStyle(
            "instrucciones",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.black,
        ),
        "campo": ParagraphStyle(
            "campo", parent=base["Normal"], fontSize=10, leading=20
        ),
        "etiqueta": ParagraphStyle(
            "etiqueta",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=GRIS,
        ),
        "pregunta": ParagraphStyle(
            "pregunta",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            spaceAfter=3,
        ),
        "opcion": ParagraphStyle(
            "opcion", parent=base["Normal"], fontSize=10, leading=14
        ),
        "area": ParagraphStyle(
            "area", parent=base["Normal"], fontSize=9, leading=12
        ),
    }


ALTO_LOGO = 15 * mm


def _encabezado(
    cuestionario: Cuestionario, estilos: dict[str, ParagraphStyle], ancho: float
) -> list:
    """Logo a la izquierda; título y descripción a su derecha.

    Si el logo no está en disco, el título ocupa todo el ancho: la ausencia
    del archivo no debe impedir imprimir el cuestionario.
    """
    texto: list = [Paragraph(_escapar(cuestionario.nombre), estilos["titulo"])]

    if cuestionario.descripcion:
        texto.append(
            Paragraph(_escapar(cuestionario.descripcion), estilos["descripcion"])
        )

    if not hay_logo():
        return texto

    imagen = Image(str(RUTA_LOGO))
    # Se escala por altura conservando la proporción original del archivo.
    proporcion = imagen.imageWidth / imagen.imageHeight
    imagen.drawHeight = ALTO_LOGO
    imagen.drawWidth = ALTO_LOGO * proporcion
    imagen.hAlign = "LEFT"

    separacion = 6 * mm
    ancho_logo = imagen.drawWidth

    tabla = Table(
        [[imagen, texto]],
        colWidths=[ancho_logo + separacion, ancho - ancho_logo - separacion],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), separacion),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    return [tabla]


def _casilla() -> Table:
    """Cuadro vacío para marcar con lápiz."""
    caja = Table([[""]], colWidths=[LADO_CASILLA], rowHeights=[LADO_CASILLA])
    caja.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return caja


def _bloque_identidad(estilos: dict[str, ParagraphStyle], ancho: float) -> list:
    """Los tres campos fijos, como líneas y casillas para llenar a mano."""
    elementos: list = []

    # Columnas alternadas campo/separador: así cada línea para escribir queda
    # visualmente separada de la siguiente, en vez de correrse de lado a lado
    # como si fuera un solo campo.
    separacion = 6 * mm
    ancho_campos = ancho - 2 * separacion

    datos = [
        [
            Paragraph("NOMBRE COMPLETO", estilos["etiqueta"]),
            "",
            Paragraph("NÚMERO DE EMPLEADO", estilos["etiqueta"]),
            "",
            Paragraph("FECHA", estilos["etiqueta"]),
        ],
        # Fila vacía: la línea se dibuja con LINEBELOW en vez de con guiones
        # bajos, que se desbordan y saltan de renglón.
        ["", "", "", "", ""],
    ]

    tabla = Table(
        datos,
        colWidths=[
            ancho_campos * 0.46,
            separacion,
            ancho_campos * 0.30,
            separacion,
            ancho_campos * 0.24,
        ],
        rowHeights=[None, 9 * mm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                ("LINEBELOW", (0, 1), (0, 1), 0.6, colors.black),
                ("LINEBELOW", (2, 1), (2, 1), 0.6, colors.black),
                ("LINEBELOW", (4, 1), (4, 1), 0.6, colors.black),
            ]
        )
    )
    elementos.append(tabla)
    elementos.append(Spacer(1, 6))

    # Área: las 8 opciones del catálogo, en dos filas de cuatro. Se marcan
    # igual que las respuestas, para que la hoja se lea de una sola forma.
    elementos.append(Paragraph("ÁREA (marca una)", estilos["etiqueta"]))
    elementos.append(Spacer(1, 3))

    celdas: list[list] = []
    for inicio in range(0, len(AREAS), 4):
        fila: list = []
        for area in AREAS[inicio : inicio + 4]:
            fila.append(_casilla())
            fila.append(Paragraph(area.label, estilos["area"]))
        while len(fila) < 8:
            fila.extend(["", ""])
        celdas.append(fila)

    ancho_casilla = 6 * mm
    ancho_texto = (ancho - 4 * ancho_casilla) / 4

    tabla_areas = Table(
        celdas, colWidths=[ancho_casilla, ancho_texto] * 4
    )
    tabla_areas.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elementos.append(tabla_areas)

    return elementos


def _bloque_pregunta(
    numero: int,
    texto: str,
    opciones: list[str],
    puntos: int,
    estilos: dict[str, ParagraphStyle],
    ancho: float,
) -> KeepTogether:
    """Una pregunta con sus opciones.

    Va envuelta en ``KeepTogether`` para que nunca se parta entre dos hojas:
    una pregunta cuyo enunciado queda en una página y sus opciones en la
    siguiente es un problema real al contestar en papel.
    """
    elementos: list = []

    sufijo = f"  ({puntos} puntos)" if puntos != 1 else ""
    elementos.append(
        Paragraph(f"{numero}. {_escapar(texto)}{sufijo}", estilos["pregunta"])
    )

    filas = [[_casilla(), Paragraph(_escapar(opcion), estilos["opcion"])] for opcion in opciones]

    tabla = Table(filas, colWidths=[8 * mm, ancho - 8 * mm])
    tabla.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 6),
                ("LEFTPADDING", (1, 0), (1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    elementos.append(tabla)
    elementos.append(Spacer(1, 9))

    return KeepTogether(elementos)


def _escapar(texto: str) -> str:
    """Escapa lo que reportlab interpretaría como marcado."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generar_pdf_cuestionario(cuestionario: Cuestionario) -> BytesIO:
    """Arma el cuestionario imprimible y lo devuelve en memoria."""
    estilos = _estilos()
    flujo = BytesIO()

    ancho_util = letter[0] - 2 * MARGEN

    documento = BaseDocTemplate(
        flujo,
        pagesize=letter,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN,
        bottomMargin=MARGEN + 8 * mm,
        title=f"Cuestionario — {cuestionario.nombre}",
        author="Sistema ESH",
    )

    def pie_de_pagina(lienzo, doc) -> None:
        """Nombre del cuestionario y número de página en cada hoja."""
        lienzo.saveState()
        lienzo.setFont("Helvetica", 7.5)
        lienzo.setFillColor(GRIS)

        y = MARGEN * 0.6
        lienzo.drawString(MARGEN, y, cuestionario.nombre[:70])
        lienzo.drawRightString(letter[0] - MARGEN, y, f"Página {doc.page}")

        lienzo.setStrokeColor(GRIS_LINEA)
        lienzo.setLineWidth(0.4)
        lienzo.line(MARGEN, y + 5 * mm, letter[0] - MARGEN, y + 5 * mm)
        lienzo.restoreState()

    marco = Frame(
        documento.leftMargin,
        documento.bottomMargin,
        ancho_util,
        letter[1] - documento.topMargin - documento.bottomMargin,
        id="normal",
    )
    documento.addPageTemplates(
        [PageTemplate(id="hoja", frames=[marco], onPage=pie_de_pagina)]
    )

    contenido: list = _encabezado(cuestionario, estilos, ancho_util)
    contenido.append(Spacer(1, 8))
    contenido.extend(_bloque_identidad(estilos, ancho_util))
    contenido.append(Spacer(1, 10))

    contenido.append(
        Paragraph(
            "Marca con una X la opción correcta. Solo una por pregunta.",
            estilos["instrucciones"],
        )
    )
    contenido.append(Spacer(1, 10))

    for indice, pregunta in enumerate(cuestionario.preguntas, start=1):
        contenido.append(
            _bloque_pregunta(
                indice,
                pregunta.texto,
                [opcion.texto for opcion in pregunta.opciones],
                pregunta.puntos,
                estilos,
                ancho_util,
            )
        )

    documento.build(contenido)
    flujo.seek(0)

    return flujo
