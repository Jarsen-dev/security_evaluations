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
    MARGEN_DESCRIPCION,
    ResultadoExtraccion,
    TIPO_DESCONOCIDO,
    UMBRAL_DESCRIPCION,
    clasificar,
    mejor_coincidencia,
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


# --- Emparejado de descripciones -------------------------------------------
#
# Un mismo código de proveedor ampara varios productos y lo que los distingue
# es la descripción. Elegir mal no se nota: la existencia se le suma al
# producto equivocado y el campo deja de estar en ámbar, así que nadie vuelve
# a mirarlo. Por eso lo que se prueba aquí, sobre todo, es que ante la duda
# NO elija.


def test_con_un_solo_candidato_no_compara() -> None:
    """No hay ambigüedad que resolver, y con un corpus de uno el IDF miente."""
    assert mejor_coincidencia("lo que sea", ["GUANTES DE NITRILO"]) == (None, 0.0, 0.0)


def test_sin_candidatos_no_elige() -> None:
    assert mejor_coincidencia("GUANTES", []) == (None, 0.0, 0.0)


def test_texto_vacio_no_elige() -> None:
    assert mejor_coincidencia("   ", ["GUANTES CHICOS", "GUANTES GRANDES"]) == (
        None,
        0.0,
        0.0,
    )


def test_elige_la_descripcion_que_coincide() -> None:
    indice, score, margen = mejor_coincidencia(
        "PARACETAMOL 500MG C/20",
        ["DICLOFENACO GEL 60GR", "PARACETAMOL 500MG C/20", "VENDA ELASTICA 10CM"],
    )
    assert indice == 1
    assert score > 0.9
    assert margen > 0.2


def test_ignora_acentos_y_mayusculas() -> None:
    """La remisión viene en mayúsculas sin acentos más veces que no."""
    indice, _, _ = mejor_coincidencia(
        "SOLUCION INYECTABLE",
        ["VENDA ELASTICA 10CM", "Solución inyectable"],
    )
    assert indice == 1


def test_ante_dos_parecidas_prefiere_preguntar() -> None:
    """Dos presentaciones del mismo medicamento: que elija el operador.

    Es el caso real que motivó el margen: en el catálogo de la planta
    «DICLOFENACO GEL 60GR» y «DICLOFENACO 100MG C/20 TAB ULT» se parecen 0.624
    entre sí siendo productos distintos.
    """
    indice, _, margen = mejor_coincidencia(
        "DICLOFENACO",
        ["DICLOFENACO GEL 60GR", "DICLOFENACO 100MG C/20 TAB ULT"],
    )
    assert indice is None
    assert margen < MARGEN_DESCRIPCION


def test_lo_que_no_se_parece_a_nada_no_elige() -> None:
    indice, score, _ = mejor_coincidencia(
        "TORNILLO HEXAGONAL 3/8",
        ["PARACETAMOL 500MG C/20", "VENDA ELASTICA 10CM"],
    )
    assert indice is None
    assert score < UMBRAL_DESCRIPCION


def test_el_clasificador_de_formatos_sigue_igual() -> None:
    """`clasificar()` cambió por dentro al extraerle `_similitudes()`.

    Su contrato no: el mejor tipo por encima del umbral, y `desconocido`
    cuando no llega. Sin esta prueba, la refactorización podía haberle movido
    el comportamiento sin que nada avisara.
    """
    ejemplos = [
        ejemplo("remision_acme", "REMISION ACME SA DE CV FOLIO 123 GUANTES"),
        ejemplo("nota_beta", "NOTA DE VENTA BETA INDUSTRIAL CUBREBOCAS"),
    ]

    assert clasificar("REMISION ACME SA DE CV FOLIO 456 GUANTES", ejemplos) == (
        "remision_acme"
    )
    assert clasificar("documento sin ninguna relacion", ejemplos) == TIPO_DESCONOCIDO
    assert clasificar("", ejemplos) == TIPO_DESCONOCIDO
    assert clasificar("REMISION ACME", []) == TIPO_DESCONOCIDO


# --- Formatos que comparten plantilla ---------------------------------------
#
# Todas las facturas CFDI llevan el mismo relleno del SAT, y con dos o tres
# ejemplos el IDF no puede aprender que eso es relleno: el parecido absoluto
# sube por igual para todos los formatos y deja de distinguir. Lo que decide es
# cuánto le gana el ganador al mejor de OTRO formato.

RELLENO_SAT = (
    "Factura VERSION 4.0 CFDI Numero de serie del CSD del emisor "
    "Regimen Fiscal 626 Regimen Simplificado de Confianza Uso CFDI G03 "
    "Metodo de Pago PPD Forma de Pago 99 Por definir Moneda MXN "
    "Cadena original del complemento de certificacion digital del SAT "
    "Sello digital del emisor Sello del SAT Folio Fiscal UUID "
)

ACME = (
    "ACME SUMINISTROS INDUSTRIALES SA DE CV RFC ASI850101AB1 "
    "Avenida Constitucion 1450 Colonia Centro Monterrey Nuevo Leon "
    "GN-100-M guantes de nitrilo talla M caja con 100 piezas "
    "CS-220 casco de seguridad blanco con barbiquejo "
)
BOREAL = (
    "BOREAL SAFETY EQUIPMENT LLC RFC BSE900202XY2 "
    "Carretera Miguel Aleman kilometro 12 Apodaca Nuevo Leon "
    "EPS-77 respirador media cara con filtros P100 "
    "LT-45 lentes de seguridad antiempanantes "
)
TERCERO = (
    "VALVULAS Y CONEXIONES DEL BAJIO SA RFC VCB010203Z9 "
    "Boulevard Aeropuerto 700 Leon Guanajuato "
    "VC-4 valvula de compuerta 4 pulgadas bridada "
    "TB-2 tuberia de acero al carbon cedula 40 "
)


def factura(emisor: str, extra: str = "") -> str:
    """Una factura: el relleno del SAT que comparten todas, más lo suyo."""
    return RELLENO_SAT + emisor + extra


def test_una_factura_de_otro_proveedor_no_se_cuela_en_un_formato_conocido() -> None:
    """El caso real: una factura de un proveedor archivada como la de otro.

    Se parece a los dos formatos casi igual —lo que comparten es el relleno—,
    así que no le gana a ninguno y se queda en desconocido. Con el umbral
    absoluto de antes, el relleno bastaba para colarla.
    """
    ejemplos = [ejemplo("acme", factura(ACME)), ejemplo("boreal", factura(BOREAL))]

    assert clasificar(factura(TERCERO), ejemplos) == TIPO_DESCONOCIDO


def test_otra_factura_del_mismo_proveedor_si_se_reconoce() -> None:
    """El reverso, que es lo que se rompió al subir el umbral absoluto: las
    facturas legítimas de un proveedor dejaban de reconocerse a partir de la
    segunda."""
    ejemplos = [ejemplo("acme", factura(ACME)), ejemplo("boreal", factura(BOREAL))]

    otra = factura(ACME, "GN-100-G guantes de nitrilo talla G caja con 100 piezas ")
    assert clasificar(otra, ejemplos) == "acme"


def test_con_un_solo_formato_no_hay_cociente_y_manda_el_absoluto() -> None:
    """Sin otro formato con el que comparar, el cociente no significa nada.

    Es el corpus con el que empieza todo sistema: un formato aprendido y nada
    más. Ahí la decisión vuelve a ser un mínimo absoluto, y más alto.
    """
    ejemplos = [ejemplo("acme", factura(ACME))]

    assert clasificar(factura(ACME), ejemplos) == "acme"
    assert clasificar(TEXTO_BOREAL, ejemplos) == TIPO_DESCONOCIDO


# --- El RFC del emisor ------------------------------------------------------
#
# Dos proveedores del mismo giro comparten plantilla del SAT *y* vocabulario,
# así que ni el parecido absoluto ni el cociente entre formatos los separan.
# Lo que sí, porque está impreso en el papel: quién firma la factura.

RFC_ACME = "ASI850101AB1"
RFC_BIO = "BACA8810113Y0"
#: El receptor es siempre esta planta, así que sale en todas las facturas.
RFC_PLANTA = "CWM020627SJ7"


def factura_de(rfc_emisor: str, emisor: str, cuerpo: str) -> str:
    """Una factura con datos fiscales: relleno del SAT, emisor, receptor y lo suyo.

    El cuerpo pesa como en una factura de verdad: si fuera una línea suelta
    frente a todo el relleno fiscal, dos facturas de proveedores distintos
    saldrían casi idénticas y la prueba mediría el fixture, no el código.
    """
    return (
        f"{RELLENO_SAT} RFC emisor: {rfc_emisor} Nombre emisor: {emisor} "
        f"RFC receptor: {RFC_PLANTA} CHEONG WOON MEXICO Conceptos: {cuerpo}"
    )


CUERPO_ACME = (
    "Avenida Constitucion 1450 Colonia Centro Monterrey Nuevo Leon "
    "PAR-500 paracetamol 500mg caja con 20 tabletas lote 4471 "
    "IBU-400 ibuprofeno 400mg caja con 10 capsulas lote 4472 "
    "NAP-250 naproxeno sodico 250mg caja con 12 tabletas "
)
CUERPO_BIO = (
    "Prolongacion Madero 220 Colonia Obrera Guadalajara Jalisco "
    "PRB-01 pruebas de antigeno 5 parametros caja con 25 pruebas "
    "GLU-02 tiras reactivas de glucosa caja con 50 tiras "
    "TER-03 termometro infrarrojo de frente sin contacto "
)
CUERPO_BOREAL = (
    "Carretera Miguel Aleman kilometro 12 Apodaca Nuevo Leon "
    "EPS-77 respirador media cara con filtros P100 talla mediana "
    "LT-45 lentes de seguridad antiempanantes policarbonato "
    "GU-30 guantes de carnaza reforzados talla grande "
)


def test_otro_proveedor_del_mismo_giro_no_pasa_por_el_conocido() -> None:
    """El caso real: una farmacéutica archivada como la otra.

    Se parecen tanto —misma plantilla fiscal, mismo vocabulario de
    medicamentos— que el texto no basta. El RFC del emisor sí.
    """
    ejemplos = [
        ejemplo("acme", factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME)),
        ejemplo("boreal", factura_de("BSE900202XY2", "BOREAL SAFETY", CUERPO_BOREAL)),
    ]

    otra_farmaceutica = factura_de(RFC_BIO, "BIO HEALTH MEDIC", CUERPO_BIO)
    assert clasificar(otra_farmaceutica, ejemplos) == TIPO_DESCONOCIDO


def test_el_mismo_emisor_si_pasa() -> None:
    ejemplos = [
        ejemplo("acme", factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME)),
        ejemplo("boreal", factura_de("BSE900202XY2", "BOREAL SAFETY", CUERPO_BOREAL)),
    ]

    otra = factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME + "PAR-650 paracetamol 650mg ")
    assert clasificar(otra, ejemplos) == "acme"


def test_el_rfc_de_la_planta_no_identifica_a_nadie() -> None:
    """Sale en todas las facturas, así que no puede servir de desempate.

    Se descarta solo, por aparecer en más de un formato: no hay que
    configurarlo en ninguna parte ni mantenerlo al día.
    """
    ejemplos = [
        ejemplo("acme", factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME)),
        ejemplo("boreal", factura_de("BSE900202XY2", "BOREAL SAFETY", CUERPO_BOREAL)),
    ]

    emisores = ocr._emisores(ejemplos)
    assert emisores["acme"] == {RFC_ACME}
    assert RFC_PLANTA not in emisores["acme"] | emisores["boreal"]


def test_el_ocr_puede_errar_un_par_de_caracteres_del_rfc() -> None:
    """El mismo RFC se lee distinto en cada foto; sigue siendo el mismo."""
    assert ocr._mismo_rfc("CWM020627SJ7", "CWMO020627SJ7")
    assert ocr._mismo_rfc("CWM020627SJ7", "CWM0206278J7")
    # Pero dos empresas distintas no se confunden.
    assert not ocr._mismo_rfc(RFC_ACME, RFC_BIO)


def test_una_remision_sin_datos_fiscales_no_se_penaliza() -> None:
    """Sin RFC que comparar, decide el parecido de texto como siempre.

    Es el caso de las remisiones simples, que no llevan datos fiscales: el
    control descarta, nunca confirma.
    """
    ejemplos = [ejemplo("acme", factura(ACME)), ejemplo("boreal", factura(BOREAL))]

    otra = factura(ACME, "GN-100-G guantes de nitrilo talla G caja con 100 piezas ")
    assert clasificar(otra, ejemplos) == "acme"


def test_el_rfc_del_emisor_confirma_aunque_el_texto_dude() -> None:
    """Dos facturas del mismo proveedor pueden parecerse poco entre sí.

    Cambian los conceptos, los importes, media hoja — y el parecido de texto se
    queda por debajo de lo que se le exige. Quien firma el papel no cambia, y
    eso basta. Es el caso real: tres facturas de Bio Health, todas con su RFC
    legible, rechazadas por un cociente de 1.10.
    """
    ejemplos = [
        ejemplo("acme", factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME)),
        ejemplo("boreal", factura_de("BSE900202XY2", "BOREAL SAFETY", CUERPO_BOREAL)),
    ]

    # Otra factura del mismo emisor, con productos completamente distintos.
    otra = factura_de(RFC_ACME, "ACME PHARMA", CUERPO_BIO)

    # El texto por sí solo no llegaría: se comprueba aquí para que la prueba
    # falle si el fixture deja de reproducir el caso.
    sims = ocr._similitudes(otra, [e.texto_ocr for e in ejemplos])
    assert max(sims) / min(sims) < ocr.FACTOR_DISTINCION

    assert clasificar(otra, ejemplos) == "acme"


def test_el_rfc_del_sat_no_confirma_a_nadie() -> None:
    """Sale en todas las facturas del país; no identifica a ningún proveedor.

    Y no se descarta solo como el del receptor: si un único formato lo tiene
    legible, la regla de "lo compartido no distingue" no llega a verlo.
    """
    ejemplos = [
        ejemplo("acme", factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME) + ocr.RFC_SAT),
        ejemplo("boreal", factura_de("BSE900202XY2", "BOREAL SAFETY", CUERPO_BOREAL)),
    ]

    assert ocr.RFC_SAT not in ocr._emisores(ejemplos)["acme"]
    # Un documento donde el OCR solo pudo leer el RFC del SAT no confirma nada.
    solo_sat = f"{RELLENO_SAT} {ocr.RFC_SAT} {CUERPO_ACME}"
    assert ocr._firma_del_emisor(solo_sat, "acme", ejemplos) is None


def test_la_firma_distingue_los_tres_casos() -> None:
    ejemplos = [
        ejemplo("acme", factura_de(RFC_ACME, "ACME PHARMA", CUERPO_ACME)),
        ejemplo("boreal", factura_de("BSE900202XY2", "BOREAL SAFETY", CUERPO_BOREAL)),
    ]

    propia = factura_de(RFC_ACME, "ACME PHARMA", CUERPO_BIO)
    ajena = factura_de(RFC_BIO, "BIO HEALTH MEDIC", CUERPO_BIO)

    assert ocr._firma_del_emisor(propia, "acme", ejemplos) is True
    assert ocr._firma_del_emisor(ajena, "acme", ejemplos) is False
    # Una remisión sin datos fiscales —ningún RFC impreso—: no hay con qué
    # decidir, y el control se aparta en vez de penalizarla.
    sin_rfc = "REMISION ACME SUMINISTROS Folio A-4471 guantes de nitrilo talla M 120"
    assert ocr._firma_del_emisor(sin_rfc, "acme", ejemplos) is None


# --- Cuando el modelo se atasca ---------------------------------------------
#
# Con el OCR ruidoso el modelo puede repetir las mismas partidas hasta agotar
# su presupuesto de tokens y dejar el JSON cortado a media palabra. Pasó con
# una hoja de 16 renglones: emitió 51 partidas y la extracción entera se
# perdía. La penalización a la repetición lo hace raro; esta red lo hace
# recuperable.


def test_rescata_un_json_cortado_a_media_partida() -> None:
    cortado = (
        '{"proveedor": "MGPHARMA", "folio": "28342", "items": ['
        '{"codigo": "51142001", "descripcion": "PARACETAMOL", "cantidad": 8}, '
        '{"codigo": "51142106", "descripcion": "ADOPRE'
    )
    datos = ocr._extraer_json(cortado)

    assert datos["folio"] == "28342"
    # Lo que quedó a medias se descarta; lo leído se conserva.
    assert len(datos["items"]) == 1
    assert datos["items"][0]["codigo"] == "51142001"


def test_un_json_sin_ninguna_partida_completa_no_se_inventa() -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        ocr._extraer_json('{"proveedor": "MGPHARMA", "items": [{"codigo": "5114')


def test_quita_las_partidas_que_el_modelo_repite() -> None:
    """El bucle repite renglones enteros; se quedan una vez."""
    items = [
        {"codigo": "51142001", "cantidad": 8},
        {"codigo": "51142106", "cantidad": None},
        {"codigo": "51142001", "cantidad": 8},
        {"codigo": "51142106", "cantidad": None},
        {"codigo": "51142001", "cantidad": 8},
    ]

    assert ocr._sin_repetidos(items) == items[:2]


def test_el_mismo_codigo_con_otra_cantidad_no_es_una_repeticion() -> None:
    """Dos renglones del mismo producto con cantidades distintas son dos."""
    items = [
        {"codigo": "51142001", "cantidad": 8},
        {"codigo": "51142001", "cantidad": 3},
    ]

    assert len(ocr._sin_repetidos(items)) == 2
