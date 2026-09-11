"""OSS-обход: Presidio только для virtual key OpenWebUI-2.

В LiteLLM v1.100.0 metadata.guardrails / Policies на ключе — Enterprise:
при запросе срабатывает _premium_user_check() → HTTP 403.
Клиентский body `guardrails: [...]` — OSS. Этот хук подставляет имя
UI-guardrail'а в metadata запроса, если алиас ключа OpenWebUI-2.
Сама политика (default_on=выкл, без restore) живёт в UI, не здесь.
"""
from litellm.integrations.custom_logger import CustomLogger

GUARDRAIL_NAME = "presidio-pii"
KEY_ALIAS = "OpenWebUI-2"


class OpenWebUIPresidioAttach(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        alias = getattr(user_api_key_dict, "key_alias", None)
        if alias != KEY_ALIAS:
            return data
        if not isinstance(data, dict):
            return data
        # OSS-путь: requested guardrails в metadata / корне запроса
        meta = data.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            data["metadata"] = meta
        rails = meta.get("guardrails")
        if not isinstance(rails, list):
            rails = []
        if GUARDRAIL_NAME not in rails:
            rails = list(rails) + [GUARDRAIL_NAME]
        meta["guardrails"] = rails
        data["guardrails"] = rails
        return data


proxy_handler_instance = OpenWebUIPresidioAttach()
