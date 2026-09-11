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

## Маскирование ПДн на одном ключе (OSS)

В LiteLLM v1.100.0 **Policies и `metadata.guardrails` на ключе — Enterprise**.
Если записать `"guardrails": ["presidio-pii"]` в metadata ключа, **чат падает с 403**
(`_premium_user_check` при запросе). `default_on: true` маскировал бы все ключи — не наш случай.

Рабочий OSS-способ:

1. UI → **Guardrails → Add Guardrail → Presidio PII**. Имя `presidio-pii`.
   Analyzer `http://presidio-analyzer:3000`, Anonymizer `http://presidio-anonymizer:3000`.
   Mode `pre_call`. **Default On = выкл.** `output_parse_pii` не включать.
   Сущности → MASK: EMAIL_ADDRESS, PHONE_NUMBER, PERSON,
   **INN_RU, SNILS_RU, PASSPORT_RF** (шаг 2: без них LiteLLM не попросит
   Analyzer искать кастомные типы). PERSON закрывает ФИО (отчество или контекст
   «фио/зовут/фамилия»). ИНН/СНИЛС — только с контрольной суммой.
2. **Не** вешать guardrail на ключ в UI/API. Хук `hooks/openwebui_presidio.py`
   (подключён в `litellm_settings.callbacks`) подставляет `guardrails: ["presidio-pii"]`
   в запрос, только если `key_alias == OpenWebUI-2`. Это тот же OSS-путь, что
   «передать guardrails в body», без участия клиента.
3. После правки хука или `callbacks` — `docker compose restart litellm`.

Опционально в OpenWebUI: Connections → LiteLLM → `passthrough_params.guardrails = ["presidio-pii"]`
(дубль на стороне клиента; шлюз и так маскирует по алиасу ключа).

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
