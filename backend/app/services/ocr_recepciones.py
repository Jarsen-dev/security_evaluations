"""Extracción de los datos de una remisión a partir de su foto.

Tres pasos deterministas más un LLM **de texto**, sin entrenar ni afinar nada:

    foto (bytes)
      │
      ├─(1)─ Tesseract local (spa+eng) ──────────────► texto OCR crudo
      │        · OSD para corregir rotaciones de 90/180/270°
      │        · escala de grises + autocontraste
      │
      ├─(2)─ Clasificación TF-IDF local ─────────────► tipo de documento
      │        · compara contra el texto OCR de los ejemplos guardados
      │        · n-gramas de CARÁCTER, coseno, umbral 0.20
      │
      └─(3)─ Estructuración few-shot con un LLM ─────► JSON final
               · el modelo NUNCA ve píxeles: solo acomoda texto ya leído

**Por qué no un modelo de visión.** Un VLM "lee" los píxeles y alucina
caracteres: inventa números de parte y cantidades que no existen en el papel.
Aquí el LLM solo reordena texto que Tesseract ya vio, así que el peor caso es
que deje un campo en ``null``, no que se invente uno. Para un documento que
mueve existencias, eso es la diferencia entre un hueco que el operador llena y
un dato falso que nadie detecta.

**Este módulo nunca lanza una excepción hacia arriba.** Cualquier falla —
Tesseract ausente, imagen corrupta, LLM caído, JSON inválido— se devuelve como
``ResultadoExtraccion(ocr_ok=False, error=...)`` con un mensaje escrito para el
operador, no para el desarrollador. La ruta responde 200, el formulario abre en
captura manual y la foto ya quedó guardada. Nunca se pierde la evidencia ni se
bloquea la operación del almacén.
"""

import asyncio
import io
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
import pytesseract
from PIL import Image, ImageOps
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Valor de ``tipo_documento`` cuando el clasificador no reconoce el formato.
TIPO_DESCONOCIDO: Final[str] = "desconocido"

# Configuración del vectorizador. n-gramas de CARÁCTER, no de palabra: medido
# degradando texto real, con 20% de ruido de OCR el acierto pasa de 43% (por
# palabras) a 88% (por caracteres). Un carácter mal leído destruye la palabra
# completa como token ("Warehouse" -> "Warehousc" no comparte nada), pero
# conserva casi todos los n-gramas.
VECTORIZER_KWARGS: Final[dict[str, Any]] = {
    "analyzer": "char_wb",
    "ngram_range": (3, 5),
}

# Piso de texto para aceptar un ejemplo auto-aprendido. Deliberadamente bajo:
# el formato más débil medido tenía 105 caracteres y aprenderlo subió su score
# de 0.168 (bajo umbral) a 0.402. Un piso de 200 lo habría rechazado y ese
# formato nunca habría mejorado.
MIN_CHARS_TEMPLATE: Final[int] = 100

#: Arriba de esto es la misma foto resubida: no aporta señal nueva.
UMBRAL_DEDUP_EJEMPLO: Final[float] = 0.98

# Cuándo el sistema se atreve a elegir por el operador qué descripción de un
# código recibió.
#
# NO se reutiliza `OCR_UMBRAL_SIMILITUD` (0.20): aquel está calibrado sobre
# páginas completas, y sobre todo la asimetría está invertida. En la
# clasificación de formatos el falso positivo lo corrige el operador; aquí un
# falso positivo le suma la existencia al producto equivocado y el campo deja
# de estar en ámbar, así que nadie vuelve a mirarlo. Ante la duda se pregunta.
#
# Los dos números salen de medir las 45 descripciones reales del catálogo:
#
#   - Productos DISTINTOS entre sí: p50=0.004, p90=0.100, p99=0.273. El umbral
#     de 0.35 deja fuera ese ruido.
#   - La descripción CORRECTA leída con 10% de ruido de OCR: score p50=0.583,
#     p5=0.344; recortada a la mitad, p50=0.571. Por eso el umbral no puede
#     ser 0.60 como se pensó primero: habría mandado a preguntar la mitad de
#     los aciertos.
#   - **El margen es lo que de verdad discrimina.** Hay pares distintos que
#     puntúan altísimo entre sí —«DICLOFENACO GEL 60GR» contra «DICLOFENACO
#     100MG C/20 TAB ULT» da 0.624—, y son justo los que compartirían código.
#     En un acierto con ruido el margen está en 0.57 de mediana y 0.267 en el
#     percentil 5; entre dos presentaciones parecidas se desploma. 0.20 separa
#     los dos casos.
#
# Van como constantes y no como configuración: una variable nueva en
# `config.py` hay que pasarla también en el `environment:` de docker-compose o
# corre con el valor por omisión sin que nada lo diga. Y se recalibran
# midiendo, no a ojo: el script está en el historial del cambio.
# Cuánto tiene que ganarle el formato ganador al mejor de OTRO formato para
# creerle. Es lo que resuelve las facturas CFDI: todas comparten la plantilla
# del SAT —"VERSIÓN 4.0", el sello digital, la cadena de certificación— y con
# dos o tres ejemplos el IDF no puede aprender que eso es relleno, así que el
# parecido absoluto sube por igual para todo el mundo y deja de significar
# nada. El cociente sí, porque ese piso común se cancela. Medido con facturas
# reales de la planta: las que sí son del formato dan 1.30, 1.80 y 2.47; una
# de un proveedor ajeno se parece a todos los formatos por igual y da ~1.0.
FACTOR_DISTINCION: Final[float] = 1.20

# Con UN SOLO formato en el corpus no hay contra quién comparar y el cociente
# no existe, así que ahí manda un mínimo absoluto y más alto. Es el caso que
# archivaba las facturas de REICI como MGPHARMA: puntuaban 0.314 sin nadie que
# les hiciera sombra, mientras que una MGPHARMA de verdad daba 0.675.
UMBRAL_SIN_COMPETENCIA: Final[float] = 0.40

UMBRAL_DESCRIPCION: Final[float] = 0.35
MARGEN_DESCRIPCION: Final[float] = 0.20

# Tres límites SEPARADOS a propósito. El corpus de clasificación quiere MUCHOS
# ejemplos; el prompt quiere POCOS. Sin esta separación, cada documento
# aprendido haría la extracción más lenta y llenaría el contexto del modelo.
MAX_EJEMPLOS_CURADOS: Final[int] = 2
MAX_EJEMPLOS_AUTO: Final[int] = 4
MAX_EJEMPLOS_PROMPT: Final[int] = 2

# Confianza mínima del OSD para hacerle caso. Probado contra fotos reales: con
# confianza baja el OSD a veces sugiere una rotación que empeora una foto ya
# derecha, y es peor rotar mal que no rotar.
MIN_CONFIANZA_OSD: Final[float] = 2.0

PROMPT_SISTEMA: Final[str] = (
    "Eres un extractor de datos de remisiones y facturas de proveedores de "
    "insumos de seguridad industrial. Recibes texto ya leído por OCR (puede "
    "tener errores de reconocimiento, saltos de línea irregulares o ruido) y "
    "SIEMPRE respondes con JSON válido, sin texto adicional ni markdown. La "
    'estructura es exactamente: {"proveedor": str, "folio": str, "fecha": '
    '"YYYY-MM-DD", "items": [{"codigo": str, "descripcion": str, "cantidad": '
    'number}]}. "folio" es el número de folio o de remisión del documento. '
    '"codigo" es la clave o número de parte del producto tal como aparece en '
    'la hoja. "descripcion" es el nombre del producto tal como aparece en esa '
    "misma línea, copiado sin resumir y sin pasar de 60 caracteres: un mismo "
    "código puede amparar productos distintos y es lo único que los "
    "distingue. "
    "Si un campo no aparece en el texto o no puedes interpretarlo con "
    "confianza (incluye texto manuscrito que el OCR no pudo leer), usa null "
    "para ese campo. NUNCA inventes ni aproximes un valor que no esté "
    "razonablemente presente en el texto."
)

INSTRUCCION_FINAL: Final[str] = (
    "Ahora extrae los campos de este NUEVO texto OCR, siguiendo EXACTAMENTE "
    "la misma estructura JSON de los ejemplos anteriores (mismas llaves, "
    "mismo formato de fecha, items como lista). El texto puede tener errores "
    "de OCR (caracteres mal reconocidos, saltos de línea irregulares, ruido) "
    "— interprétalo lo mejor posible pero NUNCA inventes un valor que no esté "
    "razonablemente presente en él. Si un campo no es legible, usa null.\n\n"
)

INSTRUCCION_EJEMPLO: Final[str] = (
    "Extrae los campos de este texto OCR de ejemplo, en formato JSON:\n\n"
)

# Mensajes para el operador. Dicen qué hacer ahora y que la foto ya se guardó.
SIN_TESSERACT = (
    "El servidor no tiene instalado el motor de OCR. La foto ya se guardó; "
    "captura los campos a mano."
)
IMAGEN_ILEGIBLE = (
    "No se pudo abrir la foto. Puede estar dañada o no ser una imagen. "
    "Intenta tomarla de nuevo."
)
SIN_TEXTO = (
    "No se detectó texto legible en la foto. La foto ya se guardó; captura "
    "los campos a mano."
)
IA_NO_DISPONIBLE = (
    "La IA no respondió a tiempo. La foto ya se guardó; captura los campos a "
    "mano."
)


@dataclass(frozen=True)
class EjemploPlantilla:
    """Un ejemplo etiquetado de un formato de documento.

    Es lo que la base guarda por fila; el servicio lo pasa a este módulo para
    que no dependa de SQLAlchemy y se pueda probar sin base de datos.
    """

    tipo: str
    texto_ocr: str
    json_esperado: dict[str, Any]
    #: ``True`` si lo capturó una persona al registrar el formato.
    curado: bool


@dataclass
class ResultadoExtraccion:
    """Lo que sale del pipeline, haya funcionado o no."""

    ocr_ok: bool
    tipo_documento: str = TIPO_DESCONOCIDO
    datos: dict[str, Any] = field(default_factory=dict)
    advertencias: list[str] = field(default_factory=list)
    texto_ocr: str = ""
    error: str | None = None


# --- Paso 1: OCR -----------------------------------------------------------


def _normalizar_orientacion(imagen: Image.Image) -> Image.Image:
    """Endereza la foto si el OSD lo pide con suficiente confianza.

    Las fotos de celular llegan giradas 90/180/270° con frecuencia. Se hace
    caso al OSD **solo** por encima de ``MIN_CONFIANZA_OSD``: con confianza
    baja a veces sugiere girar una foto que ya estaba derecha, y rotar mal es
    peor que no rotar. Si el OSD falla del todo (foto borrosa, poco texto) se
    sigue sin rotar.

    No se corrige la inclinación fina: está fuera de alcance.
    """
    try:
        osd = pytesseract.image_to_osd(imagen, output_type=pytesseract.Output.DICT)
    except Exception:
        # Incluye TesseractError por falta de texto. No es un fallo del flujo:
        # simplemente no sabemos la orientación.
        logger.debug("OSD no disponible; se sigue sin rotar")
        return imagen

    confianza = float(osd.get("orientation_conf", 0) or 0)
    giro = int(osd.get("rotate", 0) or 0)

    if giro and confianza >= MIN_CONFIANZA_OSD:
        logger.info("OSD: rotando %d° (confianza %.2f)", giro, confianza)
        return imagen.rotate(-giro, expand=True)

    if giro:
        logger.info(
            "OSD sugiere %d° pero la confianza es baja (%.2f < %.2f): no se rota",
            giro,
            confianza,
            MIN_CONFIANZA_OSD,
        )
    return imagen


def texto_ocr_desde_imagen(imagen_bytes: bytes) -> str:
    """Lee el texto de una foto. Bloqueante: llámese dentro de un hilo.

    Lanza ``pytesseract.TesseractNotFoundError`` si el binario no está, y
    ``OSError`` si la imagen no se puede abrir. Quien llama las traduce a un
    mensaje para el operador.
    """
    imagen = Image.open(io.BytesIO(imagen_bytes))
    imagen = _normalizar_orientacion(imagen)
    imagen = ImageOps.autocontrast(ImageOps.grayscale(imagen), cutoff=1)
    return pytesseract.image_to_string(imagen, lang="spa+eng")


# --- Paso 2: clasificación -------------------------------------------------


def _similitudes(consulta: str, corpus: list[str]) -> list[float]:
    """Coseno TF-IDF de ``consulta`` contra cada texto de ``corpus``.

    Es la capa de abajo que comparten la clasificación de formatos y el
    emparejado de descripciones. Tres invariantes que no se pueden tocar:

    - la consulta va **al final**, y el vectorizador se ajusta sobre el corpus
      y la consulta **juntos**: el IDF depende del conjunto, así que no se
      puede precalcular ni cachear por corpus;
    - `VECTORIZER_KWARGS` es el mismo para todos (n-gramas de carácter);
    - si revienta —corpus degenerado, vocabulario vacío— se devuelve una lista
      vacía y quien llama degrada; nunca propaga.
    """
    if not consulta.strip() or not corpus:
        return []

    try:
        matriz = TfidfVectorizer(**VECTORIZER_KWARGS).fit_transform(corpus + [consulta])
        return [float(valor) for valor in cosine_similarity(matriz[-1], matriz[:-1])[0]]
    except Exception:
        logger.warning("TF-IDF falló; se degrada sin similitudes", exc_info=True)
        return []


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar descripciones.

    Sin esto, «GUANTES DE NITRÍLO» pierde puntos contra «guantes de nitrilo»
    por diferencias que a nadie le importan.
    """
    sin_acentos = (
        unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    )
    return " ".join(sin_acentos.lower().split())


def mejor_coincidencia(
    texto: str, candidatos: list[str]
) -> tuple[int | None, float, float]:
    """Elige la descripción del catálogo que más se parece a la del papel.

    Devuelve ``(indice, score, margen)``, con ``indice`` en ``None`` cuando no
    hay suficiente confianza como para decidir por el operador.

    Con **un solo candidato no se compara nada**: quien llama ya sabe que no
    hay ambigüedad, y con un corpus de un documento el IDF es degenerado y el
    coseno no significa nada.

    El margen contra el segundo mejor pesa tanto como el score: dos
    presentaciones del mismo medicamento se parecen muchísimo entre sí, y
    justo ahí es donde la elección tiene que ser del operador.
    """
    if len(candidatos) < 2 or not texto.strip():
        return None, 0.0, 0.0

    similitudes = _similitudes(_normalizar(texto), [_normalizar(c) for c in candidatos])
    if not similitudes:
        return None, 0.0, 0.0

    mejor = max(range(len(similitudes)), key=lambda i: similitudes[i])
    score = similitudes[mejor]
    segundo = max(
        (valor for indice, valor in enumerate(similitudes) if indice != mejor),
        default=0.0,
    )
    margen = score - segundo

    decide = score >= UMBRAL_DESCRIPCION and margen >= MARGEN_DESCRIPCION
    logger.info(
        "emparejado de descripción → %s (score=%.3f, 2ª=%.3f, margen=%.3f, "
        "umbrales=%.2f/%.2f, %d candidatos)",
        candidatos[mejor] if decide else "sin decidir",
        score,
        segundo,
        margen,
        UMBRAL_DESCRIPCION,
        MARGEN_DESCRIPCION,
        len(candidatos),
    )

    return (mejor if decide else None), score, margen


# El RFC de una empresa mexicana: 3 letras (4 si es persona física), la fecha
# de constitución y la homoclave.
PATRON_RFC = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")

#: El RFC del SAT aparece en todas las facturas del país, así que no puede
#: identificar a un proveedor. Va como constante porque no se descarta solo:
#: si un solo formato del corpus lo tiene legible, la regla de "lo compartido
#: no distingue" no llega a verlo como compartido.
# Opciones de generación del modelo.
#
# `repeat_penalty` no es un ajuste fino: presiona contra el BUCLE. Con el OCR
# ruidoso el modelo puede repetir las mismas partidas hasta agotar el
# presupuesto de tokens y devolver un JSON cortado a media palabra —o sea,
# nada—. Medido sobre la hoja que lo destapó (16 renglones reales): sin
# penalizar, 51 partidas en 35 s y JSON inválido; con 3000 tokens de margen,
# 96 partidas en 66 s y también inválido. **Más espacio empeora el problema**,
# así que el tope se queda donde está.
#
# 1.2 y no más: a 1.3 el modelo empieza a saltarse renglones legítimos —una
# hoja de 21 partidas devolvía 18—. Entre 1.1 y 1.2 ninguna las pierde.
#
# Y el bucle es **intermitente**: la misma hoja con la misma penalización unas
# veces lo hace y otras no, así que la garantía no está aquí sino en la red de
# `_cerrar_json_truncado()` y `_sin_repetidos()`.
OPCIONES_MODELO: Final[dict[str, Any]] = {
    "temperature": 0.1,
    "num_predict": 1600,
    "repeat_penalty": 1.2,
}

RFC_SAT: Final[str] = "SAT970701NN3"

#: Cuántos caracteres puede errar el OCR y seguir siendo el mismo RFC. Medido
#: con documentos reales: el de la planta se leyó de cinco formas distintas
#: —CWM020627SJ7, CWMO020627SJ7, CWM0206278J7…— y todas están a uno o dos
#: caracteres de distancia.
TOLERANCIA_RFC: Final[int] = 2


def _rfcs(texto: str) -> set[str]:
    """Los RFC que aparecen en un texto de OCR."""
    limpio = re.sub(r"[^A-Za-z0-9Ññ&\s]", "", texto.upper())
    return set(PATRON_RFC.findall(limpio))


def _mismo_rfc(uno: str, otro: str) -> bool:
    """Si dos lecturas son el mismo RFC, tolerando errores del OCR.

    Distancia de edición pequeña, calculada aquí y no con una dependencia
    nueva: son cadenas de doce caracteres y un puñado de comparaciones.
    """
    if abs(len(uno) - len(otro)) > TOLERANCIA_RFC:
        return False

    previa = list(range(len(otro) + 1))
    for i, letra in enumerate(uno, 1):
        actual = [i]
        for j, contra in enumerate(otro, 1):
            actual.append(
                min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (letra != contra))
            )
        previa = actual
    return previa[-1] <= TOLERANCIA_RFC


def _emisores(ejemplos: list[EjemploPlantilla]) -> dict[str, set[str]]:
    """RFC que identifican a cada formato, quitando los que no distinguen.

    En una factura hay al menos tres RFC: el del emisor, el del receptor —que
    es siempre esta planta— y el del SAT. Los dos últimos aparecen en todos los
    formatos, así que se descartan por eso mismo: **lo que sale en más de un
    formato no identifica a ninguno**. No hace falta configurar cuál es el RFC
    de la planta ni mantenerlo al día, y de paso se descartan solas las cinco
    lecturas distintas que el OCR hace de él.
    """
    por_formato: dict[str, set[str]] = {}
    for ejemplo in ejemplos:
        por_formato.setdefault(ejemplo.tipo, set()).update(_rfcs(ejemplo.texto_ocr))

    compartidos: set[str] = set()
    tipos = list(por_formato)
    for indice, uno in enumerate(tipos):
        for otro in tipos[indice + 1:]:
            for rfc_uno in por_formato[uno]:
                for rfc_otro in por_formato[otro]:
                    if _mismo_rfc(rfc_uno, rfc_otro):
                        compartidos.update({rfc_uno, rfc_otro})

    return {
        tipo: {
            rfc
            for rfc in rfcs
            if rfc not in compartidos and not _mismo_rfc(rfc, RFC_SAT)
        }
        for tipo, rfcs in por_formato.items()
    }


def _firma_del_emisor(
    texto_ocr: str, tipo: str, ejemplos: list[EjemploPlantilla]
) -> bool | None:
    """Si el documento lo emite quien emite los ejemplos de ese formato.

    ``True`` si coincide, ``False`` si lo firma otro, y ``None`` cuando no hay
    con qué decidir —el OCR no leyó ningún RFC, o el formato no tiene ninguno
    propio porque es una remisión sin datos fiscales—.

    Es la señal más fuerte del documento y por eso vale en los dos sentidos.
    Confirma: dos facturas del mismo proveedor pueden parecerse poco entre sí
    —cambian los conceptos, el importe, media hoja— y el parecido de texto se
    queda corto, pero quien la firma no cambia. Y descarta: dos proveedores del
    mismo giro comparten plantilla fiscal y vocabulario, y ahí el texto tampoco
    los separa.
    """
    propios = _emisores(ejemplos).get(tipo, set())
    del_documento = {
        rfc for rfc in _rfcs(texto_ocr) if not _mismo_rfc(rfc, RFC_SAT)
    }

    if not propios or not del_documento:
        return None

    return any(_mismo_rfc(rfc, propio) for rfc in del_documento for propio in propios)


def clasificar(texto_ocr: str, ejemplos: list[EjemploPlantilla]) -> str:
    """Devuelve el tipo de documento más parecido, o ``desconocido``.

    Determinista, gratis y sin red: compara el texto OCR contra el de cada
    ejemplo guardado. Si TF-IDF revienta (corpus degenerado, vocabulario
    vacío) se sigue con ``desconocido``: se pierden los ejemplos few-shot,
    pero el prompt de sistema por sí solo ya describe el JSON esperado.
    """
    if not texto_ocr.strip() or not ejemplos:
        return TIPO_DESCONOCIDO

    similitudes = _similitudes(texto_ocr, [ejemplo.texto_ocr for ejemplo in ejemplos])
    if not similitudes:
        return TIPO_DESCONOCIDO

    mejor = max(range(len(similitudes)), key=lambda i: similitudes[i])
    tipo_ganador = ejemplos[mejor].tipo
    score = similitudes[mejor]

    # El mejor score de OTRO tipo y el margen son lo único que permite
    # recalibrar el umbral sin adivinar. Se loguean siempre.
    otros = [
        valor
        for indice, valor in enumerate(similitudes)
        if ejemplos[indice].tipo != tipo_ganador
    ]
    segundo = max(otros) if otros else 0.0

    logger.info(
        "clasificación TF-IDF → %s (score=%.3f, 2º tipo=%.3f, cociente=%.2f, "
        "piso=%.3f, factor=%.2f, %d ejemplos de %d tipos)",
        tipo_ganador,
        score,
        segundo,
        score / segundo if segundo else float("inf"),
        settings.OCR_UMBRAL_SIMILITUD,
        FACTOR_DISTINCION,
        len(ejemplos),
        len({ejemplo.tipo for ejemplo in ejemplos}),
    )

    # Piso absoluto: por debajo de esto no se parece a nada y da igual el
    # cociente.
    if score < settings.OCR_UMBRAL_SIMILITUD:
        return TIPO_DESCONOCIDO

    # Sin otro formato con el que comparar, el cociente no significa nada.
    if not otros:
        return tipo_ganador if score >= UMBRAL_SIN_COMPETENCIA else TIPO_DESCONOCIDO

    # Lo que decide: cuánto le gana al mejor de OTRO formato. Un documento de
    # un proveedor nuevo se parece a todos por igual y no pasa de aquí.
    # Quién firma el papel pesa más que el parecido del texto, en los dos
    # sentidos: si coincide el RFC del emisor da igual que la hoja de este mes
    # traiga otros conceptos, y si no coincide da igual lo mucho que se
    # parezcan dos proveedores del mismo giro.
    firma = _firma_del_emisor(texto_ocr, tipo_ganador, ejemplos)

    if firma is False:
        logger.info(
            "descartado %s: el RFC del emisor no es el de sus ejemplos", tipo_ganador
        )
        return TIPO_DESCONOCIDO

    if firma is True:
        return tipo_ganador

    # Sin RFC con el que decidir, manda el texto.
    if score < segundo * FACTOR_DISTINCION:
        return TIPO_DESCONOCIDO

    return tipo_ganador


def debe_aprender(texto_ocr: str, textos_existentes: list[str]) -> bool:
    """Si un guardado confirmado merece guardarse como ejemplo automático.

    Conservador porque corre solo, sin que nadie lo revise: descarta el OCR
    pobre (foto ilegible, puro ruido) y la misma foto resubida.
    """
    if len(texto_ocr.strip()) < MIN_CHARS_TEMPLATE:
        return False

    if not textos_existentes:
        return True

    try:
        matriz = TfidfVectorizer(**VECTORIZER_KWARGS).fit_transform(
            textos_existentes + [texto_ocr]
        )
        similitudes = cosine_similarity(matriz[-1], matriz[:-1])[0]
    except Exception:
        # Si no se puede comparar, no aprender: es best-effort y el riesgo de
        # ensuciar el corpus pesa más que el de perder un ejemplo.
        logger.warning("No se pudo deduplicar el ejemplo", exc_info=True)
        return False

    return float(similitudes.max()) <= UMBRAL_DEDUP_EJEMPLO


# --- Paso 3: estructuración ------------------------------------------------


def _extraer_json(crudo: str) -> dict[str, Any]:
    """Parsea la respuesta del modelo tolerando texto alrededor.

    Con ``format:"json"`` Ollama suele devolver JSON limpio, pero no siempre:
    a veces lo envuelve en markdown o añade una frase. Se intenta el parseo
    directo y, si falla, se rescata el primer bloque entre llaves.
    """
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError:
        # Primero, el bloque entre llaves: cubre el markdown y las frases
        # alrededor. Si eso tampoco parsea —el caso de la respuesta cortada,
        # donde el bloque queda con la lista abierta— se intenta cerrarla.
        datos = None
        encontrado = re.search(r"\{[\s\S]*\}", crudo)
        if encontrado is not None:
            try:
                datos = json.loads(encontrado.group(0))
            except json.JSONDecodeError:
                datos = None

        if datos is None:
            datos = _cerrar_json_truncado(crudo)
        if datos is None:
            raise

    if not isinstance(datos, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON.")

    if isinstance(datos.get("items"), list):
        datos["items"] = _sin_repetidos(datos["items"])

    return datos


def _cerrar_json_truncado(crudo: str) -> dict[str, Any] | None:
    """Rescata una respuesta que se cortó a mitad de la lista de partidas.

    Cuando el modelo agota su presupuesto de tokens deja el JSON abierto y sin
    la última partida terminada. Antes eso se perdía entero; aquí se tira lo
    que quedó a medias y se cierran las llaves, que es lo que haría cualquiera
    a mano. Es una red: lo que evita el corte de verdad es la penalización a
    la repetición (ver `OPCIONES_MODELO`).
    """
    corte = crudo.rfind("}")
    if corte == -1:
        return None

    tronco = crudo[: corte + 1]
    for cierre in ("]}", "}]}", "}", ""):
        try:
            datos = json.loads(tronco + cierre)
        except json.JSONDecodeError:
            continue
        if isinstance(datos, dict):
            logger.warning("La respuesta del modelo venía cortada; se rescató lo leído")
            return datos

    return None


def _sin_repetidos(items: list[Any]) -> list[Any]:
    """Quita las partidas repetidas que deja un bucle del modelo.

    Con el OCR ruidoso el modelo puede repetir los mismos renglones docenas de
    veces: en la hoja que destapó esto emitió 51 partidas de 16 reales. Se
    comparan código y cantidad juntos.

    El precio es que una hoja con dos renglones idénticos —mismo código Y misma
    cantidad— pierde uno, y el operador lo vuelve a agregar con un clic. A
    cambio no se le presentan cincuenta partidas fantasma que tendría que
    borrar una por una.
    """
    vistas: set[tuple[str, Any]] = set()
    limpias: list[Any] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        clave = (str(item.get("codigo")).strip().lower(), item.get("cantidad"))
        if clave in vistas:
            continue
        vistas.add(clave)
        limpias.append(item)

    if len(limpias) < len(items):
        logger.info("Se descartaron %d partidas repetidas", len(items) - len(limpias))

    return limpias


def encontrar_campos_null(datos: Any, ruta: str = "") -> list[str]:
    """Rutas de todo lo que quedó en ``null``.

    Devuelve cosas como ``["fecha", "items[0].cantidad"]``. El frontend usa
    esas rutas para pintar **exactamente** esos campos en ámbar. Es la pieza
    central de la experiencia: el sistema admite lo que no supo leer en lugar
    de rellenarlo.
    """
    rutas: list[str] = []

    if isinstance(datos, dict):
        for clave, valor in datos.items():
            hijo = f"{ruta}.{clave}" if ruta else str(clave)
            rutas.extend(encontrar_campos_null(valor, hijo))
    elif isinstance(datos, list):
        for indice, valor in enumerate(datos):
            rutas.extend(encontrar_campos_null(valor, f"{ruta}[{indice}]"))
    elif datos is None and ruta:
        rutas.append(ruta)

    return rutas


def _con_esquema_vigente(esperado: dict[str, Any]) -> dict[str, Any]:
    """Completa un ejemplo guardado con las llaves que el prompt pide hoy.

    `INSTRUCCION_FINAL` le ordena al modelo seguir "EXACTAMENTE la misma
    estructura JSON de los ejemplos anteriores", y una demostración pesa más
    que el prompt de sistema: un ejemplo curado de antes de que existiera
    ``descripcion`` le enseñaría a no emitirla, y justo en los formatos que
    mejor conoce. No se puede rellenar con la descripción del catálogo —sería
    enseñarle a inventar texto que no está en la hoja—, así que va ``None``,
    que es lo que el propio prompt manda usar cuando un campo no aparece.

    Los curados no se borran solos y no hay pantalla para quitarlos, así que
    esta red vale la pena aunque hoy el corpus esté vacío.
    """
    items = esperado.get("items")
    if not isinstance(items, list):
        return esperado

    return {
        **esperado,
        "items": [
            {"codigo": None, "descripcion": None, "cantidad": None, **item}
            if isinstance(item, dict)
            else item
            for item in items
        ],
    }


def _mensajes_few_shot(texto_ocr: str, ejemplos: list[EjemploPlantilla]) -> list[dict]:
    """Arma la conversación con los pares de ejemplo del tipo detectado.

    Al prompt van **solo los curados** y como mucho ``MAX_EJEMPLOS_PROMPT``:
    los auto-aprendidos engordan el corpus de clasificación, no el prompt.
    """
    curados = [ejemplo for ejemplo in ejemplos if ejemplo.curado]
    mensajes: list[dict] = [{"role": "system", "content": PROMPT_SISTEMA}]

    for ejemplo in curados[:MAX_EJEMPLOS_PROMPT]:
        mensajes.append(
            {"role": "user", "content": INSTRUCCION_EJEMPLO + ejemplo.texto_ocr}
        )
        mensajes.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    _con_esquema_vigente(ejemplo.json_esperado), ensure_ascii=False
                ),
            }
        )

    mensajes.append({"role": "user", "content": INSTRUCCION_FINAL + texto_ocr})
    return mensajes


async def _modelo_esta_caliente(cliente: httpx.AsyncClient) -> bool:
    """Si el modelo ya está cargado en VRAM.

    Solo sirve para elegir entre el timeout frío y el caliente. **Jamás debe
    tumbar la petición**: si la consulta falla se asume frío, porque dar más
    tiempo es más seguro que cortar antes de hora.
    """
    try:
        respuesta = await cliente.get(
            f"{settings.OLLAMA_HOST.rstrip('/')}/api/ps",
            timeout=settings.OCR_TIMEOUT_PS,
        )
        cargados = respuesta.json().get("models", [])
        return any(
            modelo.get("name") == settings.OLLAMA_TEXT_MODEL for modelo in cargados
        )
    except Exception:
        logger.debug("No se pudo consultar /api/ps; se asume modelo frío")
        return False


async def _estructurar(texto_ocr: str, ejemplos: list[EjemploPlantilla]) -> dict:
    """Llama al LLM y devuelve el JSON ya parseado."""
    async with httpx.AsyncClient() as cliente:
        caliente = await _modelo_esta_caliente(cliente)
        espera = (
            settings.OCR_TIMEOUT_CALIENTE if caliente else settings.OCR_TIMEOUT_FRIO
        )
        logger.info(
            "estructurando con %s (modelo %s, timeout %ds)",
            settings.OLLAMA_TEXT_MODEL,
            "caliente" if caliente else "frío",
            espera,
        )

        respuesta = await cliente.post(
            f"{settings.OLLAMA_HOST.rstrip('/')}/api/chat",
            json={
                "model": settings.OLLAMA_TEXT_MODEL,
                "messages": _mensajes_few_shot(texto_ocr, ejemplos),
                "stream": False,
                "format": "json",
                "options": OPCIONES_MODELO,
            },
            timeout=espera,
        )
        respuesta.raise_for_status()
        contenido = respuesta.json()["message"]["content"]

    return _extraer_json(contenido)


# --- El pipeline completo --------------------------------------------------


async def extraer(
    imagen_bytes: bytes, ejemplos: list[EjemploPlantilla]
) -> ResultadoExtraccion:
    """Corre los tres pasos. **Nunca lanza**: devuelve el fallo en el resultado.

    ``ejemplos`` es el corpus completo (todos los tipos); la clasificación
    elige y la estructuración usa solo los del tipo ganador.
    """
    try:
        return await asyncio.wait_for(
            _extraer(imagen_bytes, ejemplos),
            timeout=settings.OCR_PRESUPUESTO_TOTAL,
        )
    except TimeoutError:
        logger.warning("Se agotó el presupuesto total de extracción")
        return ResultadoExtraccion(ocr_ok=False, error=IA_NO_DISPONIBLE)
    except Exception:
        # Red de seguridad final: ninguna excepción debe salir de aquí.
        logger.exception("Fallo inesperado extrayendo la remisión")
        return ResultadoExtraccion(ocr_ok=False, error=IA_NO_DISPONIBLE)


async def _extraer(
    imagen_bytes: bytes, ejemplos: list[EjemploPlantilla]
) -> ResultadoExtraccion:
    """El pipeline propiamente dicho, sin el techo de tiempo."""
    # Tesseract es CPU-bound: en el bucle de eventos bloquearía a todos los
    # demás durante segundos.
    try:
        texto = await asyncio.to_thread(texto_ocr_desde_imagen, imagen_bytes)
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract no está instalado en el contenedor")
        return ResultadoExtraccion(ocr_ok=False, error=SIN_TESSERACT)
    except (OSError, ValueError):
        logger.warning("No se pudo abrir la imagen", exc_info=True)
        return ResultadoExtraccion(ocr_ok=False, error=IMAGEN_ILEGIBLE)

    if not texto.strip():
        return ResultadoExtraccion(ocr_ok=False, texto_ocr=texto, error=SIN_TEXTO)

    # La clasificación va aunque la estructuración falle después: saber el
    # tipo sirve para no pedirle al usuario que registre un formato que ya
    # existe. sklearn también es CPU-bound.
    tipo = await asyncio.to_thread(clasificar, texto, ejemplos)
    del_tipo = [ejemplo for ejemplo in ejemplos if ejemplo.tipo == tipo]

    try:
        datos = await _estructurar(texto, del_tipo)
    except Exception:
        logger.warning("La estructuración con el LLM falló", exc_info=True)
        return ResultadoExtraccion(
            ocr_ok=False, tipo_documento=tipo, texto_ocr=texto, error=IA_NO_DISPONIBLE
        )

    return ResultadoExtraccion(
        ocr_ok=True,
        tipo_documento=tipo,
        datos=datos,
        advertencias=encontrar_campos_null(datos),
        texto_ocr=texto,
    )


# --- Utilidades ------------------------------------------------------------


def slugify(nombre: str) -> str:
    """Convierte el nombre que teclea el usuario en un identificador estable.

    ``"Remisión ACME S.A."`` -> ``"remision_acme_s_a"``. Se limita a
    ``[a-z0-9_]`` para que el slug pueda viajar en una URL sin escapes.
    """
    sin_acentos = (
        unicodedata.normalize("NFKD", nombre)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    limpio = re.sub(r"[^a-z0-9]+", "_", sin_acentos.lower()).strip("_")
    return limpio[:80]
