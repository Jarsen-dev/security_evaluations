#!/bin/sh
# ===========================================================================
# Arranque del backend: aplica migraciones y luego cede el control a uvicorn.
# `set -e` corta el arranque si Alembic falla, para no servir la API contra
# un esquema desactualizado.
# ===========================================================================
set -e

echo "[entrypoint] Aplicando migraciones de Alembic..."
alembic upgrade head
echo "[entrypoint] Migraciones al día."

echo "[entrypoint] Iniciando servidor..."
exec "$@"
