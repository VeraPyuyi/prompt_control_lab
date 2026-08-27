"""Context extraction for prompt improvement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json


@dataclass(frozen=True)
class PromptContext:
    """Small set of improvement hints extracted from run artifacts."""

    regressed_slices: list[str]
    broken_ids: list[str]
    deployment_notes: list[str]

    def to_json(self) -> JsonDict:
        return {
            "regressed_slices": self.regressed_slices,
            "broken_ids": self.broken_ids,
            "deployment_notes": self.deployment_notes,
        }


def empty_prompt_context() -> PromptContext:
    """Return an empty context."""

    return PromptContext(regressed_slices=[], broken_ids=[], deployment_notes=[])


def load_prompt_context(run_dir: Path | None) -> PromptContext:
    """Load prompt improvement hints from a run directory when available."""

    if run_dir is None:
        return empty_prompt_context()
    explanation_path = run_dir / "explanation.json"
    if not explanation_path.exists():
        return empty_prompt_context()
    explanation = read_json(explanation_path)
    return PromptContext(
        regressed_slices=_regressed_slices(explanation),
        broken_ids=_broken_ids(explanation),
        deployment_notes=_deployment_notes(explanation),
    )


def _regressed_slices(explanation: JsonDict) -> list[str]:
    failure_slices = explanation.get("failure_slices", {})
    if not isinstance(failure_slices, dict):
        return []
    regressed = failure_slices.get("regressed", {})
    if not isinstance(regressed, dict):
        return []
    return sorted(str(name) for name in regressed)


def _broken_ids(explanation: JsonDict) -> list[str]:
    example_changes = explanation.get("example_changes", {})
    if not isinstance(example_changes, dict):
        return []
    broken = example_changes.get("broken_ids", [])
    if not isinstance(broken, list):
        return []
    return sorted(str(item) for item in broken)


def _deployment_notes(explanation: JsonDict) -> list[str]:
    deployment_risk = explanation.get("deployment_risk", {})
    if not isinstance(deployment_risk, dict):
        return []
    items = deployment_risk.get("items", {})
    if not isinstance(items, dict):
        return []
    notes: list[str] = []
    for name, value in sorted(items.items(), key=lambda item: str(item[0])):
        if isinstance(value, dict):
            risk = value.get("risk")
            if isinstance(risk, str):
                notes.append(f"{name}: {risk}")
            elif value:
                notes.append(str(name))
    return notes
