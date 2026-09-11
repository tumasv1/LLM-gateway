# LLM Gateway

Общий LLM-шлюз на [LiteLLM Proxy](https://docs.litellm.ai/) для всех LLM-инструментов: единый OpenAI-совместимый адрес, за которым — маршрутизация по провайдерам, fallback, балансировка, учёт расходов и лимиты по проектам.

Деплой: отдельный **LXC** на домашнем сервере, доступ **только по LAN**.

## Состав

| Сервис | Зачем |
|--------|-------|
| litellm | сам шлюз (порт 4000, UI на `/ui`); образ пиним на `ghcr.io/berriai/litellm:v1.100.0`, не `:latest` / `:main-stable` |
| postgres | virtual keys, бюджеты, история расходов |
| redis | счётчики rpm/tpm для балансировки + кэш |
| presidio-analyzer / anonymizer | детектор и необратимая маска ПДн (Guardrails). Порты наружу не публикуются. Политика — в UI, не в YAML |

## Быстрый старт (локально / в LXC)

```bash
cp .env.example .env          # заполнить ключи провайдеров, пароли, master key
docker compose up -d
curl http://localhost:4000/health/liveliness     # "I'm alive!"
```

Подробный деплой в LXC → [`docs/lxc-setup.md`](docs/lxc-setup.md).

## Подключить проект-клиент

1. Завести ключ: `./scripts/create_project_key.sh <alias> <model> <budget$>`
2. В клиенте: `base_url=http://<lxc-ip>:4000/v1`, `api_key=<virtual key>`, `model=<из каталога>`.

Подробно про ключи/бюджеты → [`docs/virtual-keys.md`](docs/virtual-keys.md).

## Каталог моделей

Каталог живёт в Postgres (UI/API, `store_model_in_db: true`), не в файле. Сейчас: `gpt-4.1-mini` / `gpt-4.1-mini-fallback`, `deepseek/deepseek-flash`, `deepseek-v4-flash-latest`, `deepseek-v4-pro`, `openrouter/xiaomi/mimo-v2.5`, аварийный `deepseek-v4-flash-fallback`. Зеркало fallbacks для disaster recovery — в [`config/litellm_config.yaml`](config/litellm_config.yaml).

> ⚠️ После правки `config/litellm_config.yaml` нужен `docker compose restart litellm` — конфиг читается только при старте процесса. См. раздел Gotchas в [CLAUDE.md](CLAUDE.md).

## Команды

```bash
docker compose up -d / down / restart litellm
docker compose logs -f litellm
scripts/backup_db.sh           # бэкап Postgres
```
