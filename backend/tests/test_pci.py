"""Pruebas de la lógica pura del control PCI MTTO.

Ninguna toca la base de datos. `meses_a_cerrar` decide qué meses cierra sola la
vigilancia automática, y es lo único de ese mecanismo que se puede probar sin
esperar a que pase un mes de verdad: si se equivoca, o el histórico se llena de
faltas inventadas, o deja huecos que nadie vuelve a mirar.

`sanear_nombre` va aquí por otra razón: el nombre del reporte lo pone quien
sube el archivo y acaba dentro de una cabecera HTTP.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.pci_service import (
    PCI_PRIMER_MES,
    meses_a_cerrar,
    nombre_de_mes,
    sanear_nombre,
    validar_reporte,
)

ZONA = ZoneInfo("America/Monterrey")
PRIMERO = (2026, 9)


def _momento(anio: int, mes: int, dia: int, hora: int = 12) -> datetime:
    """Un instante en la hora de la planta, que es la que decide el mes."""
    return datetime(anio, mes, dia, hora, tzinfo=ZONA)


# --- meses_a_cerrar --------------------------------------------------------


def test_el_mes_en_curso_nunca_se_cierra() -> None:
    """A media septiembre todavía se puede contestar septiembre."""
    assert meses_a_cerrar(PRIMERO, _momento(2026, 9, 15), set()) == []


def test_no_inventa_historial_antes_del_estreno() -> None:
    """El control arranca en su primer mes; lo anterior no existió."""
    assert meses_a_cerrar(PRIMERO, _momento(2026, 8, 31), set()) == []


def test_el_margen_de_gracia_cubre_el_cambio_de_mes() -> None:
    """A las 00:30 del día 1 todavía no se cierra; a las 01:30 sí.

    Es lo que protege al operador que está subiendo un reporte de 10 MB a las
    23:59:40 del último día: sin margen, pierde la subida contra el cierre.
    """
    assert meses_a_cerrar(PRIMERO, _momento(2026, 10, 1, 0), set()) == []
    assert meses_a_cerrar(PRIMERO, _momento(2026, 10, 1, 1), set()) == [(2026, 9)]


def test_la_hora_local_manda_sobre_la_utc() -> None:
    """Las 23:00 del día 30 en la planta son las 05:00 UTC del día 1.

    Calculado en UTC, ese instante cerraría septiembre seis horas antes de
    tiempo, con el operador todavía a tiempo de capturarlo.
    """
    fin_de_mes = _momento(2026, 9, 30, 23)
    assert fin_de_mes.astimezone(ZoneInfo("UTC")).month == 10
    assert meses_a_cerrar(PRIMERO, fin_de_mes, set()) == []


def test_cierra_el_mes_ya_vencido() -> None:
    assert meses_a_cerrar(PRIMERO, _momento(2026, 10, 15), set()) == [(2026, 9)]


def test_varios_meses_seguidos_salen_todos_y_en_orden() -> None:
    """Un hueco de cuatro meses no puede dejar tres invisibles."""
    assert meses_a_cerrar(PRIMERO, _momento(2027, 1, 3), set()) == [
        (2026, 9),
        (2026, 10),
        (2026, 11),
        (2026, 12),
    ]


def test_omite_los_meses_que_ya_tienen_registro() -> None:
    assert meses_a_cerrar(PRIMERO, _momento(2027, 1, 3), {(2026, 10)}) == [
        (2026, 9),
        (2026, 11),
        (2026, 12),
    ]


def test_no_repite_un_mes_ya_cerrado() -> None:
    """Correr la tarea dos veces seguidas no debe duplicar nada."""
    existentes = {(2026, 9)}
    assert meses_a_cerrar(PRIMERO, _momento(2026, 10, 15), existentes) == []


def test_el_primer_mes_del_catalogo_es_el_que_se_vigila() -> None:
    """La constante del catálogo y la que usa la tarea son la misma."""
    assert PCI_PRIMER_MES == PRIMERO


# --- sanear_nombre ---------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("reporte.pdf", "reporte.pdf"),
        # Rutas: solo sobrevive el nombre del archivo.
        ("/etc/passwd", "passwd"),
        ("C:\\Users\\op\\reporte.docx", "reporte.docx"),
        ("../../../secreto.pdf", "secreto.pdf"),
        # Lo que rompería la cabecera Content-Disposition.
        ('re"porte.pdf', "reporte.pdf"),
        ("reporte\r\nX-Inyectada: si.pdf", "reporteX-Inyectada: si.pdf"),
        ("reporte\x00.pdf", "reporte.pdf"),
        # Nunca devuelve vacío: el nombre acaba en una cabecera.
        ("", "reporte"),
        ("...", "reporte"),
        (None, "reporte"),
    ],
)
def test_sanear_nombre(entrada: str | None, esperado: str) -> None:
    assert sanear_nombre(entrada) == esperado


def test_sanear_nombre_recorta_a_la_columna() -> None:
    assert len(sanear_nombre("a" * 400 + ".pdf")) == 255


# --- validar_reporte -------------------------------------------------------


def test_el_tipo_sale_de_la_extension_no_del_navegador() -> None:
    """Windows y Android mandan octet-stream para un .docx con naturalidad."""
    _, nombre, tipo = validar_reporte(b"contenido", "informe.docx")
    assert nombre == "informe.docx"
    assert tipo.endswith("wordprocessingml.document")


def test_un_formato_desconocido_se_acepta_como_generico() -> None:
    """El control admite cualquier formato: el proveedor entrega lo que entrega."""
    _, _, tipo = validar_reporte(b"contenido", "informe.rar")
    assert tipo == "application/octet-stream"


def test_un_reporte_vacio_se_rechaza() -> None:
    from app.core.errors import ErrorDeNegocio

    with pytest.raises(ErrorDeNegocio):
        validar_reporte(b"", "informe.pdf")


def test_un_reporte_enorme_se_rechaza_con_mensaje_en_espanol() -> None:
    from app.core.errors import ErrorDeNegocio

    with pytest.raises(ErrorDeNegocio, match="10 MB"):
        validar_reporte(b"x" * (11 * 1024 * 1024), "informe.pdf")


# --- nombre_de_mes ---------------------------------------------------------


def test_los_meses_van_en_espanol() -> None:
    """El locale del contenedor es C: `strftime("%B")` diría "September"."""
    assert nombre_de_mes(9) == "septiembre"
    assert nombre_de_mes(12) == "diciembre"
