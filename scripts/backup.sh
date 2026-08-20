#!/usr/bin/env bash
# Database backup. Uses `sqlite3 .backup` instead of `cp`: copying the file
# while the bot writes can produce a corrupt .db, while .backup makes a
# consistent copy.
#
# Daily cron at 3am:
#   0 3 * * * /path/to/scripts/backup.sh >> /var/log/caderneta-backup.log 2>&1
set -euo pipefail

CONTAINER="${CONTAINER:-caderneta-bot}"
DESTINATION="${DESTINATION:-${DESTINO:-$HOME/backups/caderneta}}"
KEEP_DAYS="${KEEP_DAYS:-${MANTER_DIAS:-30}}"
DB_PATH="${DB_PATH:-/data/caderneta.db}"

mkdir -p "$DESTINATION"
stamp="$(date +%Y%m%d-%H%M%S)"
file="$DESTINATION/caderneta-$stamp.db"

echo "[backup] copying from $CONTAINER:$DB_PATH"
docker exec "$CONTAINER" python -c "
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect('/tmp/backup.db')
with target:
    source.backup(target)
target.close(); source.close()
" "$DB_PATH"

docker cp "$CONTAINER:/tmp/backup.db" "$file"
docker exec "$CONTAINER" rm -f /tmp/backup.db

gzip -f "$file"
echo "[backup] created: $file.gz ($(du -h "$file.gz" | cut -f1))"

# Verification: a backup that does not open is not a backup.
if ! zcat "$file.gz" | head -c 16 | grep -q "SQLite format 3"; then
    echo "[backup] ERROR: the generated file does not look like a SQLite database" >&2
    exit 1
fi

deleted=$(find "$DESTINATION" -name 'caderneta-*.db.gz' -mtime +"$KEEP_DAYS" -print -delete | wc -l)
echo "[backup] ok. old backups removed: $deleted"
