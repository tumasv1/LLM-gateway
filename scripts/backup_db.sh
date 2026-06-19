#!/usr/bin/env bash
# Бэкап Postgres шлюза (virtual keys, бюджеты, история расходов).
# Запускать из корня проекта; в LXC повесить на cron, напр.:
#   0 3 * * *  cd /opt/LLM-gateway && ./scripts/backup_db.sh >> /var/log/llm-gw-backup.log 2>&1
#
# Хранит последние 14 бэкапов в ./backups, старые удаляет.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

mkdir -p backups
STAMP="$(date +%F_%H%M)"
OUT="backups/litellm-$STAMP.sql.gz"

echo "[$(date)] делаю бэкап → $OUT"
docker compose exec -T postgres pg_dump -U litellm litellm | gzip > "$OUT"

# ротация: оставить 14 свежих
ls -1t backups/litellm-*.sql.gz | tail -n +15 | xargs -r rm -f
echo "[$(date)] готово. Текущие бэкапы:"
ls -1t backups/litellm-*.sql.gz | head
