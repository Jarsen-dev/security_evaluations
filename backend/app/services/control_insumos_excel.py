"""Excel del Control de Insumos.

Va en su propio módulo y no dentro de ``controles_excel``, que ya pasa de mil
líneas: mismo criterio que ``pci_excel`` y ``incidencias_excel``. Los estilos y
los helpers de descarga sí se comparten.
"""

from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.core.constants import etiqueta_area
from app.models.control import RegistroControlInsumos
from app.services.controles_excel import titulo_periodo
from app.services.exportacion_comun import (
    FUENTE_TITULO,
    ajustar_anchos,
    escribir_encabezados,
)
from app.services.rondin_service import zona

NOMBRE_HOJA = "Control de insumos"

ENCABEZADOS: list[str] = [
    "Fecha",
    "Hora",
    "Código",
    "Descripción",
    "Unidad",
    "Entregado a",
    "Área",
    "Consumo",
    "Descontado",
    "¿Se terminó?",
    "Responsable",
]

ANCHOS = [12, 8, 18, 44, 10, 26, 16, 10, 12, 14, 18]


def _hora_local(momento: datetime) -> str:
    """La hora a la que se registró, en la de la planta.

    No sale de `sin_zona()`, que convierte a UTC: esta columna **es** una hora,
    y verla corrida seis horas la haría inservible. Es la misma trampa que el
    tablero de rondines documenta, con otro disfraz.
    """
    return f"{momento.astimezone(zona()):%H:%M}"


def _termino(registro: RegistroControlInsumos) -> str:
    """Qué se contestó al pop-up, o un guion si la unidad no lo pregunta."""
    if registro.termino is None:
        return "—"
    return "Sí" if registro.termino else "No"


def nombre_archivo(desde: date, hasta: date) -> str:
    return f"control_insumos_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"


def generar_excel(
    registros: list[RegistroControlInsumos], desde: date, hasta: date
) -> BytesIO:
    """Arma la hoja del periodo."""
    libro = Workbook()
    hoja: Worksheet = libro.active
    hoja.title = NOMBRE_HOJA

    hoja["A1"] = "Control de Insumos"
    hoja["A1"].font = FUENTE_TITULO
    hoja["A2"] = f"Periodo: {titulo_periodo(desde, hasta)}"

    escribir_encabezados(hoja, ENCABEZADOS, fila=4)

    for registro in registros:
        hoja.append(
            [
                registro.fecha,
                _hora_local(registro.creado_at),
                registro.codigo,
                registro.descripcion,
                registro.unidad_medida,
                registro.entregado_a,
                # El área se guarda sin acentos; el reporte se lee en español.
                etiqueta_area(registro.area),
                registro.consumo,
                registro.descontado,
                _termino(registro),
                registro.responsable,
            ]
        )

    for celda in hoja["A"][4:]:
        celda.number_format = "DD/MM/YYYY"

    ajustar_anchos(hoja, ANCHOS)
    hoja.freeze_panes = "A5"

    flujo = BytesIO()
    libro.save(flujo)
    libro.close()
    flujo.seek(0)
    return flujo
