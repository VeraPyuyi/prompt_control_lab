"""DeepSeek thinking is explicit, provider-scoped, and preserved through live-call routing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from promptcontrollab.evaluation.experiments import create_experiment, run_experiment
from promptcontrollab.evaluation.experiments.models import model_config
from promptcontrollab.integrations.providers import ProviderError, _build_request, _provider_spec


@pytest.mark.parametrize("thinking", [None, "enabled", "disabled"])
def test_deepseek_thinking_reaches_http_payload_without_rewriting_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, thinking: str | None
) -> None:
    monkeypatch.setenv("WHEEL_DEEPSEEK_TEST_KEY", "synthetic-contract-key")
    requests: list[dict[str, Any]] = []

    def transport(request: Request, timeout: float) -> tuple[bytes, dict[str, str]]:
        assert isinstance(request.data, bytes)
        requests.append(json.loads(request.data))
        return json.dumps(
            {
                "model": "deepseek-v4-flash",
                "choices": [{"message": {"content": "yes"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }
        ).encode(), {}

    monkeypatch.setattr("promptcontrollab.integrations.providers._perform_request", transport)
    config: dict[str, Any] = {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "prompt": "Answer yes.",
        "api_key_env": "WHEEL_DEEPSEEK_TEST_KEY",
        "max_output_tokens": 8,
    }
    if thinking is not None:
        config["thinking"] = thinking
    spec = {
        "schema_version": "experiment/v1",
        "operation": "run",
        "synthetic": True,
        "data": [{"id": "a", "input": "a", "expected": "yes"}],
        "baseline": config,
        "candidate": {**config, "prompt": "Return yes."},
        "metric": "exact_match",
        "budget": {"max_calls": 2, "max_output_tokens": 16, "max_seconds": 30},
    }
    result = run_experiment(tmp_path, create_experiment(tmp_path, spec)["id"])
    assert result["status"] == "completed"
    assert len(requests) == 2
    for payload in requests:
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["max_tokens"] == 8
        if thinking is None:
            assert "thinking" not in payload
        else:
            assert payload["thinking"] == {"type": thinking}


@pytest.mark.parametrize(
    "provider", ["openai", "anthropic", "gemini", "qwen", "kimi", "openai-compatible"]
)
def test_thinking_rejects_other_providers_before_transport(provider: str) -> None:
    with pytest.raises(ValueError, match="only for DeepSeek"):
        model_config(
            {"provider": provider, "model": "test", "prompt": "hi", "thinking": "disabled"},
            "baseline",
        )
    with pytest.raises(ProviderError, match="only for DeepSeek"):
        _build_request(
            _provider_spec(provider),
            model="test",
            prompt="hi",
            base_url="https://example.test",
            api_key="synthetic",
            max_output_tokens=8,
            thinking="disabled",
        )


@pytest.mark.parametrize("thinking", [None, True, 1, "auto", "DISABLED", {}, []])
def test_model_config_rejects_non_enum_thinking(thinking: object) -> None:
    with pytest.raises(ValueError, match="enabled or disabled"):
        model_config(
            {"provider": "deepseek", "model": "test", "prompt": "hi", "thinking": thinking},
            "baseline",
        )
