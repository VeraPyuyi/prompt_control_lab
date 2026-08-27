"""Model identity and provenance helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import cast

from promptcontrollab.core.files import JsonDict, read_json, read_jsonl


@dataclass(frozen=True)
class ModelIdentity:
    """Public model identity recorded by an API response or prediction file."""

    provider: str
    model_id: str
    source: str
    confidence: str
    api_version: str | None = None
    created: int | None = None
    owned_by: str | None = None
    verified: bool | None = None
    request_id: str | None = None
    request_sha256: str | None = None
    response_sha256: str | None = None
    provider_log_reference: str | None = None
    signed_receipt: str | None = None
    provenance_level: str = "level_0_declared_by_user"
    provenance_evidence: list[JsonDict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> JsonDict:
        """Serialize the model identity and its provenance evidence."""

        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "source": self.source,
            "confidence": self.confidence,
            "api_version": self.api_version,
            "created": self.created,
            "owned_by": self.owned_by,
            "verified": self.verified,
            "request_id": self.request_id,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
            "provider_log_reference": self.provider_log_reference,
            "signed_receipt": self.signed_receipt,
            "provenance_level": self.provenance_level,
            "provenance_evidence": self.provenance_evidence,
            "warnings": self.warnings,
        }


def detect_model_identity(
    *,
    provider: str | None = None,
    model_id: str | None = None,
    response_path: Path | None = None,
    predictions_path: Path | None = None,
    api_version: str | None = None,
    verify: bool = False,
    request_id: str | None = None,
    request_path: Path | None = None,
    request_sha256: str | None = None,
    response_sha256: str | None = None,
    provider_log_reference: str | None = None,
    signed_receipt: str | None = None,
) -> ModelIdentity:
    """Detect public model identity from explicit input, response JSON, or predictions JSONL."""

    sources = sum(value is not None for value in [model_id, response_path, predictions_path])
    if sources == 0:
        identity = unknown_identity(provider=provider, api_version=api_version)
    elif model_id is not None:
        identity = from_declared_model(
            model_id=model_id,
            provider=provider,
            api_version=api_version,
            source="argument.model",
        )
    elif response_path is not None:
        identity = from_response_file(response_path, provider=provider, api_version=api_version)
    elif predictions_path is not None:
        identity = from_predictions_file(
            predictions_path,
            provider=provider,
            api_version=api_version,
        )
    else:
        identity = unknown_identity(provider=provider, api_version=api_version)

    identity = _with_request_evidence(
        identity,
        request_id=request_id,
        request_sha256=request_sha256 or _hash_file_optional(request_path),
        response_sha256=response_sha256
        or (_hash_file_optional(response_path) if response_path is not None else None),
        provider_log_reference=provider_log_reference,
        signed_receipt=signed_receipt,
    )

    if verify:
        identity = verify_identity(identity)
    return _with_provenance(identity)


def unknown_identity(
    *,
    provider: str | None = None,
    api_version: str | None = None,
) -> ModelIdentity:
    """Create an explicit unknown identity when no public model ID is available."""

    return ModelIdentity(
        provider=provider or "unknown",
        model_id="unknown",
        source="missing",
        confidence="low",
        api_version=api_version,
        verified=False,
        provenance_level="level_0_declared_by_user",
        provenance_evidence=[{"type": "missing_model", "source": "missing"}],
        warnings=["No model id was found. Reproducibility is weaker without model provenance."],
    )


def from_declared_model(
    *,
    model_id: str,
    provider: str | None = None,
    api_version: str | None = None,
    source: str,
) -> ModelIdentity:
    """Create model provenance from a caller-declared public model ID."""

    return ModelIdentity(
        provider=provider or infer_provider(model_id),
        model_id=model_id,
        source=source,
        confidence="high",
        api_version=api_version,
        provenance_level="level_0_declared_by_user",
        provenance_evidence=[{"type": "declared_model", "source": source}],
        warnings=_alias_warnings(model_id),
    )


def from_response_file(
    path: Path,
    *,
    provider: str | None = None,
    api_version: str | None = None,
) -> ModelIdentity:
    """Extract an observed public model ID from a response JSON file.

    This records what the response declares and does not prove the provider's
    hidden weight build.
    """

    payload = read_json(path)
    found = _find_model_field(payload)
    if found is None:
        return unknown_identity(provider=provider, api_version=api_version)
    source, model_id = found
    detected_api_version = api_version or _find_api_version(payload)
    identity = from_declared_model(
        model_id=model_id,
        provider=provider or _find_provider(payload) or infer_provider(model_id),
        api_version=detected_api_version,
        source=f"response.{source}",
    )
    return ModelIdentity(
        provider=identity.provider,
        model_id=identity.model_id,
        source=identity.source,
        confidence=identity.confidence,
        api_version=identity.api_version,
        created=identity.created,
        owned_by=identity.owned_by,
        verified=identity.verified,
        provenance_level="level_1_observed_in_response",
        provenance_evidence=[
            {"type": "observed_model_field", "source": identity.source},
        ],
        warnings=identity.warnings,
    )


def from_predictions_file(
    path: Path,
    *,
    provider: str | None = None,
    api_version: str | None = None,
) -> ModelIdentity:
    """Summarize observed model provenance across prediction records.

    Mixed model IDs are retained as an explicit reproducibility warning rather
    than collapsed into a single identity.
    """

    records = read_jsonl(path)
    model_ids: set[str] = set()
    providers: set[str] = set()
    api_versions: set[str] = set()
    for record in records:
        payload = model_payload_from_prediction(record)
        raw_model = payload.get("model_id")
        raw_provider = payload.get("provider")
        raw_api_version = payload.get("api_version")
        if isinstance(raw_model, str) and raw_model:
            model_ids.add(raw_model)
        if isinstance(raw_provider, str) and raw_provider:
            providers.add(raw_provider)
        if isinstance(raw_api_version, str) and raw_api_version:
            api_versions.add(raw_api_version)

    warnings: list[str] = []
    if not model_ids:
        return unknown_identity(provider=provider, api_version=api_version)
    if len(model_ids) > 1:
        warnings.append(
            "Multiple model ids were found in the prediction file; "
            "prompt-only comparison is not clean."
        )
        return ModelIdentity(
            provider=provider or _one_or_unknown(providers),
            model_id="mixed",
            source="predictions.model",
            confidence="low",
            api_version=api_version or _one_or_none(api_versions),
            verified=False,
            provenance_level="level_1_observed_in_response",
            provenance_evidence=[
                {"type": "observed_prediction_model", "source": "predictions.model"}
            ],
            warnings=warnings,
        )

    model_id = next(iter(model_ids))
    detected_provider = provider or _one_or_none(providers) or infer_provider(model_id)
    detected_api_version = api_version or _one_or_none(api_versions)
    return ModelIdentity(
        provider=detected_provider,
        model_id=model_id,
        source="predictions.model",
        confidence="medium",
        api_version=detected_api_version,
        provenance_level="level_1_observed_in_response",
        provenance_evidence=[{"type": "observed_prediction_model", "source": "predictions.model"}],
        warnings=[*_alias_warnings(model_id), *warnings],
    )


def model_payload_from_prediction(record: JsonDict) -> JsonDict:
    """Extract model metadata from one raw prediction record."""

    payload: JsonDict = {}
    top_model = record.get("model")
    top_provider = record.get("provider")
    top_api_version = record.get("api_version")
    if isinstance(top_model, str):
        payload["model_id"] = top_model
    if isinstance(top_provider, str):
        payload["provider"] = top_provider
    if isinstance(top_api_version, str):
        payload["api_version"] = top_api_version

    meta = record.get("meta")
    if isinstance(meta, dict):
        meta_model = meta.get("model")
        meta_provider = meta.get("provider")
        meta_api_version = meta.get("api_version")
        if "model_id" not in payload and isinstance(meta_model, str):
            payload["model_id"] = meta_model
        if "provider" not in payload and isinstance(meta_provider, str):
            payload["provider"] = meta_provider
        if "api_version" not in payload and isinstance(meta_api_version, str):
            payload["api_version"] = meta_api_version

    response = record.get("response")
    if "model_id" not in payload and isinstance(response, dict):
        found = _find_model_field(cast(JsonDict, response))
        if found is not None:
            payload["model_id"] = found[1]
    return payload


def verify_identity(identity: ModelIdentity) -> ModelIdentity:
    """Verify public model metadata when a provider exposes a dependency-free endpoint."""

    if identity.model_id in {"unknown", "mixed"}:
        return _with_warning(
            identity,
            "Cannot verify an unknown or mixed model id.",
            verified=False,
        )
    provider = identity.provider.lower()
    if provider == "openai":
        return _verify_openai(identity)
    return _with_warning(
        identity,
        f"Online verification is not implemented for provider `{identity.provider}`.",
        verified=False,
    )


def compare_model_identities(
    baseline: JsonDict | None,
    candidate: JsonDict | None,
) -> list[str]:
    """Return warnings for model-provenance issues in a paired comparison."""

    warnings: list[str] = []
    baseline_id = _json_str(baseline or {}, "model_id")
    candidate_id = _json_str(candidate or {}, "model_id")
    baseline_provider = _json_str(baseline or {}, "provider")
    candidate_provider = _json_str(candidate or {}, "provider")
    if baseline_id in {"", "unknown"} or candidate_id in {"", "unknown"}:
        warnings.append("One side is missing model identity; reproducibility is weaker.")
    if baseline_id and candidate_id and baseline_id != candidate_id:
        warnings.append(
            "Baseline and candidate used different model ids; "
            "this is not a clean prompt-only comparison."
        )
    if baseline_provider and candidate_provider and baseline_provider != candidate_provider:
        warnings.append(
            "Baseline and candidate used different providers; "
            "compare results as model+prompt changes."
        )
    return warnings


def infer_provider(model_id: str) -> str:
    """Infer a provider from a small set of recognizable public model prefixes."""

    lowered = model_id.lower()
    if lowered.startswith("gpt-") or lowered.startswith("o1") or lowered.startswith("o3"):
        return "openai"
    if lowered.startswith("claude-"):
        return "anthropic"
    return "unknown"


def is_alias_model(model_id: str) -> bool:
    """Return whether a model id is likely an alias rather than a pinned dated id."""

    return model_id.endswith("-latest") or model_id in {"gpt-4o", "gpt-5.2"}


def _verify_openai(identity: ModelIdentity) -> ModelIdentity:
    """Verify that OpenAI exposes a matching public model metadata object.

    Notes:
        A successful lookup verifies the public model object only. It cannot
        establish the provider's hidden internal weight revision.
    """

    import json
    import os
    import urllib.error
    import urllib.request

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _with_warning(
            identity,
            "OPENAI_API_KEY is not set, so OpenAI model metadata was not verified.",
            verified=False,
        )
    request = urllib.request.Request(
        f"https://api.openai.com/v1/models/{identity.model_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        return _with_warning(
            identity,
            f"OpenAI model metadata verification failed: {exc}",
            verified=False,
        )
    return ModelIdentity(
        provider=identity.provider,
        model_id=str(payload.get("id", identity.model_id)),
        source=identity.source,
        confidence=identity.confidence,
        api_version=identity.api_version,
        created=payload.get("created") if isinstance(payload.get("created"), int) else None,
        owned_by=payload.get("owned_by") if isinstance(payload.get("owned_by"), str) else None,
        verified=True,
        request_id=identity.request_id,
        request_sha256=identity.request_sha256,
        response_sha256=identity.response_sha256,
        provider_log_reference=identity.provider_log_reference,
        signed_receipt=identity.signed_receipt,
        provenance_level="level_2_provider_metadata_verified",
        provenance_evidence=[
            *identity.provenance_evidence,
            {"type": "provider_metadata", "source": "openai.models.retrieve"},
        ],
        warnings=[
            *identity.warnings,
            "Verification confirms the public model object, not the hidden internal weight build.",
        ],
    )


def _find_model_field(payload: JsonDict) -> tuple[str, str] | None:
    for key in ("model", "model_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return key, value
    for key, value in payload.items():
        if isinstance(value, dict):
            found = _find_model_field(cast(JsonDict, value))
            if found is not None:
                source, model_id = found
                return f"{key}.{source}", model_id
    return None


def _find_api_version(payload: JsonDict) -> str | None:
    for key in ("api_version", "openai_version", "anthropic_version", "anthropic-version"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    meta = payload.get("meta")
    if isinstance(meta, dict):
        return _find_api_version(cast(JsonDict, meta))
    return None


def _find_provider(payload: JsonDict) -> str | None:
    provider = payload.get("provider")
    if isinstance(provider, str) and provider:
        return provider
    meta = payload.get("meta")
    if isinstance(meta, dict):
        return _find_provider(cast(JsonDict, meta))
    return None


def _with_warning(identity: ModelIdentity, warning: str, *, verified: bool) -> ModelIdentity:
    return ModelIdentity(
        provider=identity.provider,
        model_id=identity.model_id,
        source=identity.source,
        confidence=identity.confidence,
        api_version=identity.api_version,
        created=identity.created,
        owned_by=identity.owned_by,
        verified=verified,
        request_id=identity.request_id,
        request_sha256=identity.request_sha256,
        response_sha256=identity.response_sha256,
        provider_log_reference=identity.provider_log_reference,
        signed_receipt=identity.signed_receipt,
        provenance_level=identity.provenance_level,
        provenance_evidence=identity.provenance_evidence,
        warnings=[*identity.warnings, warning],
    )


def _with_request_evidence(
    identity: ModelIdentity,
    *,
    request_id: str | None,
    request_sha256: str | None,
    response_sha256: str | None,
    provider_log_reference: str | None,
    signed_receipt: str | None,
) -> ModelIdentity:
    return ModelIdentity(
        provider=identity.provider,
        model_id=identity.model_id,
        source=identity.source,
        confidence=identity.confidence,
        api_version=identity.api_version,
        created=identity.created,
        owned_by=identity.owned_by,
        verified=identity.verified,
        request_id=request_id,
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        provider_log_reference=provider_log_reference,
        signed_receipt=signed_receipt,
        provenance_level=identity.provenance_level,
        provenance_evidence=identity.provenance_evidence,
        warnings=identity.warnings,
    )


def _with_provenance(identity: ModelIdentity) -> ModelIdentity:
    evidence = list(identity.provenance_evidence)
    if identity.request_id:
        evidence.append({"type": "request_id", "value": identity.request_id})
    if identity.request_sha256:
        evidence.append({"type": "request_sha256", "value": identity.request_sha256})
    if identity.response_sha256:
        evidence.append({"type": "response_sha256", "value": identity.response_sha256})
    level = identity.provenance_level
    if identity.verified is True:
        level = "level_2_provider_metadata_verified"
    if identity.provider_log_reference:
        evidence.append(
            {"type": "provider_log_reference", "value": identity.provider_log_reference}
        )
        level = "level_3_provider_log_reference_recorded"
    if identity.signed_receipt:
        evidence.append({"type": "signed_receipt_reference", "value": identity.signed_receipt})
        level = "level_4_signed_receipt_recorded"
    return ModelIdentity(
        provider=identity.provider,
        model_id=identity.model_id,
        source=identity.source,
        confidence=identity.confidence,
        api_version=identity.api_version,
        created=identity.created,
        owned_by=identity.owned_by,
        verified=identity.verified,
        request_id=identity.request_id,
        request_sha256=identity.request_sha256,
        response_sha256=identity.response_sha256,
        provider_log_reference=identity.provider_log_reference,
        signed_receipt=identity.signed_receipt,
        provenance_level=level,
        provenance_evidence=evidence,
        warnings=identity.warnings,
    )


def _hash_file_optional(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _alias_warnings(model_id: str) -> list[str]:
    if is_alias_model(model_id):
        return [
            "Model aliases can change over time. "
            "Pin a dated model id when strict reproduction matters."
        ]
    return []


def _one_or_none(values: set[str]) -> str | None:
    if len(values) == 1:
        return next(iter(values))
    return None


def _one_or_unknown(values: set[str]) -> str:
    return _one_or_none(values) or "unknown"


def _json_str(payload: JsonDict, key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""
