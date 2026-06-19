#!/usr/bin/env bash
# Заводит virtual key для проекта-клиента через API LiteLLM.
#
# Использование:
#   ./scripts/create_project_key.sh <alias> <model> <budget_usd> [rpm]
# Пример:
#   ./scripts/create_project_key.sh ragv2 gpt-4.1-mini 5 200
#
# Требует переменные окружения (или подхватит из .env):
#   LITELLM_MASTER_KEY  — мастер-ключ шлюза
#   GATEWAY_URL         — адрес шлюза (по умолчанию http://localhost:4000)

set -euo pipefail

# подхватим .env, если он рядом
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$SCRIPT_DIR/.env" ] && set -a && . "$SCRIPT_DIR/.env" && set +a

ALIAS="${1:?нужен alias проекта, напр. ragv2}"
MODEL="${2:?нужно имя модели из каталога, напр. gpt-4.1-mini}"
BUDGET="${3:?нужен месячный бюджет в $, напр. 5}"
RPM="${4:-}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:4000}"
: "${LITELLM_MASTER_KEY:?не задан LITELLM_MASTER_KEY}"

# тело запроса собираем питоном — надёжнее, чем heredoc с условиями
BODY=$(ALIAS="$ALIAS" MODEL="$MODEL" BUDGET="$BUDGET" RPM="$RPM" python3 - <<'PY'
import json, os
body = {
    "key_alias": os.environ["ALIAS"],
    "models": [os.environ["MODEL"]],
    "max_budget": float(os.environ["BUDGET"]),
    "budget_duration": "30d",
    "metadata": {"tags": [os.environ["ALIAS"]]},
}
rpm = os.environ.get("RPM", "").strip()
if rpm:
    body["rpm_limit"] = int(rpm)
print(json.dumps(body))
PY
)

echo "Создаю virtual key: alias=$ALIAS model=$MODEL budget=\$$BUDGET ${RPM:+rpm=$RPM}"
curl -s -X POST "$GATEWAY_URL/key/generate" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY" | python3 -m json.tool
