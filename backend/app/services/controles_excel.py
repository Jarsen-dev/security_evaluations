"""Exportación de los controles ESH a Excel, con el formato de las hojas en papel.

Se generan en memoria (``BytesIO``) y se devuelven con ``StreamingResponse``:
nada toca el disco del servidor, igual que el resto de las exportaciones.

La idea es que quien reciba el archivo reconozca la hoja que llenaba a mano,
así que se respetan los títulos, el orden de las columnas y las notas al pie
del formato original.
"""

from datetime import date, timedelta
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ImagenExcel
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from app.core.constants import etiqueta_area
from app.core.controles_catalogo import (
    PUNTOS_SQP,
    RAYSER_NORMAL,
    RENGLONES_SUSTANCIAS,
)
from app.models.control import InspeccionSqp
from app.services.exportacion_comun import (
    BORDE_FINO,
    FUENTE_ENCABEZADO,
    FUENTE_TITULO,
    GRIS,
    RELLENO_ENCABEZADO,
    ajustar_anchos,
    escribir_encabezados,
)

# Rellenos del semáforo. Son los mismos tres colores que pinta la tabla del
# panel, para que el Excel y la pantalla no se contradigan.
RELLENOS_SEMAFORO: dict[str, PatternFill] = {
    "verde": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    "rojo": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
    "naranja": PatternFill(start_color="FFE0B2", end_color="FFE0B2", fill_type="solid"),
}

FUENTES_SEMAFORO: dict[str, Font] = {
    "verde": Font(color="006100"),
    "rojo": Font(bold=True, color="9C0006"),
    "naranja": Font(bold=True, color="9C5700"),
}

RELLENO_SECCION = PatternFill(start_color=GRIS, end_color=GRIS, fill_type="solid")

# Lado mayor de la evidencia dentro de la hoja, en píxeles. Una foto de celular
# a tamaño completo ocuparía varias pantallas de alto.
ANCHO_EVIDENCIA = 420

# Nombres de mes en español: `strftime("%B")` depende del locale del
# contenedor, que es C y devolvería "August".
MESES: tuple[str, ...] = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


def _dias_del_rango(desde: date, hasta: date) -> list[date]:
    """Todos los días del periodo, incluidos los extremos."""
    total = (hasta - desde).days + 1
    return [desde + timedelta(days=indice) for indice in range(total)]


def _mismo_mes(desde: date, hasta: date) -> bool:
    """``True`` si el periodo cabe en un solo mes natural."""
    return desde.year == hasta.year and desde.month == hasta.month


# --- Rayser ----------------------------------------------------------------


def _hoja_rayser(
    hoja: Worksheet, registros: list[dict[str, Any]], desde: date, hasta: date, periodo: str
) -> None:
    """Reproduce la hoja mensual de presiones."""
    hoja.title = "Rayser"

    hoja["A1"] = "CONTROL DE PRESIONES DE RAYSER"
    hoja["A1"].font = FUENTE_TITULO
    hoja.merge_cells("A1:E1")
    hoja["F1"] = f"Mes: {periodo}"
    hoja["F1"].font = Font(bold=True)

    # Con un rango dentro de un mismo mes basta el número de día, como en la
    # hoja impresa; si abarca varios, el número solo sería ambiguo.
    por_dia = _mismo_mes(desde, hasta)
    encabezados = [
        "Día" if por_dia else "Fecha",
        "Manómetro 1",
        "Manómetro 2",
        "Manómetro 3",
        "Manómetro 4",
        "Observaciones",
        "Responsable",
        "Evidencia",
    ]
    escribir_encabezados(hoja, encabezados, fila=2)

    registros_por_fecha = {registro["fecha"]: registro for registro in registros}

    fila = 3
    for dia in _dias_del_rango(desde, hasta):
        celda_dia = hoja.cell(row=fila, column=1)
        celda_dia.value = dia.day if por_dia else dia.strftime("%d/%m/%Y")
        celda_dia.alignment = Alignment(horizontal="center")
        celda_dia.border = BORDE_FINO

        registro = registros_por_fecha.get(dia)

        for indice in range(4):
            celda = hoja.cell(row=fila, column=2 + indice)
            celda.border = BORDE_FINO
            celda.alignment = Alignment(horizontal="center")

            if registro is None:
                continue

            lectura = registro["manometros"][indice]
            celda.value = float(lectura["valor"])
            celda.number_format = "0.0"
            celda.fill = RELLENOS_SEMAFORO[lectura["semaforo"]]
            celda.font = FUENTES_SEMAFORO[lectura["semaforo"]]

        celda_obs = hoja.cell(row=fila, column=6)
        celda_obs.value = registro["observaciones"] if registro else None
        celda_obs.alignment = Alignment(wrap_text=True, vertical="top")
        celda_obs.border = BORDE_FINO

        celda_resp = hoja.cell(row=fila, column=7)
        celda_resp.value = registro["responsable"] if registro else None
        celda_resp.border = BORDE_FINO

        celda_evidencia = hoja.cell(row=fila, column=8)
        if registro is not None:
            celda_evidencia.value = "Sí" if registro["tiene_foto"] else "—"
        celda_evidencia.alignment = Alignment(horizontal="center")
        celda_evidencia.border = BORDE_FINO

        fila += 1

    fila += 1
    hoja.cell(
        row=fila,
        column=1,
        value=f"La presión normal de los manómetros es de {RAYSER_NORMAL:g} psi.",
    ).font = Font(italic=True)

    fila += 2
    hoja.cell(
        row=fila, column=1, value="Nombre y firma de quien realiza la inspección:"
    ).font = Font(bold=True)

    ajustar_anchos(hoja, [12, 14, 14, 14, 14, 45, 20, 12])
    hoja.freeze_panes = "A3"


def _hoja_evidencias(
    libro: Workbook, evidencias: list[tuple[date, str, bytes]]
) -> None:
    """Hoja con las fotos de los días que salieron del rango.

    Se anclan como imágenes de la hoja, no como enlaces: el archivo se manda
    por correo y tiene que viajar completo.
    """
    hoja = libro.create_sheet("Evidencias")
    hoja["A1"] = "Evidencias fotográficas"
    hoja["A1"].font = FUENTE_TITULO
    ajustar_anchos(hoja, [70])

    fila = 3
    for fecha, responsable, contenido in evidencias:
        encabezado = hoja.cell(
            row=fila,
            column=1,
            value=f"{fecha:%d/%m/%Y} — registró: {responsable}",
        )
        encabezado.font = Font(bold=True)

        imagen = ImagenExcel(BytesIO(contenido))
        # Se conserva la proporción: deformar la foto dificulta leer la carátula
        # del manómetro.
        if imagen.width > ANCHO_EVIDENCIA:
            proporcion = ANCHO_EVIDENCIA / float(imagen.width)
            imagen.width = ANCHO_EVIDENCIA
            imagen.height = int(imagen.height * proporcion)

        hoja.add_image(imagen, f"A{fila + 1}")

        # ~19 px por fila: se deja el alto de la imagen más un respiro.
        fila += 2 + int(imagen.height / 19) + 2


def generar_excel_rayser(
    registros: list[dict[str, Any]],
    evidencias: list[tuple[date, str, bytes]],
    desde: date,
    hasta: date,
    periodo: str,
) -> BytesIO:
    """Arma el libro del control de presiones y lo devuelve en memoria."""
    libro = Workbook()
    hoja = libro.active
    if hoja is None:  # pragma: no cover
        hoja = libro.create_sheet()

    _hoja_rayser(hoja, registros, desde, hasta, periodo)

    if evidencias:
        _hoja_evidencias(libro, evidencias)

    flujo = BytesIO()
    libro.save(flujo)
    flujo.seek(0)
    return flujo


# --- Inspección de SQP -----------------------------------------------------


def _encabezado_sqp(hoja: Worksheet, inspeccion: InspeccionSqp) -> int:
    """Escribe la cabecera del formato y devuelve la primera fila libre."""
    hoja["A1"] = "INSPECCION DE SUSTANCIAS QUIMICAS PELIGROSAS"
    hoja["A1"].font = FUENTE_TITULO
    hoja["A1"].alignment = Alignment(horizontal="center")
    hoja.merge_cells("A1:G1")

    hoja["A2"] = "ENCARGADO Y CARGO"
    hoja["A2"].font = Font(bold=True)
    hoja.merge_cells("A2:C2")
    hoja["D2"] = "ÁREA"
    hoja["D2"].font = Font(bold=True)
    hoja.merge_cells("D2:E2")
    hoja["F2"] = "FECHA"
    hoja["F2"].font = Font(bold=True)
    hoja.merge_cells("F2:G2")

    encargado = inspeccion.encargado
    if inspeccion.cargo:
        encargado = f"{encargado} — {inspeccion.cargo}"

    hoja["A3"] = f"Nombre: {encargado}"
    hoja.merge_cells("A3:C3")
    hoja["D3"] = etiqueta_area(inspeccion.area)
    hoja.merge_cells("D3:E3")
    hoja["F3"] = inspeccion.fecha.strftime("%d/%m/%Y")
    hoja.merge_cells("F3:G3")

    return 5


def _tabla_puntos(hoja: Worksheet, inspeccion: InspeccionSqp, fila: int) -> int:
    """Escribe las secciones, los puntos y sus respuestas."""
    hoja.cell(row=fila, column=1, value="SUSTANCIAS QUÍMICAS").font = Font(bold=True)
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=2)
    _encabezados_puntos(hoja, fila)

    fila += 1
    seccion_escrita = ""
    respuestas = {respuesta.orden: respuesta for respuesta in inspeccion.respuestas}

    for orden, punto in enumerate(PUNTOS_SQP):
        if punto.seccion != seccion_escrita:
            seccion_escrita = punto.seccion
            celda_seccion = hoja.cell(row=fila, column=1, value=punto.seccion)
            celda_seccion.font = Font(bold=True)
            celda_seccion.fill = RELLENO_SECCION
            hoja.merge_cells(
                start_row=fila, start_column=1, end_row=fila, end_column=7
            )
            fila += 1

        respuesta = respuestas.get(orden)

        celda_codigo = hoja.cell(row=fila, column=1, value=punto.codigo)
        celda_codigo.alignment = Alignment(horizontal="center", vertical="top")
        celda_codigo.border = BORDE_FINO

        celda_texto = hoja.cell(row=fila, column=2, value=punto.texto)
        celda_texto.alignment = Alignment(wrap_text=True, vertical="top")
        celda_texto.border = BORDE_FINO

        # Una "X" en la columna elegida, como se marcaba a mano.
        for indice, valor in enumerate(("si", "no", "na")):
            celda = hoja.cell(row=fila, column=3 + indice)
            if respuesta is not None and respuesta.valor == valor:
                celda.value = "X"
                celda.font = Font(bold=True)
            celda.alignment = Alignment(horizontal="center", vertical="center")
            celda.border = BORDE_FINO

        celda_obs = hoja.cell(
            row=fila,
            column=6,
            value=respuesta.observaciones if respuesta else None,
        )
        celda_obs.alignment = Alignment(wrap_text=True, vertical="top")
        celda_obs.border = BORDE_FINO
        hoja.merge_cells(start_row=fila, start_column=6, end_row=fila, end_column=7)

        fila += 1

    return fila


def _celda_encabezado(hoja: Worksheet, fila: int, columna: int, texto: str) -> None:
    """Aplica el estilo de encabezado a una celda suelta.

    ``escribir_encabezados`` siempre arranca en la columna 1; aquí la fila ya
    trae contenido a la izquierda, así que se estila celda por celda.
    """
    celda = hoja.cell(row=fila, column=columna, value=texto)
    celda.fill = RELLENO_ENCABEZADO
    celda.font = FUENTE_ENCABEZADO
    celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    celda.border = BORDE_FINO


def _encabezados_puntos(hoja: Worksheet, fila: int) -> None:
    """Encabezados SI / NO / N/A / OBSERVACIONES de la tabla de puntos."""
    for columna, texto in ((3, "SI"), (4, "NO"), (5, "N/A"), (6, "OBSERVACIONES")):
        _celda_encabezado(hoja, fila, columna, texto)
    hoja.merge_cells(start_row=fila, start_column=6, end_row=fila, end_column=7)


def _tabla_sustancias(hoja: Worksheet, sustancias: list[str], fila: int) -> int:
    """Tabla numerada con las SQP del área."""
    fila += 1
    hoja.cell(row=fila, column=2, value="Nombre de la SQP").font = Font(bold=True)
    hoja.cell(row=fila, column=6, value="SGA").font = Font(bold=True)
    fila += 1

    # Siempre se imprimen los renglones del formato; si hay más sustancias
    # capturadas, se agregan las filas que hagan falta.
    total = max(RENGLONES_SUSTANCIAS, len(sustancias))

    for numero in range(1, total + 1):
        celda_numero = hoja.cell(row=fila, column=1, value=numero)
        celda_numero.alignment = Alignment(horizontal="center")
        celda_numero.border = BORDE_FINO

        celda_nombre = hoja.cell(
            row=fila,
            column=2,
            value=sustancias[numero - 1] if numero <= len(sustancias) else None,
        )
        celda_nombre.border = BORDE_FINO

        for columna in range(3, 8):
            hoja.cell(row=fila, column=columna).border = BORDE_FINO

        fila += 1

    return fila


def generar_excel_sqp(inspeccion: InspeccionSqp, sustancias: list[str]) -> BytesIO:
    """Arma la hoja de una inspección de SQP."""
    libro = Workbook()
    hoja = libro.active
    if hoja is None:  # pragma: no cover
        hoja = libro.create_sheet()
    hoja.title = "Inspeccion de SQP"

    fila = _encabezado_sqp(hoja, inspeccion)
    fila = _tabla_puntos(hoja, inspeccion, fila)
    fila = _tabla_sustancias(hoja, sustancias, fila)

    fila += 1
    hoja.cell(
        row=fila,
        column=1,
        value=f"Nombre de quien realiza la inspección: {inspeccion.responsable}",
    ).font = Font(bold=True)
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=5)

    ajustar_anchos(hoja, [8, 70, 6, 6, 7, 35, 12])

    flujo = BytesIO()
    libro.save(flujo)
    flujo.seek(0)
    return flujo


def titulo_periodo(desde: date, hasta: date) -> str:
    """Describe el periodo para el encabezado "Mes:" de la hoja."""
    if _mismo_mes(desde, hasta):
        return f"{MESES[desde.month - 1]} {desde.year}"
    return f"{desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
