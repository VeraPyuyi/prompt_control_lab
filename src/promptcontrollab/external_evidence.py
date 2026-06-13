"""One-command evidence workflow for external eval/observability exports."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.ingest import (
    ingest_auto_results,
    ingest_langfuse_results,
    ingest_langsmith_results,
    ingest_promptfoo_results,
)
from promptcontrollab.run_comparison import compare_runs

ExternalTool = Literal["auto", "promptfoo", "langfuse", "langsmith"]


def build_external_evidence(
    *,
    tool: ExternalTool,
    baseline_input: Path,
    candidate_input: Path,
    out_dir: Path,
    score_name: str | None = None,
    provider: str | None = None,
    baseline_provider: str | None = None,
    candidate_provider: str | None = None,
    model: str | None = None,
    baseline_model: str | None = None,
    candidate_model: str | None = None,
    baseline_prompt_id: str | None = None,
    candidate_prompt_id: str | None = None,
    baseline_name: str | None = None,
    candidate_name: str | None = None,
    baseline_experiment: str | None = None,
    candidate_experiment: str | None = None,
    split_hash: str | None = None,
    baseline_method: str = "baseline",
    candidate_method: str = "candidate",
    title: str = "PromptControlLab External Evidence",
    seed: int = 0,
    bootstrap_samples: int = 1000,
    permutation_samples: int = 1000,
) -> JsonDict:
    """Import two external exports, compare them, and write a compact evidence bundle."""

    if out_dir.exists() and any(out_dir.iterdir()):
        msg = f"External evidence output directory must be empty: {out_dir}"
        raise ValueError(msg)
    ensure_dir(out_dir)

    imports_dir = out_dir / "imports"
    baseline_dir = imports_dir / "baseline"
    candidate_dir = imports_dir / "candidate"
    baseline_payload = _ingest_one(
        tool=tool,
        source_path=baseline_input,
        out_dir=baseline_dir,
        score_name=score_name,
        provider=baseline_provider or provider,
        model=baseline_model or model,
        prompt_id=baseline_prompt_id,
        name=baseline_name,
        experiment=baseline_experiment,
        method=baseline_method,
    )
    candidate_payload = _ingest_one(
        tool=tool,
        source_path=candidate_input,
        out_dir=candidate_dir,
        score_name=score_name,
        provider=candidate_provider or provider,
        model=candidate_model or model,
        prompt_id=candidate_prompt_id,
        name=candidate_name,
        experiment=candidate_experiment,
        method=candidate_method,
    )
    _patch_manifest(
        baseline_dir,
        split_hash=split_hash,
        prompt_id=baseline_prompt_id,
    )
    _patch_manifest(
        candidate_dir,
        split_hash=split_hash,
        prompt_id=candidate_prompt_id,
    )

    comparison_dir = out_dir / "comparison"
    comparison_payload = compare_runs(
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        out_dir=comparison_dir,
        title=title,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutation_samples=permutation_samples,
    )
    copied_artifacts = _copy_headline_artifacts(comparison_dir=comparison_dir, out_dir=out_dir)
    payload: JsonDict = {
        "kind": "external_evidence",
        "tool": tool,
        "out_dir": str(out_dir),
        "imports_dir": str(imports_dir),
        "baseline_import": baseline_payload,
        "candidate_import": candidate_payload,
        "comparison_dir": str(comparison_dir),
        "comparison": {
            "stats_path": comparison_payload.get("stats_path"),
            "comparison_validity_path": comparison_payload.get("comparison_validity_path"),
            "evidence_card_path": comparison_payload.get("evidence_card_path"),
            "report_md": comparison_payload.get("report_md"),
            "report_html": comparison_payload.get("report_html"),
            "evidence_card": comparison_payload.get("evidence_card"),
        },
        "copied_artifacts": [str(path) for path in copied_artifacts],
        "next_actions": [
            "Open evidence_card.md for the compact prompt optimization evidence card.",
            "Open report.html for the full comparison dashboard.",
            "Review imports/baseline and imports/candidate if provenance looks incomplete.",
        ],
    }
    write_json(out_dir / "evidence_from_result.json", payload)
    return payload


def _ingest_one(
    *,
    tool: ExternalTool,
    source_path: Path,
    out_dir: Path,
    score_name: str | None,
    provider: str | None,
    model: str | None,
    prompt_id: str | None,
    name: str | None,
    experiment: str | None,
    method: str,
) -> JsonDict:
    if tool == "auto":
        return ingest_auto_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=prompt_id,
            name=name,
            experiment=experiment,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    if tool == "promptfoo":
        return ingest_promptfoo_results(
            source_path=source_path,
            out_dir=out_dir,
            prompt_id=prompt_id,
            provider=provider,
            method=method,
        )
    if tool == "langfuse":
        return ingest_langfuse_results(
            source_path=source_path,
            out_dir=out_dir,
            name=name,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    if tool == "langsmith":
        return ingest_langsmith_results(
            source_path=source_path,
            out_dir=out_dir,
            experiment=experiment,
            score_name=score_name,
            model=model,
            provider=provider,
            method=method,
        )
    msg = f"Unsupported external evidence tool: {tool}"
    raise ValueError(msg)


def _patch_manifest(
    run_dir: Path,
    *,
    split_hash: str | None,
    prompt_id: str | None,
) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    if split_hash:
        manifest["split_hash"] = split_hash
    if prompt_id:
        prompt = manifest.get("prompt")
        prompt_payload = prompt if isinstance(prompt, dict) else {}
        prompt_payload.setdefault("prompt_id", prompt_id)
        manifest["prompt"] = prompt_payload
    write_json(manifest_path, manifest)


def _copy_headline_artifacts(*, comparison_dir: Path, out_dir: Path) -> list[Path]:
    names = [
        "evidence_card.json",
        "evidence_card.md",
        "report.md",
        "report.html",
        "stats.json",
        "comparison_validity.json",
        "comparison_validity.md",
    ]
    copied: list[Path] = []
    for name in names:
        source = comparison_dir / name
        if not source.exists():
            continue
        target = out_dir / name
        shutil.copy2(source, target)
        copied.append(target)
    return copied
