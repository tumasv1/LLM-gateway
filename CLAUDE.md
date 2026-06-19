# CLAUDE.md — LLM Gateway

Контекст для Claude Code при работе с этим репозиторием.

## Что это

Общий **LLM-шлюз** на базе [LiteLLM Proxy](https://docs.litellm.ai/) для всех LLM-инструментов пользователя (агент RAGv2, агент на DeepSeek/openclaw, будущие боты, n8n, IDE). Единая точка входа ко всем моделям: один OpenAI-совместимый адрес, за которым — маршрутизация по провайдерам, fallback, балансировка, учёт расходов и лимиты по проектам.

Раньше LiteLLM жил внутри проекта RAGv2 — теперь вынесен сюда как самостоятельная инфраструктура.

## Где работает

- **Прод**: отдельный **LXC** на домашнем сервере (Proxmox), Docker внутри, `docker compose up`. Доступ **только по LAN** (наружу не публикуется).
- **Dev**: локально на Mac через Docker Desktop (тот же `docker compose`).

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
- **Каталог моделей** — `config/litellm_config.yaml` как bootstrap. В рантайме модели/ключи управляются через UI/API (`store_model_in_db: true`) — без правки файлов и перезапуска.
- **Load balancing + надёжность**: несколько deployment-ов под одним `model_name` (разные провайдеры/ключи) + `routing_strategy: usage-based-routing-v2` (Redis) + `num_retries`/`cooldown`/`fallbacks`.
- **LAN-only**: LXC без публичного IP; при необходимости внешнего доступа — только через существующий reverse-proxy (nginx) с TLS, не публикуя 4000 напрямую.

## Команды

```bash
docker compose up -d              # поднять стек
docker compose restart litellm    # перечитать config/litellm_config.yaml (ВАЖНО: см. gotcha)
docker compose logs -f litellm    # логи
docker compose down               # остановить
scripts/create_project_key.sh <alias> <model> <budget$>   # завести virtual key проекту
scripts/backup_db.sh              # бэкап Postgres (ключи + история)
```
UI: `http://<lxc-ip>:4000/ui` (логин `admin`, пароль = `LITELLM_MASTER_KEY`).

## Как добавить новый проект-клиент

1. `scripts/create_project_key.sh` (или UI → Virtual Keys → Create) → получить `sk-...`.
2. В проекте-клиенте: `base_url = http://<lxc-ip>:4000/v1`, `api_key = <virtual key>`, `model = <имя из каталога>`.
3. Код клиента не меняется — он думает, что общается с обычным OpenAI API.

## Gotchas (важные грабли)

- **Конфиг читается ОДИН раз при старте процесса.** Правка `config/litellm_config.yaml` требует `docker compose restart litellm`. `docker compose up -d` при изменении только примонтированного файла **НЕ пересоздаёт** контейнер → процесс держит старый конфиг. (Проверено: с правкой ключа `up -d` не подхватывал, помогал только `restart`/`--force-recreate`.)
- **mem_limit: 1g.** При 512m LiteLLM падает с OOM (exit 137) ещё на старте.
- **store_model_in_db: true** — модели/ключи, добавленные через UI, лежат в Postgres, а не в файле. Файл — только начальная загрузка.
- **Кастомные цены** в каталоге обязательны для агрегаторов (OpenRouter/nano-gpt) — их нет во встроенной таблице цен LiteLLM, иначе расходы в $ неверны.
- **Упавшие попытки (fallback) НЕ пишутся** в `LiteLLM_SpendLogs` по умолчанию — логируются только успешные вызовы. Видимость сбоев/fallback даёт `/metrics` (Prometheus) и Langfuse, а не встроенные логи.
- **Redis с паролем** (`--requirepass`): и сам redis, и router в конфиге используют `REDIS_PASSWORD`.

## Код-стиль

Комментарии на русском, неформально, для новичка (как в основном проекте пользователя).
