"""Pruebas de la lógica pura del pipeline de recepciones.

Ninguna necesita Tesseract, ni el LLM, ni base de datos: el OCR y la llamada
HTTP se parchean, y los ejemplos de plantilla se construyen a mano con texto
controlado. Así corren en cualquier máquina y en cualquier orden.
"""

import json
from typing import Any

import pytest

from app.services import ocr_recepciones as ocr
from app.services.ocr_recepciones import (
    EjemploPlantilla,
    ResultadoExtraccion,
    TIPO_DESCONOCIDO,
)

# Textos largos y bien diferenciados: el clasificador compara n-gramas de
# carácter, así que necesitan cuerpo real para que los scores signifiquen algo.
TEXTO_ACME = (
    "REMISION ACME SUMINISTROS INDUSTRIALES SA DE CV\n"
    "Folio: A-4471   Fecha: 2026-03-11\n"
    "Cliente: Cheong Woon Planta Monterrey\n"
    "CLAVE        DESCRIPCION                     CANTIDAD\n"
    "GN-100-M     Guantes de nitrilo talla M           120\n"
    "CS-220       Casco de seguridad blanco             40\n"
    "Entregado por almacen central, ruta norte.\n"
)

TEXTO_BOREAL = (
    "DEPARTURE SHEET  BOREAL SAFETY EQUIPMENT LLC\n"
    "Document No. BS-99812      Issued: 2026-03-12\n"
    "Ship to: Cheong Woon Manufacturing\n"
    "PART NUMBER   ITEM DESCRIPTION            QTY SHIPPED\n"
    "EPS-77        Respirador media cara               15\n"
    "Warehouse pickup, dock 3, inspected by QA team.\n"
)


def ejemplo(tipo: str, texto: str, *, curado: bool = True) -> EjemploPlantilla:
    return EjemploPlantilla(
        tipo=tipo,
        texto_ocr=texto,
        json_esperado={"proveedor": tipo, "folio": "X-1", "fecha": None, "items": []},
        curado=curado,
    )


# --- encontrar_campos_null -------------------------------------------------


def test_campos_null_planos() -> None:
    datos = {"proveedor": "ACME", "folio": None, "fecha": None}
    assert ocr.encontrar_campos_null(datos) == ["folio", "fecha"]


def test_campos_null_anidados_dict_en_lista_en_dict() -> None:
    """El caso que importa: null dentro de una partida dentro del documento."""
    datos = {
        "proveedor": "ACME",
        "folio": "A-1",
        "items": [
            {"codigo": "GN-100", "cantidad": 5},
            {"codigo": None, "cantidad": None},
            {"codigo": "CS-220", "cantidad": None},
        ],
    }
    assert ocr.encontrar_campos_null(datos) == [
        "items[1].codigo",
        "items[1].cantidad",
        "items[2].cantidad",
    ]


def test_campos_null_sin_nulos() -> None:
    datos = {"proveedor": "ACME", "items": [{"codigo": "A", "cantidad": 1}]}
    assert ocr.encontrar_campos_null(datos) == []


def test_campos_null_ignora_la_raiz() -> None:
    """Un null suelto sin ruta no genera una entrada vacía."""
    assert ocr.encontrar_campos_null(None) == []


# --- Parseo tolerante de JSON ----------------------------------------------


def test_json_limpio() -> None:
    assert ocr._extraer_json('{"folio": "A-1"}') == {"folio": "A-1"}


def test_json_envuelto_en_markdown() -> None:
    crudo = 'Claro, aquí tienes:\n```json\n{"folio": "A-1"}\n```\nEspero que sirva.'
    assert ocr._extraer_json(crudo) == {"folio": "A-1"}


def test_json_invalido_si_lanza() -> None:
    with pytest.raises((json.JSONDecodeError, ValueError)):
        ocr._extraer_json("no hay ningun objeto aqui")


def test_json_que_no_es_objeto_lanza() -> None:
    with pytest.raises(ValueError):
        ocr._extraer_json("[1, 2, 3]")


# --- slugify ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Remisión ACME", "remision_acme"),
        ("  Boreal   Safety  ", "boreal_safety"),
        ("Factura #123 / S.A. de C.V.", "factura_123_s_a_de_c_v"),
        ("ÑOÑO Ácido", "nono_acido"),
    ],
)
def test_slugify(entrada: str, esperado: str) -> None:
    assert ocr.slugify(entrada) == esperado


def test_slugify_recorta_a_80() -> None:
    assert len(ocr.slugify("a" * 200)) == 80


# --- Clasificación ---------------------------------------------------------


def test_clasificar_elige_el_mas_similar() -> None:
    ejemplos = [ejemplo("acme", TEXTO_ACME), ejemplo("boreal", TEXTO_BOREAL)]
    # Una foto nueva del mismo proveedor: mismo encabezado, otro folio y otra
    # partida.
    nuevo = TEXTO_ACME.replace("A-4471", "A-4620").replace("120", "80")
    assert ocr.clasificar(nuevo, ejemplos) == "acme"


def test_clasificar_bajo_umbral_es_desconocido() -> None:
    ejemplos = [ejemplo("acme", TEXTO_ACME)]
    ajeno = (
        "COMPROBANTE FISCAL DIGITAL POR INTERNET\n"
        "Regimen fiscal 601 General de Ley Personas Morales\n"
        "Uso del CFDI G03 Gastos en general\n"
    )
    assert ocr.clasificar(ajeno, ejemplos) == TIPO_DESCONOCIDO


def test_clasificar_sin_ejemplos_es_desconocido() -> None:
    assert ocr.clasificar(TEXTO_ACME, []) == TIPO_DESCONOCIDO


def test_clasificar_texto_vacio_es_desconocido() -> None:
    assert ocr.clasificar("   ", [ejemplo("acme", TEXTO_ACME)]) == TIPO_DESCONOCIDO


def test_clasificar_corpus_degenerado_no_revienta() -> None:
    """Vocabulario imposible: debe degradar a desconocido, no propagar."""
    assert ocr.clasificar("...", [ejemplo("raro", "")]) == TIPO_DESCONOCIDO


# --- debe_aprender ---------------------------------------------------------


def test_no_aprende_texto_demasiado_corto() -> None:
    assert ocr.debe_aprender("cuatro letras", []) is False


def test_aprende_el_primero_de_su_tipo() -> None:
    assert ocr.debe_aprender(TEXTO_ACME, []) is True


def test_no_aprende_la_misma_foto_resubida() -> None:
    assert ocr.debe_aprender(TEXTO_ACME, [TEXTO_ACME]) is False


def test_aprende_una_foto_distinta_del_mismo_formato() -> None:
    otro = TEXTO_ACME.replace("A-4471", "A-9999").replace(
        "Guantes de nitrilo talla M", "Botas dielectricas del 27"
    )
    assert ocr.debe_aprender(otro, [TEXTO_ACME]) is True


# --- El prompt no crece con lo aprendido -----------------------------------


def test_prompt_solo_usa_curados_y_respeta_el_tope() -> None:
    """El límite del prompt es independiente del corpus de clasificación.

    Es la razón de que existan tres constantes separadas: sin esto, cada
    documento aprendido haría la extracción más lenta.
    """
    ejemplos = [
        ejemplo("acme", TEXTO_ACME + " uno", curado=True),
        ejemplo("acme", TEXTO_ACME + " dos", curado=True),
        ejemplo("acme", TEXTO_ACME + " tres", curado=False),
        ejemplo("acme", TEXTO_ACME + " cuatro", curado=False),
        ejemplo("acme", TEXTO_ACME + " cinco", curado=False),
        ejemplo("acme", TEXTO_ACME + " seis", curado=False),
    ]
    mensajes = ocr._mensajes_few_shot("texto nuevo", ejemplos)

    # 1 system + 2 pares (user/assistant) + 1 user final
    assert len(mensajes) == 1 + 2 * ocr.MAX_EJEMPLOS_PROMPT + 1
    assert mensajes[0]["role"] == "system"
    assert mensajes[-1]["content"].endswith("texto nuevo")

    # Ninguno de los auto-aprendidos entró al prompt.
    cuerpo = " ".join(mensaje["content"] for mensaje in mensajes)
    for palabra in ("tres", "cuatro", "cinco", "seis"):
        assert f"{TEXTO_ACME} {palabra}" not in cuerpo


def test_prompt_sin_curados_solo_lleva_sistema_e_instruccion() -> None:
    ejemplos = [ejemplo("acme", TEXTO_ACME, curado=False)]
    mensajes = ocr._mensajes_few_shot("texto", ejemplos)
    assert len(mensajes) == 2
    assert mensajes[0]["role"] == "system"
    assert mensajes[1]["role"] == "user"


# --- Degradación: el pipeline nunca lanza ----------------------------------


@pytest.fixture
def sin_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """El LLM está caído: la estructuración siempre falla."""

    async def explota(*_args: Any, **_kwargs: Any) -> dict:
        raise ConnectionError("Ollama no responde")

    monkeypatch.setattr(ocr, "_estructurar", explota)


def parchear_ocr(monkeypatch: pytest.MonkeyPatch, texto: str) -> None:
    monkeypatch.setattr(ocr, "texto_ocr_desde_imagen", lambda _bytes: texto)


async def test_llm_caido_devuelve_ocr_ok_false_sin_lanzar(
    monkeypatch: pytest.MonkeyPatch, sin_llm: None
) -> None:
    parchear_ocr(monkeypatch, TEXTO_ACME)

    resultado = await ocr.extraer(b"fake", [ejemplo("acme", TEXTO_ACME)])

    assert isinstance(resultado, ResultadoExtraccion)
    assert resultado.ocr_ok is False
    assert resultado.error == ocr.IA_NO_DISPONIBLE


async def test_llm_caido_igual_resuelve_el_tipo(
    monkeypatch: pytest.MonkeyPatch, sin_llm: None
) -> None:
    """Saber el formato sirve aunque la extracción falle.

    Sin esto le pediríamos al operador registrar un formato que ya existe.
    """
    parchear_ocr(monkeypatch, TEXTO_ACME)

    resultado = await ocr.extraer(b"fake", [ejemplo("acme", TEXTO_ACME)])

    assert resultado.tipo_documento == "acme"
    assert resultado.texto_ocr == TEXTO_ACME


async def test_tesseract_ausente_devuelve_ocr_ok_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytesseract

    def sin_binario(_bytes: bytes) -> str:
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(ocr, "texto_ocr_desde_imagen", sin_binario)

    resultado = await ocr.extraer(b"fake", [])

    assert resultado.ocr_ok is False
    assert resultado.error == ocr.SIN_TESSERACT


async def test_imagen_corrupta_devuelve_ocr_ok_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def rota(_bytes: bytes) -> str:
        raise OSError("cannot identify image file")

    monkeypatch.setattr(ocr, "texto_ocr_desde_imagen", rota)

    resultado = await ocr.extraer(b"fake", [])

    assert resultado.ocr_ok is False
    assert resultado.error == ocr.IMAGEN_ILEGIBLE


async def test_sin_texto_legible_devuelve_ocr_ok_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parchear_ocr(monkeypatch, "   \n  ")

    resultado = await ocr.extraer(b"fake", [])

    assert resultado.ocr_ok is False
    assert resultado.error == ocr.SIN_TEXTO


async def test_extraccion_feliz_devuelve_advertencias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parchear_ocr(monkeypatch, TEXTO_ACME)

    async def estructura(*_args: Any, **_kwargs: Any) -> dict:
        return {
            "proveedor": "ACME",
            "folio": "A-4471",
            "fecha": None,
            "items": [{"codigo": "GN-100-M", "cantidad": None}],
        }

    monkeypatch.setattr(ocr, "_estructurar", estructura)

    resultado = await ocr.extraer(b"fake", [ejemplo("acme", TEXTO_ACME)])

    assert resultado.ocr_ok is True
    assert resultado.tipo_documento == "acme"
    assert resultado.advertencias == ["fecha", "items[0].cantidad"]


# --- OSD -------------------------------------------------------------------


class ImagenFalsa:
    """Registra si le pidieron rotar y cuánto."""

    def __init__(self) -> None:
        self.giro: int | None = None

    def rotate(self, grados: int, expand: bool = False) -> "ImagenFalsa":
        self.giro = grados
        return self


def test_osd_rota_con_confianza_alta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ocr.pytesseract,
        "image_to_osd",
        lambda *_a, **_k: {"rotate": 90, "orientation_conf": 5.0},
    )
    imagen = ImagenFalsa()

    ocr._normalizar_orientacion(imagen)  # type: ignore[arg-type]

    assert imagen.giro == -90


def test_osd_ignora_confianza_baja(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rotar mal es peor que no rotar: por eso el piso de confianza."""
    monkeypatch.setattr(
        ocr.pytesseract,
        "image_to_osd",
        lambda *_a, **_k: {"rotate": 90, "orientation_conf": 0.4},
    )
    imagen = ImagenFalsa()

    ocr._normalizar_orientacion(imagen)  # type: ignore[arg-type]

    assert imagen.giro is None


def test_osd_roto_no_tumba_el_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def explota(*_a: Any, **_k: Any) -> dict:
        raise RuntimeError("TesseractError: too few characters")

    monkeypatch.setattr(ocr.pytesseract, "image_to_osd", explota)
    imagen = ImagenFalsa()

    devuelta = ocr._normalizar_orientacion(imagen)  # type: ignore[arg-type]

    assert devuelta is imagen
    assert imagen.giro is None
