import asyncio
import sys
import types
import unittest
from pathlib import Path

# хук импортирует litellm — в юнит-тестах его нет, подставляем заглушку
_litellm = types.ModuleType("litellm")
_integrations = types.ModuleType("litellm.integrations")
_custom = types.ModuleType("litellm.integrations.custom_logger")


class CustomLogger:
    pass


_custom.CustomLogger = CustomLogger
sys.modules.setdefault("litellm", _litellm)
sys.modules.setdefault("litellm.integrations", _integrations)
sys.modules.setdefault("litellm.integrations.custom_logger", _custom)

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))

from langfuse_key_alias_tag import (  # noqa: E402
    LangfuseKeyAliasTag,
    client_tag,
    enrich_langfuse_metadata,
)


class _Key:
    def __init__(self, alias):
        self.key_alias = alias


class ClientTagTests(unittest.TestCase):
    def test_known_aliases(self):
        self.assertEqual(client_tag("OpenWebUI-2"), "openwebui")
        self.assertEqual(client_tag("Ragv2"), "ragv2")
        self.assertEqual(client_tag("OpenClaw"), "openclaw")

    def test_unknown_lowercased(self):
        self.assertEqual(client_tag("n8n"), "n8n")
        self.assertEqual(client_tag("Speech2Text"), "speech2text")

    def test_empty(self):
        self.assertIsNone(client_tag(None))
        self.assertIsNone(client_tag("  "))


class EnrichTests(unittest.TestCase):
    def test_short_tag_and_trace_name(self):
        data = enrich_langfuse_metadata({}, "OpenClaw")
        self.assertEqual(data["metadata"]["tags"], ["openclaw"])
        self.assertEqual(data["metadata"]["trace_name"], "openclaw")

    def test_strips_noisy_tags_keeps_utility(self):
        data = {
            "metadata": {
                "tags": [
                    "user_api_key_alias:Ragv2",
                    "User-Agent: OpenAI",
                    "cache_hit:None",
                    "utility",
                ],
                "trace_name": "generate_title",
            }
        }
        enrich_langfuse_metadata(data, "Ragv2")
        self.assertEqual(data["metadata"]["tags"], ["utility", "ragv2"])
        self.assertEqual(data["metadata"]["trace_name"], "generate_title")

    def test_openwebui_headers_to_session_and_user(self):
        data = {
            "proxy_server_request": {
                "headers": {
                    "X-OpenWebUI-Chat-Id": "chat-abc-123",
                    "X-OpenWebUI-User-Email": "misha@example.com",
                    "X-OpenWebUI-User-Name": "Misha",
                }
            }
        }
        enrich_langfuse_metadata(data, "OpenWebUI-2")
        meta = data["metadata"]
        self.assertEqual(meta["tags"], ["openwebui"])
        self.assertEqual(meta["session_id"], "chat-abc-123")
        self.assertEqual(meta["trace_user_id"], "misha@example.com")
        self.assertEqual(meta["trace_name"], "openwebui")

    def test_does_not_overwrite_client_session_or_user(self):
        data = {
            "metadata": {
                "session_id": "already-set",
                "trace_user_id": "client-user",
            },
            "metadata_headers_unused": True,
            "proxy_server_request": {
                "headers": {
                    "x-openwebui-chat-id": "chat-new",
                    "x-openwebui-user-email": "other@example.com",
                }
            },
        }
        enrich_langfuse_metadata(data, "OpenWebUI-2")
        self.assertEqual(data["metadata"]["session_id"], "already-set")
        self.assertEqual(data["metadata"]["trace_user_id"], "client-user")

    def test_ignores_temporary_local_chat_id(self):
        data = {
            "proxy_server_request": {
                "headers": {"X-OpenWebUI-Chat-Id": "local"}
            }
        }
        enrich_langfuse_metadata(data, "OpenWebUI-2")
        self.assertNotIn("session_id", data["metadata"])

    def test_user_name_fallback(self):
        data = {
            "metadata": {
                "headers": {"X-OpenWebUI-User-Name": "Misha"}
            }
        }
        enrich_langfuse_metadata(data, "OpenWebUI-2")
        self.assertEqual(data["metadata"]["trace_user_id"], "Misha")

    def test_no_alias_still_maps_headers(self):
        data = {
            "proxy_server_request": {
                "headers": {
                    "x-openwebui-chat-id": "chat-1",
                    "x-openwebui-user-id": "uid-9",
                }
            }
        }
        enrich_langfuse_metadata(data, None)
        self.assertEqual(data["metadata"]["session_id"], "chat-1")
        self.assertEqual(data["metadata"]["trace_user_id"], "uid-9")
        self.assertEqual(data["metadata"]["tags"], [])

    def test_openwebui_utility_task_tag(self):
        data = {"metadata": {"task": "title_generation"}}
        enrich_langfuse_metadata(data, "OpenWebUI-2")
        self.assertIn("utility", data["metadata"]["tags"])
        self.assertIn("openwebui", data["metadata"]["tags"])
        self.assertEqual(data["metadata"]["trace_name"], "title_generation")

    def test_hook_async(self):
        hook = LangfuseKeyAliasTag()
        data = asyncio.run(
            hook.async_pre_call_hook(_Key("n8n"), None, {}, "completion")
        )
        self.assertEqual(data["metadata"]["tags"], ["n8n"])
        self.assertEqual(data["metadata"]["trace_name"], "n8n")


if __name__ == "__main__":
    unittest.main()
