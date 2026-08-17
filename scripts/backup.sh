#!/usr/bin/env bash
#
# Respaldo de la base de datos del sistema de evaluaciones.
#
# Genera un volcado comprimido con la fecha en el nombre y borra los que
# superan la retención configurada. Pensado para cron:
#
#   0 2 * * * /ruta/al/proyecto/scripts/backup.sh >> /var/log/evaluaciones_backup.log 2>&1
#
# Restaurar:
#   gunzip -c backups/evaluaciones_20260817_020000.sql.gz | \
#     docker exec -i evaluaciones_db psql -U evaluaciones -d evaluaciones
#
set -euo pipefail

# --- Configuración ---------------------------------------------------------

RAIZ_PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIRECTORIO_BACKUPS="${DIRECTORIO_BACKUPS:-$RAIZ_PROYECTO/backups}"
DIAS_RETENCION="${DIAS_RETENCION:-30}"
CONTENEDOR_DB="${CONTENEDOR_DB:-evaluaciones_db}"

# Las credenciales salen del .env del proyecto: no se duplican aquí.
if [[ -f "$RAIZ_PROYECTO/.env" ]]; then
    # shellcheck disable=SC1091  # la ruta se resuelve en tiempo de ejecución
    set -a && source "$RAIZ_PROYECTO/.env" && set +a
else
    echo "ERROR: no se encontró $RAIZ_PROYECTO/.env" >&2
    exit 1
fi

POSTGRES_USER="${POSTGRES_USER:-evaluaciones}"
POSTGRES_DB="${POSTGRES_DB:-evaluaciones}"

marca_tiempo() { date '+%Y-%m-%d %H:%M:%S'; }
registrar() { echo "[$(marca_tiempo)] $*"; }

# --- Verificaciones previas ------------------------------------------------

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR_DB"; then
    registrar "ERROR: el contenedor '$CONTENEDOR_DB' no está corriendo."
    exit 1
fi

mkdir -p "$DIRECTORIO_BACKUPS"

ARCHIVO="$DIRECTORIO_BACKUPS/evaluaciones_$(date '+%Y%m%d_%H%M%S').sql.gz"
PARCIAL="$ARCHIVO.parcial"

# --- Volcado ---------------------------------------------------------------

registrar "Iniciando respaldo de '$POSTGRES_DB'…"

# Se escribe primero a un archivo .parcial y se renombra al final: así un
# respaldo interrumpido nunca queda con nombre de respaldo válido, y cron no
# lo confunde con uno bueno.
if docker exec "$CONTENEDOR_DB" pg_dump \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --clean --if-exists --no-owner --no-privileges \
    | gzip -9 > "$PARCIAL"; then
    mv "$PARCIAL" "$ARCHIVO"
else
    registrar "ERROR: pg_dump falló. Se descarta el archivo incompleto."
    rm -f "$PARCIAL"
    exit 1
fi

# gzip de un volcado vacío pesa ~20 bytes: eso indica que algo salió mal
# aunque pg_dump haya devuelto 0.
TAMANO=$(stat -c%s "$ARCHIVO")
if [[ "$TAMANO" -lt 1024 ]]; then
    registrar "ERROR: el respaldo pesa solo $TAMANO bytes; se descarta."
    rm -f "$ARCHIVO"
    exit 1
fi

registrar "Respaldo creado: $ARCHIVO ($(numfmt --to=iec-i --suffix=B "$TAMANO" 2>/dev/null || echo "$TAMANO bytes"))"

# --- Retención -------------------------------------------------------------

BORRADOS=$(find "$DIRECTORIO_BACKUPS" -name 'evaluaciones_*.sql.gz' -type f \
    -mtime "+$DIAS_RETENCION" -print -delete | wc -l)

if [[ "$BORRADOS" -gt 0 ]]; then
    registrar "Eliminados $BORRADOS respaldo(s) con más de $DIAS_RETENCION días."
fi

TOTAL=$(find "$DIRECTORIO_BACKUPS" -name 'evaluaciones_*.sql.gz' -type f | wc -l)
registrar "Respaldos disponibles: $TOTAL"
