# Мультитенантность: Teams → Keys → Budgets

Шлюз один, а пользуются им много проектов. Чтобы их разделить — каждому проекту свой **virtual key**.

## Зачем

- **Раздельный учёт расходов**: видно, какой проект сколько потратил ($ и токены).
- **Изоляция**: упёрся в лимит один — остальные живы; утёк один ключ — отзываешь только его.
- **Права и бюджеты**: одному проекту доступен только `gpt-4.1-mini`, другому — `deepseek-chat`; у каждого свой месячный потолок и rate-limit.

Провайдерские ключи (OpenRouter, nano-gpt, DeepSeek) клиентам НЕ выдаются — они лежат в `.env` шлюза. Клиент знает только свой virtual key.

## Иерархия LiteLLM

- **Team** (команда/проектная группа) — на неё можно повесить общий бюджет и список моделей.
- **Key** (virtual key) — принадлежит команде или стоит сам по себе; им и ходит клиент.
- **Budget** — лимит трат ($) за период (`budget_duration`, напр. `30d`); при превышении шлюз отдаёт ошибку.

## Создать ключ — скриптом

```bash
./scripts/create_project_key.sh ragv2 gpt-4.1-mini 5 200
#                                 alias  модель      $/мес rpm
```
Вернётся JSON с полем `key` (`sk-...`) — это и есть virtual key проекта.

## Создать ключ — вручную через API

```bash
curl -s -X POST http://<lxc-ip>:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "key_alias": "deepseek-agent",
        "models": ["deepseek-chat"],
        "max_budget": 10,
        "budget_duration": "30d",
        "rpm_limit": 100,
        "metadata": {"tags": ["openclaw"]}
      }'
```

Или в UI: **Virtual Keys → Create New Key**.

## Как клиент использует ключ

```python
from openai import OpenAI
client = OpenAI(base_url="http://<lxc-ip>:4000/v1", api_key="sk-<virtual-key>")
client.chat.completions.create(model="gpt-4.1-mini", messages=[...])
```
Код клиента не меняется — это обычный OpenAI-совместимый вызов.

## Полезное

- Посмотреть/отозвать ключи: UI → Virtual Keys, или `GET /key/info`, `POST /key/delete`.
- Расходы по проекту: UI → Usage (фильтр по key/alias/tag), или таблица `LiteLLM_SpendLogs` в Postgres.
- Сменить бюджет/модели ключа без перевыпуска: `POST /key/update`.
