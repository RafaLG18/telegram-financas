#!/bin/sh
# Migrate before starting the bot. Since there is only one replica (see
# helm/values), there is no risk of two concurrent migrations.
set -eu

echo "[entrypoint] applying migrations to ${DB_PATH:-/data/caderneta.db}"
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
