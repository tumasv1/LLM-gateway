"""Обогащение трейсов Langfuse для langfuse_otel.

langfuse_default_tags в yaml читает только legacy callback. OTEL смотрит
metadata.tags / session_id / trace_user_id / trace_name.

Короткий тег = алиас ключа (openclaw, openwebui, ragv2), без префикса
user_api_key_alias:. Сессия и пользователь OpenWebUI — из заголовков
X-OpenWebUI-*, если клиент сам их не передал.
"""
from litellm.integrations.custom_logger import CustomLogger

# Известные алиасы ключей → короткий тег для фильтра в UI.
# Остальные просто lower().
_ALIAS_TAGS = {
    "openwebui-2": "openwebui",
    "openwebui": "openwebui",
    "ragv2": "ragv2",
    "openclaw": "openclaw",
}

_NOISE_TAG_PREFIXES = (
    "user_api_key_alias:",
    "user-agent:",
    "cache_hit:",
)

_CHAT_ID_HEADERS = ("x-openwebui-chat-id",)
_USER_EMAIL_HEADERS = ("x-openwebui-user-email",)
_USER_NAME_HEADERS = ("x-openwebui-user-name",)
_USER_ID_HEADERS = ("x-openwebui-user-id",)

# служебные таски OpenWebUI (название чата, follow-up вопросы) — отдельный тег
_OWUI_UTILITY_TASKS = {
    "title_generation",
    "follow_up_generation",
    "tags_generation",
    "emoji_generation",
    "query_generation",
    "autocomplete_generation",
    "moa_generation",
}


def client_tag(alias):
    if not alias or not isinstance(alias, str):
        return None
    key = alias.strip().lower()
    if not key:
        return None
    return _ALIAS_TAGS.get(key, key)


def _header_map(data):
    """Заголовки запроса: proxy_server_request и копия в metadata.headers."""
    found = {}
    if not isinstance(data, dict):
        return found
    sources = []
    proxy = data.get("proxy_server_request")
    if isinstance(proxy, dict) and isinstance(proxy.get("headers"), dict):
        sources.append(proxy["headers"])
    meta = data.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("headers"), dict):
        sources.append(meta["headers"])
    for headers in sources:
        for k, v in headers.items():
            if not isinstance(k, str) or v is None:
                continue
            val = v if isinstance(v, str) else str(v)
            val = val.strip()
            if val:
                found[k.lower()] = val
    return found


def _first_header(headers, names):
    for name in names:
        val = headers.get(name)
        if val:
            return val
    return None


def _clean_tags(tags, alias_tag):
    cleaned = []
    seen = set()
    for raw in tags:
        if not isinstance(raw, str):
            continue
        tag = raw.strip()
        if not tag:
            continue
        lower = tag.lower()
        if any(lower.startswith(p) for p in _NOISE_TAG_PREFIXES):
            continue
        if lower in seen:
            continue
        seen.add(lower)
        cleaned.append(tag)
    if alias_tag and alias_tag.lower() not in seen:
        cleaned.append(alias_tag)
    return cleaned


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def enrich_langfuse_metadata(data, alias):
    """Мутирует data["metadata"]. Возвращает data (или как пришло)."""
    if not isinstance(data, dict):
        return data
    meta = data.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
        data["metadata"] = meta

    tag = client_tag(alias)
    tags = meta.get("tags")
    if not isinstance(tags, list):
        tags = []
    else:
        tags = list(tags)

    task = meta.get("task")
    if isinstance(task, str) and task in _OWUI_UTILITY_TASKS:
        tags.append("utility")
        if _blank(meta.get("trace_name")):
            meta["trace_name"] = task

    meta["tags"] = _clean_tags(tags, tag)

    if tag and _blank(meta.get("trace_name")):
        meta["trace_name"] = tag

    headers = _header_map(data)
    chat_id = _first_header(headers, _CHAT_ID_HEADERS)
    if chat_id == "local":
        chat_id = None
    if chat_id and _blank(meta.get("session_id")):
        meta["session_id"] = chat_id

    user_id = (
        _first_header(headers, _USER_EMAIL_HEADERS)
        or _first_header(headers, _USER_NAME_HEADERS)
        or _first_header(headers, _USER_ID_HEADERS)
    )
    if user_id and _blank(meta.get("trace_user_id")):
        meta["trace_user_id"] = user_id

    return data


class LangfuseKeyAliasTag(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        alias = getattr(user_api_key_dict, "key_alias", None)
        return enrich_langfuse_metadata(data, alias)


proxy_handler_instance = LangfuseKeyAliasTag()
