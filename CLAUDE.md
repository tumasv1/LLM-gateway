# CLAUDE.md — LLM Gateway

Контекст для Claude Code при работе с этим репозиторием.

## Что это

Общий **LLM-шлюз** на базе [LiteLLM Proxy](https://docs.litellm.ai/) для всех LLM-инструментов пользователя (агент RAGv2, агент на DeepSeek/openclaw, будущие боты, n8n, IDE). Единая точка входа ко всем моделям: один OpenAI-совместимый адрес, за которым — маршрутизация по провайдерам, fallback, балансировка, учёт расходов и лимиты по проектам.

Раньше LiteLLM жил внутри проекта RAGv2 — теперь вынесен сюда как самостоятельная инфраструктура.

## Где работает

- **Прод**: отдельный **LXC `192.168.3.203`** (Proxmox), Docker внутри, путь `/opt/LLM-gateway`. Доступ **только по LAN**. SSH: `root@192.168.3.203` (passwordless-ключ настроен).
- **Dev**: локально на Mac через Docker Desktop (тот же `docker compose`).
- UI/API шлюза: `http://192.168.3.203:4000` (UI на `/ui`).

## Текущий статус (развёрнуто и проверено)

- ✅ Стек поднят на LXC, все 3 контейнера healthy. RAM по факту: litellm ~0.85–0.9 ГБ, postgres ~40 МБ, redis ~10 МБ → **~0.95 ГБ суммарно**.
- ✅ Каталог моделей управляется через UI (не файл): `gpt-4.1-mini` (OpenRouter, основной), `gpt-4.1-mini-fallback` (nano-gpt, резервный), `deepseek-chat` (ключ-заглушка).
- ✅ Ключи провайдеров обновлены (старые засветились в чате).
- ✅ Fallback проверен: при недоступности OpenRouter запросы к `gpt-4.1-mini` автоматически уходят в nano-gpt (`gpt-4.1-mini-fallback`), клиент не замечает.
- ✅ Мультитенантность проверена: virtual key с `models=[gpt-4.1-mini]` получает отказ при попытке к `deepseek-chat`.
- ✅ Бэкапы: cron root ежедневно 03:00 → `backups/`, ротация 14, лог `/var/log/llm-gw-backup.log`. **Восстановление протестировано**.
- ✅ RAGv2 переключён на шлюз (`http://192.168.3.203:4000/v1`, virtual key `ragv2`). Будущие клиенты: openclaw/DeepSeek-агент, боты, n8n.
- ✅ Трейсинг в Langfuse подключён (`success_callback: ["langfuse"]` в `config/litellm_config.yaml`) — активируется, когда в `.env` появятся реальные `LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY` от развёрнутого self-hosted Langfuse (отдельный проект `../Langfuse`, свой LXC).

## Архитектура

```
клиенты (virtual keys) ──► LiteLLM :4000 ──► OpenRouter / nano-gpt / DeepSeek / ...
                                │
                                ├─ Postgres : virtual keys, бюджеты, история расходов
                                └─ Redis    : счётчики rpm/tpm (load balancing) + кэш
```

- **litellm** — сам шлюз (`ghcr.io/berriai/litellm:main-stable`), порт 4000.
- **postgres** — платформенные данные (ключи/бюджеты/`LiteLLM_SpendLogs`). **Бэкапить** (`scripts/backup_db.sh`).
- **redis** — общие счётчики для `usage-based-routing-v2` и кэш ответов.

## Ключевые решения

- **Мультитенантность через virtual keys**: каждый проект-клиент получает свой ключ с бюджетом, лимитами (rpm/tpm) и списком разрешённых моделей. Провайдерские ключи живут ТОЛЬКО здесь, клиентам не раздаются.
- **Каталог моделей управляется через UI** (`store_model_in_db: true`). `config/litellm_config.yaml` содержит только `router_settings`, `litellm_settings`, `general_settings` — без `model_list`. Модели добавляются/редактируются в UI без перезапуска.
- **Именование deployment-ов**: `model_name` = имя для клиентов (`gpt-4.1-mini`); `LiteLLM Model Name` = внутренний роутинг. Для OpenRouter использовать `openrouter/openai/gpt-4.1-mini` (api_base не нужен — LiteLLM знает адрес). Для кастомных провайдеров (nano-gpt) — Provider `openai` + `api_base = https://nano-gpt.com/api/v1` + `openai/gpt-4.1-mini`.
- **Схема надёжности gpt-4.1-mini**: один основной deployment (OpenRouter) + отдельная модель-резерв `gpt-4.1-mini-fallback` (nano-gpt). Fallback прописан в `config/litellm_config.yaml`. При сбое OpenRouter LiteLLM делает `num_retries=3`, затем переключается на nano-gpt. После `cooldown_time=30с` снова пробует OpenRouter. `routing_strategy: usage-based-routing-v2` остаётся в конфиге — пригодится, если в группу добавится второй deployment.
- **`deepseek-v4-flash-fallback` (app.provod.ai) — общий аварийный фолбэк**: работает в РФ без VPN. Прописан последним звеном в fallback-цепочке у всех моделей (`gpt-4.1-mini`, `gpt-4.1-mini-fallback`, `deepseek-v4-flash`, `deepseek-v4-flash-thinking`, `deepseek-v4-pro`) — если сломается VPN и станут недоступны OpenRouter/DeepSeek official, трафик уйдёт сюда. Сам по себе не используется напрямую, дальше никуда не фолбэчит (конечная точка).
- **Различать провайдеров в логах**: смотреть колонку `api_base` в `LiteLLM_SpendLogs` — там видно кто реально ответил (openrouter.ai vs nano-gpt.com).
- **LAN-only**: LXC без публичного IP; при необходимости внешнего доступа — только через существующий reverse-proxy (nginx) с TLS, не публикуя 4000 напрямую.

## Команды

```bash
docker compose up -d              # поднять стек
docker compose restart litellm    # перечитать config/litellm_config.yaml (ВАЖНО: см. gotcha)
docker compose logs -f litellm    # логи
docker compose down               # остановить
scripts/create_project_key.sh <alias> <model> <budget$> [rpm]   # завести virtual key проекту
scripts/backup_db.sh              # бэкап Postgres (ключи + история); уже стоит в cron 03:00
```
UI: `http://192.168.3.203:4000/ui` (логин `admin`, пароль = `LITELLM_MASTER_KEY`).

## Проверка восстановления из бэкапа

Никогда не восстанавливать поверх рабочей БД — лить дамп во **временный** контейнер и сверять:
```bash
cd /opt/LLM-gateway
LATEST=$(ls -t backups/litellm-*.sql.gz | head -1)
docker run -d --name pg-restore-test -e POSTGRES_USER=litellm -e POSTGRES_PASSWORD=test -e POSTGRES_DB=litellm postgres:16-alpine
# ВАЖНО: ждать НАСТОЯЩИЙ сервер реальным запросом (pg_isready врёт во время init):
for i in $(seq 1 40); do docker exec pg-restore-test psql -U litellm -d litellm -tAc "SELECT 1" >/dev/null 2>&1 && break; sleep 1; done
zcat "$LATEST" | docker exec -i pg-restore-test psql -U litellm -d litellm
docker exec pg-restore-test psql -U litellm -d litellm -c '\dt'
docker rm -f pg-restore-test
```

## Как добавить новый проект-клиент

1. `scripts/create_project_key.sh` (или UI → Virtual Keys → Create) → получить `sk-...`.
2. В проекте-клиенте: `base_url = http://<lxc-ip>:4000/v1`, `api_key = <virtual key>`, `model = <имя из каталога>`.
3. Код клиента не меняется — он думает, что общается с обычным OpenAI API.

## Gotchas (важные грабли)

- **Конфиг читается ОДИН раз при старте процесса.** Правка `config/litellm_config.yaml` требует `docker compose restart litellm`. `docker compose up -d` при изменении только примонтированного файла **НЕ пересоздаёт** контейнер → процесс держит старый конфиг. (Проверено: с правкой ключа `up -d` не подхватывал, помогал только `restart`/`--force-recreate`.)
- **mem_limit: 1g.** При 512m LiteLLM падает с OOM (exit 137) ещё на старте.
- **store_model_in_db: true** — модели/ключи, добавленные через UI, лежат в Postgres, а не в файле. Файл — только начальная загрузка.
- **Кастомные цены** в каталоге обязательны для агрегаторов (OpenRouter/nano-gpt) — их нет во встроенной таблице цен LiteLLM, иначе расходы в $ неверны.
- **Упавшие попытки (fallback) НЕ пишутся** в `LiteLLM_SpendLogs` по умолчанию — логируются только успешные вызовы (даже отдельная таблица `LiteLLM_ErrorLogs` по умолчанию пустая). Признак fallback в логах — `model_group`/`api_base` успешной строки (она от запасного провайдера), а не отдельная failure-строка. Полную видимость сбоев/fallback даёт `/metrics` (Prometheus) и Langfuse.
- **Redis с паролем** (`--requirepass`): и сам redis, и router в конфиге используют `REDIS_PASSWORD`.
- **`.env` обязателен** рядом с `docker-compose.yml`: пароль в `POSTGRES_PASSWORD` и внутри `DATABASE_URL` должны СОВПАДАТЬ, иначе LiteLLM не подключится к БД. Шаблон — `.env.example`.
- **Скрипты-bash + `set -e` + `grep -c`**: `grep -c` возвращает код 1 при нуле совпадений и рушит скрипт с `set -e` именно в «хорошем» случае → оборачивать в `|| true`.
- **Гонка старта Postgres**: официальный образ при первом запуске поднимает временный init-сервер, потом гасит и стартует настоящий. `pg_isready` отвечает «готов» уже на временном → можно попасть в окно «database is shutting down». Ждать настоящий сервер реальным `psql -c 'SELECT 1'` в цикле.
- **Безопасность**: реальные ключи провайдеров (OpenRouter/nano-gpt) светились в чате при настройке → были перевыпущены и обновлены в UI шлюза.
- **Кнопка «Test Model» в UI сломана для gpt-4.1-mini**: шлёт `max_tokens: 5`, модель требует минимум 16 → ошибка `integer_below_min_value`. Тестировать через curl: `curl -s -X POST http://localhost:4000/v1/chat/completions -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" -d '{"model":"gpt-4.1-mini","messages":[{"role":"user","content":"2+2=?"}],"max_tokens":50}'`.

## Код-стиль

Комментарии на русском, неформально, для новичка (как в основном проекте пользователя).
