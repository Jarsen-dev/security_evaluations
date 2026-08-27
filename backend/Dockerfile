# ===========================================================================
# Backend FastAPI — imagen multi-stage
#   target `dev`  -> código montado desde el host, recarga en caliente
#   target `prod` -> código copiado, usuario sin privilegios (default)
# ===========================================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# `libpq5` no hace falta (asyncpg no usa libpq), pero `curl` sirve para
# diagnosticar el healthcheck desde dentro del contenedor.
#
# Tesseract es el paso (1) del pipeline de recepciones: lee la foto de la
# remisión antes de que el LLM acomode el texto. Los dos idiomas son
# necesarios, no opcionales: las hojas traen el cuerpo en español y los
# encabezados de muchos proveedores en inglés, y `lang="spa+eng"` los
# resuelve en una sola pasada.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Las dependencias van antes que el código: así un cambio en app/ no
# invalida la capa de pip.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# --- Desarrollo ------------------------------------------------------------
FROM base AS dev

COPY . .
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

# --- Producción ------------------------------------------------------------
FROM base AS prod

RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser . .
USER appuser

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}"]
