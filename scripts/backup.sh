#!/usr/bin/env bash
# Backup do banco. Usa `sqlite3 .backup` em vez de `cp`: copiar o arquivo com o
# bot escrevendo pode gerar um .db corrompido, o .backup faz copia consistente.
#
# Cron diario as 3h:
#   0 3 * * * /caminho/scripts/backup.sh >> /var/log/caderneta-backup.log 2>&1
set -euo pipefail

CONTAINER="${CONTAINER:-caderneta-bot}"
DESTINO="${DESTINO:-$HOME/backups/caderneta}"
MANTER_DIAS="${MANTER_DIAS:-30}"
DB_PATH="${DB_PATH:-/data/caderneta.db}"

mkdir -p "$DESTINO"
carimbo="$(date +%Y%m%d-%H%M%S)"
arquivo="$DESTINO/caderneta-$carimbo.db"

echo "[backup] copiando de $CONTAINER:$DB_PATH"
docker exec "$CONTAINER" python -c "
import sqlite3, sys
origem = sqlite3.connect(sys.argv[1])
destino = sqlite3.connect('/tmp/backup.db')
with destino:
    origem.backup(destino)
destino.close(); origem.close()
" "$DB_PATH"

docker cp "$CONTAINER:/tmp/backup.db" "$arquivo"
docker exec "$CONTAINER" rm -f /tmp/backup.db

gzip -f "$arquivo"
echo "[backup] gerado: $arquivo.gz ($(du -h "$arquivo.gz" | cut -f1))"

# Verificacao: backup que nao abre nao e backup.
if ! zcat "$arquivo.gz" | head -c 16 | grep -q "SQLite format 3"; then
    echo "[backup] ERRO: arquivo gerado nao parece um banco SQLite" >&2
    exit 1
fi

apagados=$(find "$DESTINO" -name 'caderneta-*.db.gz' -mtime +"$MANTER_DIAS" -print -delete | wc -l)
echo "[backup] ok. backups antigos removidos: $apagados"
