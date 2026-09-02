"""Espejo en disco de los formatos que el clasificador aprende.

Una carpeta por formato y una subcarpeta por ejemplo, con la foto, el JSON de
lo que se confirmó y el texto que leyó el OCR. Existe para poder revisar como
archivos lo que el sistema aprendió: qué hoja vio, qué sacó de ella y con qué
texto la reconoce.

**Es una copia, no la fuente.** El clasificador sigue leyendo el corpus de la
base de datos, así que borrar una carpeta no hace que el sistema olvide un
formato. Y por eso mismo nada de aquí puede tumbar una recepción: si el disco
está lleno, montado en solo lectura o falta el volumen, se registra el fallo y
la vida sigue.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import DIRECTORIO_FORMATOS

logger = logging.getLogger(__name__)

#: Ejemplos que se conservan por formato. Al llegar al tope entra el nuevo y
#: sale el más viejo: si el proveedor rediseña su remisión, el espejo se pone
#: al día solo en vez de quedarse anclado a las primeras hojas que se vieron.
MAX_EJEMPLOS_DISCO = 4

#: Extensión por tipo de imagen. La lista blanca de las fotos de recepción son
#: JPG, PNG y WEBP; cualquier otra cosa se guarda como .bin antes que inventar.
EXTENSIONES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

NOMBRE_FOTO = "remision"
NOMBRE_JSON = "extraido.json"
NOMBRE_TEXTO = "texto_ocr.txt"
NOMBRE_FORMATO = "formato.txt"


def carpetas_a_borrar(nombres: list[str], tope: int = MAX_EJEMPLOS_DISCO) -> list[str]:
    """Cuáles sobran para que queden ``tope`` ejemplos, contando el que entra.

    Las carpetas se llaman por su fecha, así que ordenar por nombre es ordenar
    por antigüedad y no hace falta preguntarle nada al sistema de archivos.

    Va aparte y sin tocar disco para poder probar la rotación, que es la parte
    con más filo: se borran directorios.
    """
    if tope < 1:
        return sorted(nombres)

    sobran = len(nombres) - tope + 1
    return sorted(nombres)[:sobran] if sobran > 0 else []


def guardar_ejemplo(
    *,
    slug: str,
    nombre: str,
    imagen: bytes,
    tipo_mime: str,
    texto_ocr: str,
    json_esperado: dict[str, Any],
    raiz: Path | None = None,
) -> None:
    """Escribe un ejemplo en disco y rota los viejos.

    ``slug`` da nombre a la carpeta y no el nombre tecleado: ya viene saneado a
    ``[a-z0-9_]`` por ``ocr_recepciones.slugify()``, así que un formato llamado
    ``../../etc`` no puede escribir fuera de su sitio. El nombre legible se
    guarda dentro, en ``formato.txt``, que es lo que hace entendible la carpeta
    al abrirla.

    Nunca lanza: ver el docstring del módulo.
    """
    base = (raiz or DIRECTORIO_FORMATOS) / slug

    try:
        base.mkdir(parents=True, exist_ok=True)

        previas = [hijo.name for hijo in base.iterdir() if hijo.is_dir()]
        for sobra in carpetas_a_borrar(previas):
            shutil.rmtree(base / sobra, ignore_errors=True)

        carpeta = base / datetime.now().strftime("%Y%m%d-%H%M%S")
        carpeta.mkdir(exist_ok=True)

        (carpeta / (NOMBRE_FOTO + EXTENSIONES.get(tipo_mime, ".bin"))).write_bytes(imagen)
        (carpeta / NOMBRE_JSON).write_text(
            json.dumps(json_esperado, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (carpeta / NOMBRE_TEXTO).write_text(texto_ocr, encoding="utf-8")

        # Se reescribe cada vez: si el formato se renombra, la carpeta lo dice.
        (base / NOMBRE_FORMATO).write_text(
            f"{nombre}\nIdentificador: {slug}\n", encoding="utf-8"
        )

        logger.info("Ejemplo de %s guardado en disco: %s", slug, carpeta)

    except Exception:
        logger.warning(
            "No se pudo escribir el espejo del formato %s; el corpus de la base "
            "no se ve afectado",
            slug,
            exc_info=True,
        )
