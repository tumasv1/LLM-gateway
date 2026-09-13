"""Тег user_api_key_alias для Langfuse OTEL.

langfuse_default_tags в yaml обрабатывает только legacy callback (SDK 2.x).
langfuse_otel смотрит metadata.tags. Этот хук кладёт туда
user_api_key_alias:<alias>, чтобы фильтр по клиенту остался как раньше.
"""
from litellm.integrations.custom_logger import CustomLogger


class LangfuseKeyAliasTag(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        alias = getattr(user_api_key_dict, "key_alias", None)
        if not alias or not isinstance(data, dict):
            return data
        meta = data.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            data["metadata"] = meta
        tags = meta.get("tags")
        if not isinstance(tags, list):
            tags = []
        else:
            tags = list(tags)
        tag = f"user_api_key_alias:{alias}"
        if tag not in tags:
            tags.append(tag)
        meta["tags"] = tags
        return data


proxy_handler_instance = LangfuseKeyAliasTag()
