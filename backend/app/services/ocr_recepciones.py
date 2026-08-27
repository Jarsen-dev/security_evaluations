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
    '"YYYY-MM-DD", "items": [{"codigo": str, "cantidad": number}]}. '
    '"folio" es el número de folio o de remisión del documento. "codigo" es '
    "la clave o número de parte del producto tal como aparece en la hoja. "
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


def clasificar(texto_ocr: str, ejemplos: list[EjemploPlantilla]) -> str:
    """Devuelve el tipo de documento más parecido, o ``desconocido``.

    Determinista, gratis y sin red: compara el texto OCR contra el de cada
    ejemplo guardado. Si TF-IDF revienta (corpus degenerado, vocabulario
    vacío) se sigue con ``desconocido``: se pierden los ejemplos few-shot,
    pero el prompt de sistema por sí solo ya describe el JSON esperado.
    """
    if not texto_ocr.strip() or not ejemplos:
        return TIPO_DESCONOCIDO

    try:
        corpus = [ejemplo.texto_ocr for ejemplo in ejemplos] + [texto_ocr]
        matriz = TfidfVectorizer(**VECTORIZER_KWARGS).fit_transform(corpus)
        similitudes = cosine_similarity(matriz[-1], matriz[:-1])[0]
    except Exception:
        logger.warning("TF-IDF falló; se sigue con tipo desconocido", exc_info=True)
        return TIPO_DESCONOCIDO

    mejor = int(similitudes.argmax())
    tipo_ganador = ejemplos[mejor].tipo
    score = float(similitudes[mejor])

    # El mejor score de OTRO tipo y el margen son lo único que permite
    # recalibrar el umbral sin adivinar. Se loguean siempre.
    otros = [
        float(valor)
        for indice, valor in enumerate(similitudes)
        if ejemplos[indice].tipo != tipo_ganador
    ]
    segundo = max(otros) if otros else 0.0

    logger.info(
        "clasificación TF-IDF → %s (score=%.3f, 2º tipo=%.3f, margen=%.3f, "
        "umbral=%.3f, %d ejemplos de %d tipos)",
        tipo_ganador,
        score,
        segundo,
        score - segundo,
        settings.OCR_UMBRAL_SIMILITUD,
        len(ejemplos),
        len({ejemplo.tipo for ejemplo in ejemplos}),
    )

    if score < settings.OCR_UMBRAL_SIMILITUD:
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
        encontrado = re.search(r"\{[\s\S]*\}", crudo)
        if encontrado is None:
            raise
        datos = json.loads(encontrado.group(0))

    if not isinstance(datos, dict):
        raise ValueError("La respuesta del modelo no es un objeto JSON.")
    return datos


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
                "content": json.dumps(ejemplo.json_esperado, ensure_ascii=False),
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
                "options": {"temperature": 0.1, "num_predict": 800},
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
