"""Не слать в Langfuse пустые дочерние спаны guardrail / raw_gen_ai_request.

langfuse_otel на каждый LLM-вызов рисует ещё:
- guardrail (Presidio) — часто два раза, pre_call и post/during;
- raw_gen_ai_request — дубль провайдерского запроса без I/O и без тегов.

Это не второй вызов модели. Патч глушит только эти спаны, generation остаётся.
"""
from litellm.integrations.custom_logger import CustomLogger


def _noop(self, *args, **kwargs):
    return None


def _install():
    try:
        from litellm.integrations.opentelemetry import OpenTelemetry
    except Exception:
        return
    OpenTelemetry._create_guardrail_span = _noop
    OpenTelemetry._maybe_log_raw_request = _noop
    if hasattr(OpenTelemetry, "_emit_guardrail_spans_from_request_data"):
        OpenTelemetry._emit_guardrail_spans_from_request_data = _noop


_install()


class LangfuseOtelQuiet(CustomLogger):
    pass


proxy_handler_instance = LangfuseOtelQuiet()
