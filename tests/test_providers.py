from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from email.message import Message
from typing import Any, cast
from urllib.error import HTTPError
from urllib.request import Request

import pytest

import promptcontrollab.integrations.providers as providers_module
from promptcontrollab.integrations.providers import (
    ProviderError,
    ProviderResponse,
    call_provider,
    doctor_provider,
    inspect_provider,
    list_providers,
)


def _json_response(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _capture_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: dict[str, Any],
    headers: Mapping[str, str] | None = None,
) -> list[tuple[Request, float]]:
    calls: list[tuple[Request, float]] = []

    def fake_transport(request: Request, timeout: float) -> tuple[bytes, Mapping[str, str]]:
        calls.append((request, timeout))
        return _json_response(payload), headers or {}

    monkeypatch.setattr("promptcontrollab.integrations.providers._perform_request", fake_transport)
    return calls


def _request_json(request: Request) -> dict[str, Any]:
    assert request.data is not None
    value = json.loads(cast(bytes, request.data).decode("utf-8"))
    assert isinstance(value, dict)
    return value


def _headers(request: Request) -> dict[str, str]:
    return {key.lower(): value for key, value in request.header_items()}


class _FakeResponse:
    def __init__(self, body: bytes, *, content_length: int | None = None) -> None:
        self.body = body
        self.headers = Message()
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.read_sizes: list[int] = []

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return self.body if size < 0 else self.body[:size]


class _FakeOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[Request, float]] = []

    def open(self, request: Request, timeout: float) -> _FakeResponse:
        self.calls.append((request, timeout))
        return self.response


def test_provider_registry_has_all_canonical_providers_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-private-value")

    providers = list_providers()

    assert [item["id"] for item in providers] == [
        "openai",
        "anthropic",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
        "openai-compatible",
    ]
    assert "sk-private-value" not in json.dumps(providers)
    assert all("default_model" not in item for item in providers)


def test_inspect_provider_reports_configuration_without_returning_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://proxy.example.test/deepseek")

    result = inspect_provider("deepseek")

    assert result["configured"] is True
    assert result["api_key_env"] == "DEEPSEEK_API_KEY"
    assert result["base_url"] == "https://proxy.example.test/deepseek"
    assert result["model_required"] is True
    assert "deepseek-secret" not in json.dumps(result)


def test_kimi_requires_explicit_or_environment_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOONSHOT_API_KEY", "secret")
    monkeypatch.delenv("MOONSHOT_BASE_URL", raising=False)

    result = inspect_provider("kimi")

    assert result["configured"] is False
    assert any("MOONSHOT_BASE_URL" in warning for warning in result["warnings"])


@pytest.mark.parametrize(
    ("provider", "key_env", "base_env", "default_base", "response_model"),
    [
        ("openai", "OPENAI_API_KEY", "OPENAI_BASE_URL", "https://api.openai.com/v1", "gpt-test"),
        (
            "deepseek",
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_BASE_URL",
            "https://api.deepseek.com",
            "deepseek-test",
        ),
        (
            "qwen",
            "DASHSCOPE_API_KEY",
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen-test",
        ),
    ],
)
def test_openai_compatible_provider_request_and_normalization(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    key_env: str,
    base_env: str,
    default_base: str,
    response_model: str,
) -> None:
    monkeypatch.setenv(key_env, "private-key")
    monkeypatch.delenv(base_env, raising=False)
    calls = _capture_transport(
        monkeypatch,
        payload={
            "id": "completion-1",
            "model": response_model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "A useful answer",
                        "reasoning_content": "must not persist",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
            "system_fingerprint": "public-fingerprint",
        },
        headers={"x-request-id": "request-header-id"},
    )

    result = call_provider(
        provider=provider,
        model=f"{provider}-requested",
        prompt="Hello",
        timeout=12.5,
        max_output_tokens=77,
    )

    request, timeout = calls[0]
    assert request.full_url == f"{default_base}/chat/completions"
    assert timeout == 12.5
    assert _headers(request)["authorization"] == "Bearer private-key"
    expected_limit_key = "max_completion_tokens" if provider == "openai" else "max_tokens"
    assert _request_json(request) == {
        "model": f"{provider}-requested",
        "messages": [{"role": "user", "content": "Hello"}],
        expected_limit_key: 77,
    }
    assert result.provider == provider
    assert result.model_id == response_model
    assert result.output_text == "A useful answer"
    assert result.request_id == "request-header-id"
    assert result.usage == {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13}
    assert result.request_sha256.startswith("sha256:")
    assert result.response_sha256.startswith("sha256:")
    assert result.provenance_evidence[0]["type"] == "observed_model_field"
    serialized = json.dumps(result.to_json())
    assert "private-key" not in serialized
    assert "must not persist" not in serialized
    assert result.raw_metadata["finish_reason"] == "stop"


def test_successful_response_redacts_credentials_from_persisted_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "configured-provider-secret-123456"
    other_secret = "sk-proj-secondary-secret-value-987654"
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    _capture_transport(
        monkeypatch,
        payload={
            "id": f"response:{other_secret}",
            "object": f"Bearer {other_secret}",
            "model": f"model:{api_key}",
            "system_fingerprint": f"fingerprint:{api_key}",
            "choices": [{"message": {"content": "safe output"}, "finish_reason": "stop"}],
        },
        headers={"x-request-id": f"request:{api_key}:{other_secret}"},
    )

    result = call_provider(provider="openai", model="gpt-test", prompt="Hello")

    persisted_context = {
        "model_id": result.model_id,
        "request_id": result.request_id,
        "provenance_evidence": result.provenance_evidence,
        "raw_metadata": result.raw_metadata,
        "warnings": result.warnings,
    }
    serialized = json.dumps(persisted_context, sort_keys=True)
    assert api_key not in serialized
    assert other_secret not in serialized
    assert "[redacted]" in serialized
    assert result.output_text == "safe output"


def test_openai_compatible_output_redacts_exact_configured_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "local-provider-key-123456"
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", api_key)
    _capture_transport(
        monkeypatch,
        payload={
            "model": "local-model-v1",
            "choices": [
                {"message": {"content": f"Keep this prefix; echoed={api_key}; keep this suffix."}}
            ],
        },
    )

    result = call_provider(
        provider="openai-compatible",
        model="local-model-v1",
        prompt="Hello",
        base_url="http://127.0.0.1:9000/v1",
    )

    assert result.output_text == "Keep this prefix; echoed=[redacted]; keep this suffix."
    assert api_key not in json.dumps(result.to_json())


def test_anthropic_output_redacts_exact_configured_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key = "anthropic-provider-key-123456"
    monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    _capture_transport(
        monkeypatch,
        payload={
            "model": "claude-test",
            "content": [
                {"type": "text", "text": "Keep this prefix; "},
                {"type": "text", "text": f"echoed={api_key}; keep this suffix."},
            ],
            "stop_reason": "end_turn",
        },
    )

    result = call_provider(provider="anthropic", model="claude-test", prompt="Hello")

    assert result.output_text == "Keep this prefix; echoed=[redacted]; keep this suffix."
    assert api_key not in json.dumps(result.to_json())


def test_successful_response_preserves_benign_public_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "configured-provider-secret-123456")
    _capture_transport(
        monkeypatch,
        payload={
            "id": "chatcmpl-keyframe-tokenizer-20260823",
            "model": "key-value-tokenizer-v2.1",
            "system_fingerprint": "fp_keyframe-tokenizer_v2",
            "choices": [{"message": {"content": "safe output"}, "finish_reason": "stop"}],
        },
        headers={"x-request-id": "req_keyframe-tokenizer_20260823"},
    )

    result = call_provider(provider="openai", model="gpt-test", prompt="Hello")

    assert result.model_id == "key-value-tokenizer-v2.1"
    assert result.request_id == "req_keyframe-tokenizer_20260823"
    assert result.raw_metadata["id"] == "chatcmpl-keyframe-tokenizer-20260823"
    assert result.raw_metadata["system_fingerprint"] == "fp_keyframe-tokenizer_v2"


def test_kimi_openai_compatible_request_requires_configured_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-secret")
    calls = _capture_transport(
        monkeypatch,
        payload={
            "model": "moonshot-test",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )

    result = call_provider(
        provider="kimi",
        model="moonshot-test",
        prompt="Hello",
        base_url="https://moonshot.example.test/v1",
    )

    assert calls[0][0].full_url == "https://moonshot.example.test/v1/chat/completions"
    assert result.provider == "kimi"


def test_anthropic_request_and_response_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    calls = _capture_transport(
        monkeypatch,
        payload={
            "id": "msg_1",
            "model": "claude-test-20260823",
            "content": [
                {"type": "thinking", "thinking": "must not persist"},
                {"type": "text", "text": "Anthropic answer"},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 6, "output_tokens": 3},
        },
        headers={"request-id": "anthropic-request"},
    )

    result = call_provider(
        provider="anthropic",
        model="claude-test-20260823",
        prompt="Hello",
        max_output_tokens=55,
    )

    request = calls[0][0]
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert _headers(request)["x-api-key"] == "anthropic-secret"
    assert _headers(request)["anthropic-version"] == "2023-06-01"
    assert _request_json(request) == {
        "model": "claude-test-20260823",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 55,
    }
    assert result.output_text == "Anthropic answer"
    assert result.request_id == "anthropic-request"
    assert result.usage == {"input_tokens": 6, "output_tokens": 3, "total_tokens": 9}
    assert "must not persist" not in json.dumps(result.to_json())


def test_gemini_request_and_response_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    calls = _capture_transport(
        monkeypatch,
        payload={
            "modelVersion": "gemini-test-001",
            "responseId": "gemini-request",
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "Gemini answer"},
                            {"thought": True, "text": "must not persist"},
                        ],
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 2,
                "totalTokenCount": 7,
                "thoughtsTokenCount": 99,
            },
        },
    )

    result = call_provider(
        provider="gemini",
        model="models/gemini-test",
        prompt="Hello",
        max_output_tokens=44,
    )

    request = calls[0][0]
    assert request.full_url == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-test:generateContent"
    )
    assert _headers(request)["x-goog-api-key"] == "gemini-secret"
    assert _request_json(request) == {
        "contents": [{"role": "user", "parts": [{"text": "Hello"}]}],
        "generationConfig": {"maxOutputTokens": 44},
    }
    assert result.output_text == "Gemini answer"
    assert result.model_id == "gemini-test-001"
    assert result.request_id == "gemini-request"
    assert result.usage == {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    assert "must not persist" not in json.dumps(result.to_json())
    assert "thoughtsTokenCount" not in json.dumps(result.to_json())


@pytest.mark.parametrize(
    "finish_reason",
    [
        "FINISH_REASON_UNSPECIFIED",
        "SAFETY",
        "RECITATION",
        "LANGUAGE",
        "OTHER",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "MALFORMED_FUNCTION_CALL",
        "IMAGE_SAFETY",
        "IMAGE_PROHIBITED_CONTENT",
        "IMAGE_OTHER",
        "NO_IMAGE",
        "IMAGE_RECITATION",
        "UNEXPECTED_TOOL_CALL",
        "TOO_MANY_TOOL_CALLS",
        "MISSING_THOUGHT_SIGNATURE",
        "MALFORMED_RESPONSE",
        "ESCALATION",
    ],
)
def test_gemini_rejects_non_success_finish_reasons_even_with_partial_text(
    monkeypatch: pytest.MonkeyPatch,
    finish_reason: str,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    _capture_transport(
        monkeypatch,
        payload={
            "modelVersion": "gemini-test",
            "candidates": [
                {
                    "content": {"parts": [{"text": "partial output must not be accepted"}]},
                    "finishReason": finish_reason,
                }
            ],
        },
    )

    with pytest.raises(ProviderError, match=finish_reason):
        call_provider(provider="gemini", model="gemini-test", prompt="Hello")


@pytest.mark.parametrize("finish_reason", ["STOP", "MAX_TOKENS"])
def test_gemini_accepts_documented_text_success_finish_reasons(
    monkeypatch: pytest.MonkeyPatch,
    finish_reason: str,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    _capture_transport(
        monkeypatch,
        payload={
            "modelVersion": "gemini-test",
            "candidates": [
                {
                    "content": {"parts": [{"text": "usable output"}]},
                    "finishReason": finish_reason,
                }
            ],
        },
    )

    result = call_provider(provider="gemini", model="gemini-test", prompt="Hello")

    assert result.output_text == "usable output"
    assert result.raw_metadata["finish_reason"] == finish_reason


def test_generic_openai_compatible_uses_configurable_env_and_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCAL_LLM_TOKEN", "generic-secret")
    calls = _capture_transport(
        monkeypatch,
        payload={
            "model": "local-model-v1",
            "choices": [{"message": {"content": "local answer"}}],
            "usage": {},
        },
    )

    result = call_provider(
        provider="openai-compatible",
        model="local-model-v1",
        prompt="Hello",
        base_url="http://127.0.0.1:9000/v1",
        api_key_env="LOCAL_LLM_TOKEN",
    )

    assert calls[0][0].full_url == "http://127.0.0.1:9000/v1/chat/completions"
    assert _headers(calls[0][0])["authorization"] == "Bearer generic-secret"
    assert result.output_text == "local answer"
    assert "generic-secret" not in json.dumps(result.to_json())


def test_generic_openai_compatible_can_use_explicit_environment_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://gateway.example.test/v1")
    calls = _capture_transport(
        monkeypatch,
        payload={"model": "model-a", "choices": [{"message": {"content": "ok"}}]},
    )

    call_provider(provider="openai-compatible", model="model-a", prompt="Hello")

    assert calls[0][0].full_url == "https://gateway.example.test/v1/chat/completions"


def test_doctor_is_offline_by_default_and_requires_explicit_model_for_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    def unexpected_transport(request: Request, timeout: float) -> tuple[bytes, Mapping[str, str]]:
        raise AssertionError("offline doctor must not call the network")

    monkeypatch.setattr(
        "promptcontrollab.integrations.providers._perform_request",
        unexpected_transport,
    )

    offline = doctor_provider("openai")
    assert offline["status"] == "ready"
    assert offline["live_checked"] is False

    with pytest.raises(ProviderError, match="explicit model id"):
        doctor_provider("openai", live=True)


def test_doctor_live_call_is_tiny_and_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    calls = _capture_transport(
        monkeypatch,
        payload={"model": "gpt-test", "choices": [{"message": {"content": "OK"}}]},
    )

    result = doctor_provider("openai", live=True, model="gpt-test", timeout=3.0)

    assert result["status"] == "ok"
    assert result["live_checked"] is True
    assert _request_json(calls[0][0])["max_completion_tokens"] == 4


def test_missing_key_and_unknown_provider_errors_are_clear_and_secret_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        call_provider(provider="openai", model="gpt-test", prompt="Hello")
    with pytest.raises(ProviderError, match="Unknown provider"):
        inspect_provider("not-real")


def test_http_errors_are_clear_without_exposing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "top-secret-key")

    def failed_transport(request: Request, timeout: float) -> tuple[bytes, Mapping[str, str]]:
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized top-secret-key",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr(
        "promptcontrollab.integrations.providers._perform_request",
        failed_transport,
    )

    with pytest.raises(ProviderError) as caught:
        call_provider(provider="openai", model="gpt-test", prompt="Hello")

    message = str(caught.value)
    assert "openai" in message
    assert "401" in message
    assert "top-secret-key" not in message


def test_invalid_model_base_url_and_response_fail_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    with pytest.raises(ProviderError, match="model id"):
        call_provider(provider="openai", model="", prompt="Hello")
    with pytest.raises(ProviderError, match="credentials"):
        call_provider(
            provider="openai",
            model="gpt-test",
            prompt="Hello",
            base_url="https://user:pass@example.test/v1",
        )

    def invalid_json(request: Request, timeout: float) -> tuple[bytes, Mapping[str, str]]:
        return b"not-json", {}

    monkeypatch.setattr("promptcontrollab.integrations.providers._perform_request", invalid_json)
    with pytest.raises(ProviderError, match="invalid JSON"):
        call_provider(provider="openai", model="gpt-test", prompt="Hello")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_standard_json_constants_are_rejected_during_decode(
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    response_bytes = (
        '{"model":"gpt-test","created":'
        f'{constant},"choices":[{{"message":{{"content":"ok"}}}}]}}'
    ).encode()

    def constant_response(
        request: Request,
        timeout: float,
    ) -> tuple[bytes, Mapping[str, str]]:
        return response_bytes, {}

    monkeypatch.setattr(
        "promptcontrollab.integrations.providers._perform_request",
        constant_response,
    )

    with pytest.raises(ProviderError, match="invalid JSON") as caught:
        call_provider(provider="openai", model="gpt-test", prompt="Hello")

    assert "non-standard numeric constant" in str(caught.value)
    assert constant in str(caught.value)


def test_overflowed_json_number_is_rejected_as_non_finite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    def overflow_response(
        request: Request,
        timeout: float,
    ) -> tuple[bytes, Mapping[str, str]]:
        return (
            b'{"model":"gpt-test","created":1e400,'
            b'"choices":[{"message":{"content":"ok"}}]}',
            {},
        )

    monkeypatch.setattr(
        "promptcontrollab.integrations.providers._perform_request",
        overflow_response,
    )

    with pytest.raises(ProviderError, match="finite JSON numbers"):
        call_provider(provider="openai", model="gpt-test", prompt="Hello")


@pytest.mark.parametrize(
    ("latency_ms", "usage", "raw_metadata"),
    [
        (float("nan"), {}, {}),
        (1.0, {"input_tokens": float("inf")}, {}),
        (1.0, {}, {"nested": {"score": float("-inf")}}),
    ],
    ids=["latency-nan", "usage-infinity", "metadata-negative-infinity"],
)
def test_provider_response_rejects_non_finite_normalized_numbers(
    latency_ms: float,
    usage: dict[str, Any],
    raw_metadata: dict[str, Any],
) -> None:
    with pytest.raises(ProviderError, match="finite JSON numbers"):
        ProviderResponse(
            provider="openai",
            model_id="gpt-test",
            output_text="ok",
            request_id="request-1",
            usage=usage,
            latency_ms=latency_ms,
            request_sha256="sha256:request",
            response_sha256="sha256:response",
            provenance_evidence=[{"type": "observed_model_field", "confidence": 1.0}],
            raw_metadata=raw_metadata,
            warnings=[],
        )


def test_provider_response_json_is_strictly_serializable_with_finite_numbers() -> None:
    response = ProviderResponse(
        provider="openai",
        model_id="gpt-test",
        output_text="ok",
        request_id="request-1",
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        latency_ms=1.25,
        request_sha256="sha256:request",
        response_sha256="sha256:response",
        provenance_evidence=[{"type": "observed_model_field", "confidence": 0.5}],
        raw_metadata={"created": 1.5},
        warnings=[],
    )

    encoded = json.dumps(response.to_json(), allow_nan=False, sort_keys=True)

    assert '"latency_ms": 1.25' in encoded


def test_response_without_model_records_declared_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    _capture_transport(
        monkeypatch,
        payload={"id": "response-1", "choices": [{"message": {"content": "ok"}}]},
    )

    result = call_provider(provider="openai", model="gpt-requested", prompt="Hello")

    assert result.model_id == "gpt-requested"
    assert result.provenance_evidence[0]["type"] == "declared_model"
    assert result.warnings


@pytest.mark.parametrize(
    "base_url",
    [
        "http://provider.example.test/v1",
        "http://192.168.1.20:8080/v1",
        "http://10.0.0.2/v1",
    ],
)
def test_plain_http_is_rejected_for_non_loopback_hosts(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "secret")

    with pytest.raises(ProviderError, match="HTTPS"):
        call_provider(
            provider="openai-compatible",
            model="local-model",
            prompt="Hello",
            base_url=base_url,
        )


@pytest.mark.parametrize(
    "base_url",
    ["http://localhost:9000/v1", "http://127.0.0.1:9000/v1", "http://[::1]:9000/v1"],
)
def test_plain_http_is_allowed_only_for_loopback_hosts(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "secret")
    calls = _capture_transport(
        monkeypatch,
        payload={"model": "local-model", "choices": [{"message": {"content": "ok"}}]},
    )

    call_provider(
        provider="openai-compatible",
        model="local-model",
        prompt="Hello",
        base_url=base_url,
    )

    assert calls[0][0].full_url.endswith("/chat/completions")


def test_transport_installs_redirect_rejecting_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _FakeResponse(b"{}", content_length=2)
    opener = _FakeOpener(response)
    installed_handlers: list[object] = []

    def fake_build_opener(*handlers: object) -> _FakeOpener:
        installed_handlers.extend(handlers)
        return opener

    monkeypatch.setattr(
        "promptcontrollab.integrations.providers.urllib.request.build_opener",
        fake_build_opener,
    )
    request = Request(
        "https://provider.example.test/v1/chat/completions",
        headers={"Authorization": "Bearer private"},
    )

    providers_module._perform_request(request, 2.0)

    assert any(
        isinstance(handler, providers_module._RejectRedirectHandler)
        for handler in installed_handlers
    )
    redirect_handler = next(
        handler
        for handler in installed_handlers
        if isinstance(handler, providers_module._RejectRedirectHandler)
    )
    redirect_call = cast(Callable[..., object | None], redirect_handler.redirect_request)
    assert redirect_call() is None


def test_transport_rejects_declared_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(b"{}", content_length=providers_module._MAX_RESPONSE_BYTES + 1)
    opener = _FakeOpener(response)
    monkeypatch.setattr(
        "promptcontrollab.integrations.providers.urllib.request.build_opener",
        lambda *handlers: opener,
    )

    with pytest.raises(ProviderError, match="10 MiB"):
        providers_module._perform_request(Request("https://example.test"), 2.0)

    assert response.read_sizes == []


def test_transport_uses_bounded_read_and_rejects_undeclared_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(b"x" * (providers_module._MAX_RESPONSE_BYTES + 1))
    opener = _FakeOpener(response)
    monkeypatch.setattr(
        "promptcontrollab.integrations.providers.urllib.request.build_opener",
        lambda *handlers: opener,
    )

    with pytest.raises(ProviderError, match="10 MiB"):
        providers_module._perform_request(Request("https://example.test"), 2.0)

    assert response.read_sizes == [providers_module._MAX_RESPONSE_BYTES + 1]


@pytest.mark.parametrize(
    ("provider", "key_env", "payload"),
    [
        ("openai", "OPENAI_API_KEY", {"error": {"message": "request rejected"}}),
        (
            "anthropic",
            "ANTHROPIC_API_KEY",
            {"type": "error", "error": {"message": "request rejected"}},
        ),
        ("gemini", "GEMINI_API_KEY", {"error": {"message": "request rejected"}}),
    ],
)
def test_http_200_error_envelopes_raise_provider_error(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    key_env: str,
    payload: dict[str, Any],
) -> None:
    monkeypatch.setenv(key_env, "secret")
    _capture_transport(monkeypatch, payload=payload)

    with pytest.raises(ProviderError, match="error response"):
        call_provider(provider=provider, model="test-model", prompt="Hello")


def test_error_envelope_does_not_expose_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-highly-private")
    _capture_transport(
        monkeypatch,
        payload={"error": {"message": "invalid sk-highly-private credential"}},
    )

    with pytest.raises(ProviderError) as caught:
        call_provider(provider="openai", model="gpt-test", prompt="Hello")

    assert "sk-highly-private" not in str(caught.value)


@pytest.mark.parametrize(
    ("provider", "key_env", "payload", "message"),
    [
        (
            "openai",
            "OPENAI_API_KEY",
            {
                "model": "gpt-test",
                "choices": [
                    {
                        "message": {"content": "", "refusal": "policy refusal"},
                        "finish_reason": "content_filter",
                    }
                ],
            },
            "refused or blocked",
        ),
        (
            "anthropic",
            "ANTHROPIC_API_KEY",
            {"model": "claude-test", "content": [], "stop_reason": "refusal"},
            "refused or blocked",
        ),
        (
            "gemini",
            "GEMINI_API_KEY",
            {"promptFeedback": {"blockReason": "SAFETY"}},
            "refused or blocked",
        ),
        (
            "gemini",
            "GEMINI_API_KEY",
            {"modelVersion": "gemini-test", "candidates": []},
            "missing candidate",
        ),
        (
            "openai",
            "OPENAI_API_KEY",
            {"model": "gpt-test", "choices": [{"message": {"content": ""}}]},
            "empty output",
        ),
    ],
)
def test_http_200_unusable_responses_raise_provider_error(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    key_env: str,
    payload: dict[str, Any],
    message: str,
) -> None:
    monkeypatch.setenv(key_env, "secret")
    _capture_transport(monkeypatch, payload=payload)

    with pytest.raises(ProviderError, match=message):
        call_provider(provider=provider, model="test-model", prompt="Hello")


def test_live_doctor_does_not_report_ok_for_empty_http_200_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    _capture_transport(
        monkeypatch,
        payload={"model": "gpt-test", "choices": [{"message": {"content": ""}}]},
    )

    with pytest.raises(ProviderError, match="empty output"):
        doctor_provider("openai", live=True, model="gpt-test")
