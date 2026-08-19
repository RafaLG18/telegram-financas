#!/bin/sh
# Migracao antes de subir o bot. Como so existe uma replica (ver helm/values),
# nao ha risco de duas migracoes concorrentes.
set -eu

echo "[entrypoint] aplicando migracoes em ${DB_PATH:-/data/caderneta.db}"
alembic upgrade head

echo "[entrypoint] iniciando: $*"
exec "$@"
