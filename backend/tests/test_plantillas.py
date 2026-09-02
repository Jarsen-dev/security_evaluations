"""Pruebas del corpus de formatos de recepción.

Es el camino que el operador percibía como «no guarda nada» y hasta ahora no
tenía ninguna prueba. Lo que se cubre aquí es la regla que más se rompía: una
hoja con dos remisiones son **dos guardados con la misma foto**, y sin
comparar el texto el segundo duplicaba el ejemplo y el tercero se estrellaba
contra el tope, perdiendo todo lo de ese guardado.

Sin base de datos, como el resto de la suite: la decisión vive en una función
pura y el comportamiento contra Postgres se comprueba con el guion de punta a
punta que acompaña al cambio.
"""

import json
import time
from pathlib import Path

import pytest

from app.services import espejo_formatos
from app.services.espejo_formatos import carpetas_a_borrar
from app.services.ocr_recepciones import MAX_EJEMPLOS_CURADOS, slugify
from app.services.plantilla_service import (
    DEMASIADOS_CURADOS,
    YA_APRENDIDO,
    decidir_ejemplo_curado,
)

TEXTO = "REMISION MGPHARMA SA DE CV\nFolio: 26906\nQUITADOL 500MG C/10 TAB   8\n"
OTRO = "DEPARTURE SHEET BOREAL SAFETY\nDoc: BS-99812\nRespirador media cara  15\n"


def test_el_primer_ejemplo_se_guarda() -> None:
    assert decidir_ejemplo_curado(TEXTO, []) is None


def test_la_misma_hoja_no_se_guarda_dos_veces() -> None:
    """Y no es un error: es el segundo documento de la misma foto."""
    assert decidir_ejemplo_curado(TEXTO, [TEXTO]) == YA_APRENDIDO


def test_una_hoja_distinta_si_se_guarda() -> None:
    assert decidir_ejemplo_curado(OTRO, [TEXTO]) is None


def test_el_tope_solo_lo_alcanzan_hojas_distintas() -> None:
    curados = [TEXTO, OTRO][:MAX_EJEMPLOS_CURADOS]
    assert decidir_ejemplo_curado("una tercera hoja", curados) == DEMASIADOS_CURADOS


def test_el_tope_no_estorba_si_la_hoja_ya_estaba() -> None:
    """Con el corpus lleno, repetir una hoja conocida sigue sin ser un error.

    Importa porque un formato con sus dos ejemplos es el caso normal, y ahí
    cada documento adicional de una misma foto pasaría por aquí.
    """
    curados = [TEXTO, OTRO][:MAX_EJEMPLOS_CURADOS]
    assert decidir_ejemplo_curado(TEXTO, curados) == YA_APRENDIDO


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("MGPharma Remisión", "mgpharma_remision"),
        ("Departure Sheet (General)", "departure_sheet_general"),
        ("###", ""),
        ("   ", ""),
        ("한국어", ""),
    ],
)
def test_el_identificador_sale_del_nombre(nombre: str, esperado: str) -> None:
    """Un nombre que no deja identificador se rechaza al registrar.

    El campo del formulario solo exige que no esté en blanco, así que un
    nombre de puros símbolos —o en hangul, que la app admite— llegaría hasta
    aquí y hay que decirlo, no tragárselo.
    """
    assert slugify(nombre) == esperado


# --- El espejo en disco -----------------------------------------------------
#
# Los ejemplos se escriben además como archivos, para poder revisarlos sin
# pantalla. Es una copia y no la fuente, así que lo que más importa probar es
# que no puede tumbar una recepción y que la rotación borra lo que debe: son
# directorios enteros.

FECHAS = [
    "20260901-100000",
    "20260901-110000",
    "20260902-090000",
    "20260902-100000",
    "20260902-110000",
    "20260902-120000",
]


def test_con_sitio_de_sobra_no_borra_nada() -> None:
    assert carpetas_a_borrar(FECHAS[:2], tope=4) == []


def test_al_llegar_al_tope_deja_sitio_para_el_que_entra() -> None:
    """Con cuatro guardadas, la quinta obliga a soltar la más vieja."""
    assert carpetas_a_borrar(FECHAS[:4], tope=4) == [FECHAS[0]]


def test_borra_las_mas_viejas_y_conserva_las_recientes() -> None:
    sobran = carpetas_a_borrar(FECHAS, tope=4)
    assert sobran == FECHAS[:3]
    assert len(set(FECHAS) - set(sobran)) == 3  # + la que entra = 4


def test_el_orden_lo_decide_la_fecha_no_el_sistema_de_archivos() -> None:
    """Da igual cómo lleguen listadas: se ordenan por nombre, que es la fecha."""
    revueltas = [FECHAS[3], FECHAS[0], FECHAS[5], FECHAS[1]]
    assert carpetas_a_borrar(revueltas, tope=2) == [FECHAS[0], FECHAS[1], FECHAS[3]]


def test_guarda_la_foto_el_json_y_el_texto(tmp_path: Path) -> None:
    espejo_formatos.guardar_ejemplo(
        slug="mgpharma_remision",
        nombre="MGPharma Remisión",
        imagen=b"\xff\xd8\xff bytes de la foto",
        tipo_mime="image/jpeg",
        texto_ocr=TEXTO,
        json_esperado={"folio": "26906", "items": []},
        raiz=tmp_path,
    )

    carpeta = tmp_path / "mgpharma_remision"
    ejemplo = next(hijo for hijo in carpeta.iterdir() if hijo.is_dir())

    assert (ejemplo / "remision.jpg").read_bytes().startswith(b"\xff\xd8\xff")
    assert json.loads((ejemplo / "extraido.json").read_text())["folio"] == "26906"
    assert (ejemplo / "texto_ocr.txt").read_text() == TEXTO
    # El nombre legible vive dentro: la carpeta se llama por el identificador.
    assert "MGPharma Remisión" in (carpeta / "formato.txt").read_text()


def test_rota_de_verdad_sobre_el_disco(tmp_path: Path) -> None:
    for indice in range(6):
        espejo_formatos.guardar_ejemplo(
            slug="rotacion",
            nombre="Rotación",
            imagen=b"foto",
            tipo_mime="image/png",
            texto_ocr=f"hoja {indice}",
            json_esperado={},
            raiz=tmp_path,
        )
        # El sello de tiempo tiene resolución de segundo: sin esto las seis
        # caerían en la misma carpeta y no habría nada que rotar.
        time.sleep(1.05)

    ejemplos = [h for h in (tmp_path / "rotacion").iterdir() if h.is_dir()]
    assert len(ejemplos) == espejo_formatos.MAX_EJEMPLOS_DISCO
    textos = sorted((h / "texto_ocr.txt").read_text() for h in ejemplos)
    assert textos == ["hoja 2", "hoja 3", "hoja 4", "hoja 5"]


def test_si_el_disco_falla_no_tumba_la_recepcion(tmp_path: Path) -> None:
    """Un fichero donde debería ir la carpeta: imposible escribir, y da igual."""
    (tmp_path / "estorbo").write_text("no soy un directorio")

    espejo_formatos.guardar_ejemplo(
        slug="estorbo",
        nombre="Estorbo",
        imagen=b"foto",
        tipo_mime="image/jpeg",
        texto_ocr=TEXTO,
        json_esperado={},
        raiz=tmp_path,
    )
