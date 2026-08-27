"""Dependency-free provider adapters with normalized provenance metadata.

The adapters intentionally expose the public model identifier reported by an
API response. They do not claim to identify an unpublished weight build.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import NoReturn, cast

from promptcontrollab.core.errors import PromptControlLabError
from promptcontrollab.core.files import JsonDict


class ProviderError(PromptControlLabError):
    """A provider is misconfigured or returned an unusable response."""


@dataclass(frozen=True)
class ProviderSpec:
    """Stable metadata needed to configure one provider adapter."""

    provider_id: str
    display_name: str
    protocol: str
    api_key_env: str
    base_url_env: str
    default_base_url: str | None
    docs_url: str

    def to_json(self) -> JsonDict:
        """Serialize public provider configuration without credential values."""

        return {
            "id": self.provider_id,
            "display_name": self.display_name,
            "protocol": self.protocol,
            "api_key_env": self.api_key_env,
            "base_url_env": self.base_url_env,
            "default_base_url": self.default_base_url,
            "docs_url": self.docs_url,
            "model_required": True,
        }


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized, persistence-safe result of one provider call."""

    provider: str
    model_id: str
    output_text: str
    request_id: str | None
    usage: JsonDict
    latency_ms: float
    request_sha256: str
    response_sha256: str
    provenance_evidence: list[JsonDict]
    raw_metadata: JsonDict
    warnings: list[str]

    def __post_init__(self) -> None:
        self.to_json()

    def to_json(self) -> JsonDict:
        """Serialize a normalized provider response after finite-value validation."""

        payload: JsonDict = {
            "provider": self.provider,
            "model_id": self.model_id,
            "output_text": self.output_text,
            "request_id": self.request_id,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
            "provenance_evidence": self.provenance_evidence,
            "raw_metadata": self.raw_metadata,
            "warnings": self.warnings,
        }
        _require_finite_json_numbers(payload)
        return payload


_PROVIDERS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        provider_id="openai",
        display_name="OpenAI",
        protocol="openai-chat-completions",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        default_base_url="https://api.openai.com/v1",
        docs_url="https://platform.openai.com/docs/api-reference/chat",
    ),
    "anthropic": ProviderSpec(
        provider_id="anthropic",
        display_name="Anthropic",
        protocol="anthropic-messages",
        api_key_env="ANTHROPIC_API_KEY",
        base_url_env="ANTHROPIC_BASE_URL",
        default_base_url="https://api.anthropic.com",
        docs_url="https://docs.anthropic.com/en/api/messages",
    ),
    "gemini": ProviderSpec(
        provider_id="gemini",
        display_name="Google Gemini",
        protocol="gemini-generate-content",
        api_key_env="GEMINI_API_KEY",
        base_url_env="GEMINI_BASE_URL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        docs_url="https://ai.google.dev/api/generate-content",
    ),
    "deepseek": ProviderSpec(
        provider_id="deepseek",
        display_name="DeepSeek",
        protocol="openai-chat-completions",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        default_base_url="https://api.deepseek.com",
        docs_url="https://api-docs.deepseek.com/api/create-chat-completion",
    ),
    "qwen": ProviderSpec(
        provider_id="qwen",
        display_name="Qwen / DashScope",
        protocol="openai-chat-completions",
        api_key_env="DASHSCOPE_API_KEY",
        base_url_env="DASHSCOPE_BASE_URL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        docs_url="https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
    ),
    "kimi": ProviderSpec(
        provider_id="kimi",
        display_name="Kimi / Moonshot",
        protocol="openai-chat-completions",
        api_key_env="MOONSHOT_API_KEY",
        base_url_env="MOONSHOT_BASE_URL",
        # Kimi deployments may use region- or product-specific gateways. Requiring an
        # explicit URL prevents this adapter from silently choosing the wrong service.
        default_base_url=None,
        docs_url="https://platform.moonshot.cn/docs/api/chat",
    ),
    "openai-compatible": ProviderSpec(
        provider_id="openai-compatible",
        display_name="OpenAI-compatible endpoint",
        protocol="openai-chat-completions",
        api_key_env="OPENAI_COMPATIBLE_API_KEY",
        base_url_env="OPENAI_COMPATIBLE_BASE_URL",
        default_base_url=None,
        docs_url="https://platform.openai.com/docs/api-reference/chat",
    ),
}

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
_MAX_RESPONSE_LABEL = "10 MiB"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_GEMINI_SUCCESS_FINISH_REASONS = {"STOP", "MAX_TOKENS"}
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:authorization|api[-_ ]?key|access[-_ ]?token|auth[-_ ]?token|"
    r"secret|credential)\s*[:=]\s*(?:bearer\s+)?[\"']?"
    r"[A-Za-z0-9][A-Za-z0-9._~+/=-]{7,}[\"']?"
)
_BEARER_SECRET_RE = re.compile(
    r"(?i)\bbearer\s+[A-Za-z0-9][A-Za-z0-9._~+/=-]{7,}"
)
_KNOWN_SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"sk[-_][A-Za-z0-9][A-Za-z0-9._-]{14,}|"
    r"AIza[0-9A-Za-z_-]{20,}|"
    r"github_pat_[0-9A-Za-z_]{20,}|"
    r"gh[pousr]_[0-9A-Za-z]{20,}|"
    r"xox[baprs]-[0-9A-Za-z-]{10,}|"
    r"(?:AKIA|ASIA)[0-9A-Z]{16}|"
    r"eyJ[0-9A-Za-z_-]{8,}\.[0-9A-Za-z_-]{8,}\.[0-9A-Za-z_-]{8,}"
    r")(?![A-Za-z0-9])"
)


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so authorization headers never reach another URL."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        """Reject every redirect to keep authorization headers on the original host."""

        return None


def list_providers() -> list[JsonDict]:
    """Return provider metadata in stable public order, without credentials."""

    return [spec.to_json() for spec in _PROVIDERS.values()]


def inspect_provider(
    provider: str,
    *,
    base_url: str | None = None,
    api_key_env: str | None = None,
) -> JsonDict:
    """Inspect local provider configuration without making a network call."""

    spec = _provider_spec(provider)
    key_env = _key_env(spec, api_key_env)
    resolved_base = _resolve_base_url(spec, base_url, required=False)
    key_present = bool(os.environ.get(key_env))
    warnings: list[str] = []
    if not key_present:
        warnings.append(f"Environment variable {key_env} is not set.")
    if resolved_base is None:
        warnings.append(
            f"No base URL is configured. Set {spec.base_url_env} or pass base_url explicitly."
        )
    return {
        **spec.to_json(),
        "api_key_env": key_env,
        "base_url": resolved_base,
        "api_key_present": key_present,
        "configured": key_present and resolved_base is not None,
        "warnings": warnings,
    }


def doctor_provider(
    provider: str,
    *,
    live: bool = False,
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
    timeout: float = 10.0,
) -> JsonDict:
    """Validate provider configuration; perform a tiny call only when requested."""

    inspected = inspect_provider(provider, base_url=base_url, api_key_env=api_key_env)
    result: JsonDict = {
        **inspected,
        "status": "ready" if inspected["configured"] else "error",
        "live_checked": False,
    }
    if not live:
        return result
    if not model or not model.strip():
        raise ProviderError("A live provider doctor check requires an explicit model id.")
    if not inspected["configured"]:
        warnings = inspected.get("warnings")
        detail = "; ".join(str(item) for item in warnings) if isinstance(warnings, list) else ""
        raise ProviderError(f"Provider '{provider}' is not configured. {detail}".strip())
    response = call_provider(
        provider=provider,
        model=model,
        prompt="Reply with exactly OK.",
        base_url=base_url,
        timeout=timeout,
        max_output_tokens=4,
        api_key_env=api_key_env,
    )
    result.update(
        {
            "status": "ok",
            "live_checked": True,
            "observed_model_id": response.model_id,
            "request_id": response.request_id,
            "latency_ms": response.latency_ms,
            "provenance_evidence": response.provenance_evidence,
        }
    )
    return result


def call_provider(
    *,
    provider: str,
    model: str,
    prompt: str,
    base_url: str | None = None,
    timeout: float = 30.0,
    max_output_tokens: int = 256,
    api_key_env: str | None = None,
) -> ProviderResponse:
    """Call a supported provider and return a normalized, redacted response."""

    spec = _provider_spec(provider)
    model_id = model.strip()
    if not model_id:
        raise ProviderError("An explicit model id is required; no default model is selected.")
    if timeout <= 0:
        raise ProviderError("timeout must be greater than zero.")
    if max_output_tokens <= 0:
        raise ProviderError("max_output_tokens must be greater than zero.")
    key_env = _key_env(spec, api_key_env)
    api_key = os.environ.get(key_env)
    if not api_key:
        raise ProviderError(
            f"Provider '{spec.provider_id}' requires API credentials in {key_env}."
        )
    resolved_base = _resolve_base_url(spec, base_url, required=True)
    assert resolved_base is not None
    request, request_payload = _build_request(
        spec,
        model=model_id,
        prompt=prompt,
        base_url=resolved_base,
        api_key=api_key,
        max_output_tokens=max_output_tokens,
    )
    request_bytes = _stable_json_bytes(request_payload)
    request_digest = _digest(request_bytes)
    started = time.perf_counter()
    try:
        response_bytes, response_headers = _perform_request(request, timeout)
    except urllib.error.HTTPError as exc:
        reason = _redact_error_text(str(exc.reason), api_key)
        raise ProviderError(
            f"Provider '{spec.provider_id}' request failed with HTTP {exc.code}: {reason}."
        ) from None
    except urllib.error.URLError as exc:
        reason = _redact_error_text(str(exc.reason), api_key)
        raise ProviderError(
            f"Provider '{spec.provider_id}' could not reach its configured endpoint: {reason}."
        ) from None
    except (TimeoutError, OSError) as exc:
        reason = _redact_error_text(str(exc), api_key)
        raise ProviderError(
            f"Provider '{spec.provider_id}' request failed: {reason}."
        ) from None
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    try:
        decoded = json.loads(
            response_bytes.decode("utf-8"),
            parse_constant=_reject_non_standard_json_constant,
        )
    except UnicodeDecodeError:
        raise ProviderError(
            f"Provider '{spec.provider_id}' returned invalid JSON: invalid UTF-8."
        ) from None
    except json.JSONDecodeError as exc:
        raise ProviderError(
            f"Provider '{spec.provider_id}' returned invalid JSON: {exc.msg}."
        ) from None
    except ValueError as exc:
        raise ProviderError(
            f"Provider '{spec.provider_id}' returned invalid JSON: {exc}."
        ) from None
    if not isinstance(decoded, dict):
        raise ProviderError(f"Provider '{spec.provider_id}' returned a non-object JSON response.")
    _require_finite_json_numbers(decoded)
    payload = cast(JsonDict, decoded)
    _raise_for_error_envelope(spec, payload, api_key=api_key)
    return _normalize_response(
        spec,
        requested_model=model_id,
        payload=payload,
        headers=response_headers,
        api_key=api_key,
        latency_ms=latency_ms,
        request_sha256=request_digest,
        response_sha256=_digest(response_bytes),
    )


def _provider_spec(provider: str) -> ProviderSpec:
    provider_id = provider.strip().lower()
    try:
        return _PROVIDERS[provider_id]
    except KeyError:
        supported = ", ".join(_PROVIDERS)
        raise ProviderError(
            f"Unknown provider '{provider}'. Supported providers: {supported}."
        ) from None


def _key_env(spec: ProviderSpec, override: str | None) -> str:
    value = override or spec.api_key_env
    if not _ENV_NAME_RE.fullmatch(value):
        raise ProviderError("api_key_env must be an environment-variable name, not a credential.")
    return value


def _resolve_base_url(
    spec: ProviderSpec,
    explicit: str | None,
    *,
    required: bool,
) -> str | None:
    raw = explicit or os.environ.get(spec.base_url_env) or spec.default_base_url
    if raw is None or not raw.strip():
        if required:
            raise ProviderError(
                f"Provider '{spec.provider_id}' requires a base URL. "
                f"Set {spec.base_url_env} or pass base_url explicitly."
            )
        return None
    value = raw.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProviderError(
            f"Provider '{spec.provider_id}' base URL must be an absolute HTTP(S) URL."
        )
    if parsed.scheme == "http" and parsed.hostname.lower() not in _LOOPBACK_HOSTS:
        raise ProviderError(
            "Remote provider endpoints must use HTTPS. Plain HTTP is allowed only for "
            "local loopback endpoints (localhost, 127.0.0.1, or ::1)."
        )
    if parsed.username is not None or parsed.password is not None:
        raise ProviderError("Provider base URLs must not contain embedded credentials.")
    if parsed.query or parsed.fragment:
        raise ProviderError("Provider base URLs must not contain a query string or fragment.")
    return value


def _build_request(
    spec: ProviderSpec,
    *,
    model: str,
    prompt: str,
    base_url: str,
    api_key: str,
    max_output_tokens: int,
) -> tuple[urllib.request.Request, JsonDict]:
    """Build a provider-specific HTTPS request and its hashable payload."""

    if spec.protocol == "anthropic-messages":
        endpoint = f"{base_url}/v1/messages"
        payload: JsonDict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "Anthropic-Version": "2023-06-01",
        }
    elif spec.protocol == "gemini-generate-content":
        normalized_model = model.removeprefix("models/")
        encoded_model = urllib.parse.quote(normalized_model, safe="-._")
        endpoint = f"{base_url}/models/{encoded_model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
        }
    else:
        endpoint = f"{base_url}/chat/completions"
        limit_key = "max_completion_tokens" if spec.provider_id == "openai" else "max_tokens"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            limit_key: max_output_tokens,
        }
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    request = urllib.request.Request(
        endpoint,
        data=_stable_json_bytes(payload),
        headers=headers,
        method="POST",
    )
    return request, payload


def _perform_request(
    request: urllib.request.Request,
    timeout: float,
) -> tuple[bytes, Mapping[str, str]]:
    opener = urllib.request.build_opener(_RejectRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = -1
            if declared_size > _MAX_RESPONSE_BYTES:
                raise ProviderError(
                    f"Provider response exceeds the {_MAX_RESPONSE_LABEL} safety limit."
                )
        body = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ProviderError(
                f"Provider response exceeds the {_MAX_RESPONSE_LABEL} safety limit."
            )
        return body, dict(response.headers.items())


def _normalize_response(
    spec: ProviderSpec,
    *,
    requested_model: str,
    payload: JsonDict,
    headers: Mapping[str, str],
    api_key: str,
    latency_ms: float,
    request_sha256: str,
    response_sha256: str,
) -> ProviderResponse:
    """Normalize one provider payload into the persistence-safe response schema."""

    _validate_usable_response(spec, payload)
    if spec.protocol == "anthropic-messages":
        output = _anthropic_output(payload)
        usage = _anthropic_usage(payload)
        metadata = _anthropic_metadata(payload)
        response_model = _string(payload.get("model"))
    elif spec.protocol == "gemini-generate-content":
        output = _gemini_output(payload)
        usage = _gemini_usage(payload)
        metadata = _gemini_metadata(payload)
        response_model = _string(payload.get("modelVersion"))
    else:
        output = _openai_output(payload)
        usage = _openai_usage(payload)
        metadata = _openai_metadata(payload)
        response_model = _string(payload.get("model"))

    if not output.strip():
        raise ProviderError(f"Provider '{spec.provider_id}' returned an empty output.")

    warnings: list[str] = []
    if response_model:
        model_id = response_model
        evidence = [
            {
                "type": "observed_model_field",
                "source": (
                    "response.modelVersion"
                    if spec.protocol == "gemini-generate-content"
                    else "response.model"
                ),
            }
        ]
    else:
        model_id = requested_model
        evidence = [{"type": "declared_model", "source": "request.model"}]
        warnings.append(
            "The response did not report a public model id; the requested model id was recorded."
        )
    request_id = _request_id(headers, payload)
    return ProviderResponse(
        provider=spec.provider_id,
        model_id=_redact_persisted_text(model_id, api_key),
        output_text=_redact_persisted_text(output, api_key),
        request_id=(
            _redact_persisted_text(request_id, api_key) if request_id is not None else None
        ),
        usage=_redact_json_dict(usage, api_key),
        latency_ms=latency_ms,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        provenance_evidence=[_redact_json_dict(item, api_key) for item in evidence],
        raw_metadata=_redact_json_dict(metadata, api_key),
        warnings=[_redact_persisted_text(warning, api_key) for warning in warnings],
    )


def _raise_for_error_envelope(
    spec: ProviderSpec,
    payload: JsonDict,
    *,
    api_key: str,
) -> None:
    error = payload.get("error")
    if error is None and payload.get("type") != "error":
        return
    detail = "provider reported an unspecified error"
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            detail = message.strip()
    elif isinstance(error, str) and error.strip():
        detail = error.strip()
    raise ProviderError(
        f"Provider '{spec.provider_id}' returned an error response: "
        f"{_redact_error_text(detail, api_key)}."
    )


def _validate_usable_response(spec: ProviderSpec, payload: JsonDict) -> None:
    """Reject provider payloads that represent refusal, blocking, or empty output."""

    if spec.protocol == "anthropic-messages":
        stop_reason = _string(payload.get("stop_reason"))
        if stop_reason and stop_reason.lower() in {"refusal", "safety", "content_filter"}:
            raise ProviderError(f"Provider '{spec.provider_id}' refused or blocked the response.")
        content = payload.get("content")
        if isinstance(content, list) and any(
            isinstance(item, dict) and item.get("type") == "refusal" for item in content
        ):
            raise ProviderError(f"Provider '{spec.provider_id}' refused or blocked the response.")
        return

    if spec.protocol == "gemini-generate-content":
        prompt_feedback = payload.get("promptFeedback")
        if isinstance(prompt_feedback, dict):
            block_reason = _string(prompt_feedback.get("blockReason"))
            if block_reason and block_reason != "BLOCK_REASON_UNSPECIFIED":
                raise ProviderError(
                    f"Provider '{spec.provider_id}' refused or blocked the response."
                )
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates or not isinstance(
            candidates[0], dict
        ):
            raise ProviderError(
                f"Provider '{spec.provider_id}' returned a missing candidate response."
            )
        finish_reason = _string(candidates[0].get("finishReason"))
        normalized_reason = finish_reason.upper() if finish_reason else None
        if normalized_reason and normalized_reason not in _GEMINI_SUCCESS_FINISH_REASONS:
            raise ProviderError(
                f"Provider '{spec.provider_id}' returned an unusable response "
                f"(finish reason: {normalized_reason}); it may have been refused or blocked."
            )
        return

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError(
            f"Provider '{spec.provider_id}' returned a missing candidate or choice response."
        )
    choice = choices[0]
    finish_reason = _string(choice.get("finish_reason"))
    message = choice.get("message")
    refusal = message.get("refusal") if isinstance(message, dict) else None
    if (isinstance(refusal, str) and refusal.strip()) or finish_reason in {
        "content_filter",
        "refusal",
        "safety",
    }:
        raise ProviderError(f"Provider '{spec.provider_id}' refused or blocked the response.")


def _openai_output(payload: JsonDict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    return _public_text(message.get("content"))


def _anthropic_output(payload: JsonDict) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _gemini_output(payload: JsonDict) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return ""
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    text_parts: list[str] = []
    for part in parts:
        if not isinstance(part, dict) or part.get("thought") is True:
            continue
        text = part.get("text")
        if isinstance(text, str):
            text_parts.append(text)
    return "".join(text_parts)


def _public_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type not in {None, "text", "output_text"}:
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _openai_usage(payload: JsonDict) -> JsonDict:
    usage = payload.get("usage")
    source = cast(JsonDict, usage) if isinstance(usage, dict) else {}
    return _normalized_usage(
        source.get("prompt_tokens", source.get("input_tokens")),
        source.get("completion_tokens", source.get("output_tokens")),
        source.get("total_tokens"),
    )


def _anthropic_usage(payload: JsonDict) -> JsonDict:
    usage = payload.get("usage")
    source = cast(JsonDict, usage) if isinstance(usage, dict) else {}
    return _normalized_usage(source.get("input_tokens"), source.get("output_tokens"), None)


def _gemini_usage(payload: JsonDict) -> JsonDict:
    usage = payload.get("usageMetadata")
    source = cast(JsonDict, usage) if isinstance(usage, dict) else {}
    return _normalized_usage(
        source.get("promptTokenCount"),
        source.get("candidatesTokenCount"),
        source.get("totalTokenCount"),
    )


def _normalized_usage(input_value: object, output_value: object, total_value: object) -> JsonDict:
    input_tokens = input_value if isinstance(input_value, int) else None
    output_tokens = output_value if isinstance(output_value, int) else None
    total_tokens = total_value if isinstance(total_value, int) else None
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _openai_metadata(payload: JsonDict) -> JsonDict:
    metadata = _copy_scalars(payload, ("id", "object", "created", "system_fingerprint"))
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")
        if isinstance(finish_reason, str):
            metadata["finish_reason"] = finish_reason
    return metadata


def _anthropic_metadata(payload: JsonDict) -> JsonDict:
    return _copy_scalars(
        payload,
        ("id", "type", "role", "stop_reason", "stop_sequence"),
    )


def _gemini_metadata(payload: JsonDict) -> JsonDict:
    metadata = _copy_scalars(payload, ("responseId", "modelVersion"))
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        finish_reason = candidates[0].get("finishReason")
        if isinstance(finish_reason, str):
            metadata["finish_reason"] = finish_reason
    prompt_feedback = payload.get("promptFeedback")
    if isinstance(prompt_feedback, dict):
        block_reason = prompt_feedback.get("blockReason")
        if isinstance(block_reason, str):
            metadata["block_reason"] = block_reason
    return metadata


def _copy_scalars(payload: JsonDict, keys: tuple[str, ...]) -> JsonDict:
    result: JsonDict = {}
    for key in keys:
        value = payload.get(key)
        if key in payload and (isinstance(value, (str, int, float, bool)) or value is None):
            result[key] = value
    return result


def _request_id(headers: Mapping[str, str], payload: JsonDict) -> str | None:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    for key in ("x-request-id", "request-id", "x-goog-request-id"):
        if lowered.get(key):
            return lowered[key]
    for key in ("responseId", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _stable_json_bytes(payload: JsonDict) -> bytes:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(payload: bytes) -> str:
    return f"sha256:{sha256(payload).hexdigest()}"


def _reject_non_standard_json_constant(value: str) -> NoReturn:
    raise ValueError(f"non-standard numeric constant {value}")


def _require_finite_json_numbers(value: object) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProviderError("Provider response must contain only finite JSON numbers.")
        return
    if isinstance(value, list):
        for item in value:
            _require_finite_json_numbers(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            _require_finite_json_numbers(item)


def _redact_json_dict(value: JsonDict, api_key: str) -> JsonDict:
    return {key: _redact_json_value(item, api_key) for key, item in value.items()}


def _redact_json_value(value: object, api_key: str) -> object:
    if isinstance(value, str):
        return _redact_persisted_text(value, api_key)
    if isinstance(value, list):
        return [_redact_json_value(item, api_key) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _redact_json_value(item, api_key)
            for key, item in value.items()
        }
    return value


def _redact_persisted_text(value: str, api_key: str) -> str:
    redacted = value.replace(api_key, "[redacted]")
    redacted = _SECRET_ASSIGNMENT_RE.sub("[redacted]", redacted)
    redacted = _BEARER_SECRET_RE.sub("[redacted]", redacted)
    return _KNOWN_SECRET_RE.sub("[redacted]", redacted)


def _redact_error_text(value: str, api_key: str) -> str:
    redacted = _redact_persisted_text(value, api_key)
    return redacted[:240] or "request failed"


__all__ = [
    "ProviderError",
    "ProviderResponse",
    "ProviderSpec",
    "call_provider",
    "doctor_provider",
    "inspect_provider",
    "list_providers",
]
