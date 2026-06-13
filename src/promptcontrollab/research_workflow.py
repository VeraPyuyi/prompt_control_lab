"""One-command research workflows for paper-derived diagnostics."""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from promptcontrollab.claim_check import run_claim_check
from promptcontrollab.evaluation import run_import_eval
from promptcontrollab.evidence_card import write_evidence_card
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json, write_jsonl
from promptcontrollab.optional import require_module
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.splitting import load_tasks, make_split, write_split
from promptcontrollab.statistics import compare_prediction_files
from promptcontrollab.trajectory import analyze_trajectory
from promptcontrollab.tv_soft import summarize_tv_soft
from promptcontrollab.validity import run_comparison_validity
from promptcontrollab.version import __version__

PAPER_MAPPING: list[JsonDict] = [
    {
        "concept": "tri-split withheld protocol",
        "commands": ["pcl split", "pcl analyze"],
        "artifact": "splits.json",
        "meaning": "Checks train/validation/withheld separation and split reproducibility.",
    },
    {
        "concept": "paired statistical comparison",
        "commands": ["pcl stats"],
        "artifact": "stats.json",
        "meaning": (
            "Reports paired mean delta, bootstrap CI, permutation p-value, "
            "and Holm correction."
        ),
    },
    {
        "concept": "soft-to-hard projection gap",
        "commands": ["pcl soft-hard"],
        "artifact": "diagnostics/soft_hard.json",
        "meaning": (
            "Measures whether learned soft vectors are close to deployable "
            "token embeddings."
        ),
    },
    {
        "concept": "HuggingFace hidden-state extraction",
        "commands": ["pcl extract-hidden"],
        "artifact": "inputs/hidden_states.npz",
        "meaning": (
            "Prepares trajectory-ready hidden states from an open/local model, or records "
            "the provided hidden-state source."
        ),
    },
    {
        "concept": "hidden-state trajectory",
        "commands": ["pcl trajectory"],
        "artifact": "diagnostics/trajectory.json",
        "meaning": "Reports drift, log-decay slope, fit quality, and turnpike-like signal.",
    },
    {
        "concept": "Riccati surrogate",
        "commands": ["pcl riccati"],
        "artifact": "diagnostics/riccati.json",
        "meaning": "Checks stability on a fitted finite-dimensional surrogate only.",
    },
    {
        "concept": "time-varying soft-control lane",
        "commands": ["pcl tv-soft"],
        "artifact": "diagnostics/tv_soft.json",
        "meaning": "Compares static, time-varying, shuffled, and random soft-control lanes.",
    },
    {
        "concept": "prompt optimization evidence card",
        "commands": ["pcl evidence-card"],
        "artifact": "evidence_card.json",
        "meaning": "Summarizes the recorded research evidence into one reviewer-facing card.",
    },
]

PAPER_REMEDIATION: dict[str, JsonDict] = {
    "soft-to-hard projection gap": {
        "required_inputs": ["inputs/soft_prompt.npz", "inputs/vocab_embeddings.npz"],
        "command": (
            "pcl soft-hard --soft inputs/soft_prompt.npz "
            "--vocab inputs/vocab_embeddings.npz --out diagnostics"
        ),
        "artifact": "diagnostics/soft_hard.json",
        "explains": (
            "Whether the optimized soft vectors remain close enough to deployable hard tokens."
        ),
    },
    "HuggingFace hidden-state extraction": {
        "required_inputs": ["inputs/prompts.jsonl", "HuggingFace model id or local model path"],
        "command": (
            "pcl extract-hidden --model <model-id-or-path> "
            "--prompts inputs/prompts.jsonl --out inputs/hidden_states.npz"
        ),
        "artifact": "inputs/hidden_states.npz",
        "explains": (
            "Creates the hidden-state artifact needed by trajectory and Riccati diagnostics."
        ),
    },
    "hidden-state trajectory": {
        "required_inputs": ["inputs/hidden_states.npz"],
        "command": "pcl trajectory --states inputs/hidden_states.npz --out diagnostics",
        "artifact": "diagnostics/trajectory.json",
        "explains": (
            "Whether internal hidden-state traces show drift, decay, or turnpike-like behavior."
        ),
    },
    "Riccati surrogate": {
        "required_inputs": [
            "inputs/surrogate_mats.npz or inputs/hidden_states.npz",
        ],
        "command": "pcl riccati --trajectory inputs/hidden_states.npz --out diagnostics",
        "artifact": "diagnostics/riccati.json",
        "explains": (
            "Whether a fitted finite-dimensional control surrogate is self-consistent and stable."
        ),
    },
    "time-varying soft-control lane": {
        "required_inputs": [
            "inputs/method_predictions.jsonl with static/tv/shuffled/random methods",
        ],
        "command": (
            "pcl tv-soft --predictions inputs/method_predictions.jsonl "
            "--out diagnostics --baseline-method static"
        ),
        "artifact": "diagnostics/tv_soft.json",
        "explains": (
            "Whether time-varying gains look tied to temporal structure rather than capacity."
        ),
    },
}


@dataclass(frozen=True)
class ResearchPaths:
    soft_path: Path | None
    vocab_path: Path | None
    states_path: Path | None
    matrices_path: Path | None
    tv_predictions_path: Path | None
    diagnostics_dir: Path
    summary_dir: Path


def write_research_demo(*, out_dir: Path, seed: int = 0) -> JsonDict:
    """Write synthetic paper-style fixtures and run all research diagnostics."""

    np = cast(Any, require_module("numpy", feature="research demo", extra="research"))
    inputs_dir = out_dir / "inputs"
    ensure_dir(inputs_dir)
    rng = np.random.default_rng(seed)

    soft = np.array([[0.95, 0.05], [0.05, 0.96], [0.72, 0.70]], dtype=float)
    embeddings = np.array(
        [[1.0, 0.0], [0.0, 1.0], [0.707, 0.707], [-1.0, 0.0]],
        dtype=float,
    )
    states = np.array(
        [[3.2, 0.25], [2.1, 0.17], [1.25, 0.10], [0.62, 0.05], [0.20, 0.02], [0.0, 0.0]],
        dtype=float,
    )
    states = states + rng.normal(0.0, 0.001, states.shape)
    matrices = {
        "A": np.array([[0.82, 0.04], [0.0, 0.65]], dtype=float),
        "B": np.eye(2),
        "Q": np.eye(2),
        "R": np.eye(2),
    }

    soft_path = inputs_dir / "soft_prompt.npz"
    vocab_path = inputs_dir / "vocab_embeddings.npz"
    states_path = inputs_dir / "hidden_states.npz"
    matrices_path = inputs_dir / "surrogate_mats.npz"
    predictions_path = inputs_dir / "method_predictions.jsonl"
    np.savez(soft_path, soft=soft)
    np.savez(vocab_path, embeddings=embeddings)
    np.savez(states_path, states=states)
    write_json(
        Path(str(states_path) + ".metadata.json"),
        {
            "kind": "research_demo_hidden_states",
            "source": "synthetic_demo",
            "model_id": "synthetic_control_trace",
            "out_path": str(states_path),
            "states_shape": [int(states.shape[0]), int(states.shape[1])],
            "prompt_count": int(states.shape[0]),
            "layer": None,
            "pool": "synthetic_trajectory",
            "boundary": (
                "Synthetic hidden states for demonstrating trajectory/Riccati diagnostics; "
                "not activations from an operational language model."
            ),
        },
    )
    np.savez(matrices_path, **matrices)
    write_jsonl(predictions_path, _demo_method_predictions())
    write_json(
        inputs_dir / "README.json",
        {
            "kind": "research_demo_inputs",
            "description": (
                "Synthetic fixtures for paper-derived diagnostics. They are small enough to run "
                "without an LLM and are not benchmark results."
            ),
            "seed": seed,
        },
    )
    _write_demo_evaluation_bundle(out_dir=out_dir, inputs_dir=inputs_dir, seed=seed)

    return run_research_diagnostics(
        run_dir=out_dir,
        mode="demo",
        soft_path=soft_path,
        vocab_path=vocab_path,
        states_path=states_path,
        matrices_path=matrices_path,
        tv_predictions_path=predictions_path,
        diagnostics_dir=out_dir / "diagnostics",
        summary_dir=out_dir,
        tail=1,
    )


def _write_demo_evaluation_bundle(*, out_dir: Path, inputs_dir: Path, seed: int) -> None:
    tasks_path = inputs_dir / "tasks.jsonl"
    baseline_raw_path = inputs_dir / "baseline_predictions.jsonl"
    candidate_raw_path = inputs_dir / "candidate_predictions.jsonl"
    tasks = _demo_tasks(count=20)
    write_jsonl(tasks_path, tasks)
    write_jsonl(
        baseline_raw_path,
        [{"id": task["id"], "output": "wrong"} for task in tasks],
    )
    write_jsonl(
        candidate_raw_path,
        [{"id": task["id"], "output": task["expected"]} for task in tasks],
    )

    loaded_tasks = load_tasks(tasks_path)
    split = make_split(loaded_tasks, train_ratio=0.5, val_ratio=0.25, seed=seed)
    write_split(out_dir / "splits.json", split)
    model_provider = "synthetic"
    model_id = "synthetic-control-model-20260613"
    run_import_eval(
        data_path=tasks_path,
        predictions_path=baseline_raw_path,
        out_dir=out_dir / "baseline",
        metric="exact_match",
        method="baseline",
        provider=model_provider,
        model_id=model_id,
    )
    run_import_eval(
        data_path=tasks_path,
        predictions_path=candidate_raw_path,
        out_dir=out_dir / "candidate",
        metric="exact_match",
        method="candidate",
        provider=model_provider,
        model_id=model_id,
    )
    baseline_prompt_hash = _demo_prompt_hash("Answer the question.")
    candidate_prompt_hash = _demo_prompt_hash("Answer with only the final result.")
    _patch_demo_run_manifest(
        out_dir / "baseline" / "manifest.json",
        split_hash=split.split_hash,
        prompt_id="research-demo-baseline",
        prompt_hash=baseline_prompt_hash,
    )
    _patch_demo_run_manifest(
        out_dir / "candidate" / "manifest.json",
        split_hash=split.split_hash,
        prompt_id="research-demo-candidate",
        prompt_hash=candidate_prompt_hash,
    )
    stats = compare_prediction_files(
        baseline_path=out_dir / "baseline" / "predictions.jsonl",
        candidate_path=out_dir / "candidate" / "predictions.jsonl",
        out_path=out_dir / "stats.json",
        seed=seed,
        bootstrap_samples=200,
        permutation_samples=200,
    )
    validity = run_comparison_validity(
        baseline_dir=out_dir / "baseline",
        candidate_dir=out_dir / "candidate",
        out_path=out_dir / "comparison_validity.json",
    )
    candidate_metrics = read_json(out_dir / "candidate" / "metrics.json")
    write_json(out_dir / "metrics.json", candidate_metrics)
    write_json(
        out_dir / "manifest.json",
        {
            "tool": "promptcontrollab",
            "tool_version": __version__,
            "mode": "research_demo",
            "method": "synthetic_baseline_vs_candidate",
            "metric": "exact_match",
            "data_path": str(tasks_path),
            "baseline_run": str(out_dir / "baseline"),
            "candidate_run": str(out_dir / "candidate"),
            "split_hash": split.split_hash,
            "model": read_json(out_dir / "candidate" / "manifest.json").get("model", {}),
            "prompt": {
                "prompt_id": "research-demo-candidate",
                "prompt_hash": candidate_prompt_hash,
                "prompt_version": "synthetic-demo",
            },
            "baseline_prompt": {
                "prompt_id": "research-demo-baseline",
                "prompt_hash": baseline_prompt_hash,
                "prompt_version": "synthetic-demo",
            },
            "candidate_prompt": {
                "prompt_id": "research-demo-candidate",
                "prompt_hash": candidate_prompt_hash,
                "prompt_version": "synthetic-demo",
            },
            "stats_summary": {
                "mean_delta": stats["comparisons"][0]["mean_delta"],
                "permutation_p_value": stats["comparisons"][0]["permutation_p_value"],
            },
            "comparison_validity": validity.get("validity"),
            "boundary": (
                "Synthetic comparison bundle for demonstrating PromptControlLab evidence "
                "artifacts; not a benchmark result."
            ),
        },
    )


def _demo_tasks(*, count: int) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for index in range(count):
        expected = str(index + 1)
        rows.append(
            {
                "id": f"demo-{index:02d}",
                "input": f"What is {index} + 1?",
                "expected": expected,
                "slice": "arithmetic" if index % 2 == 0 else "format",
                "meta": {"source": "research_demo_synthetic"},
            }
        )
    return rows


def _patch_demo_run_manifest(
    path: Path,
    *,
    split_hash: str,
    prompt_id: str,
    prompt_hash: str,
) -> None:
    manifest = read_json(path)
    manifest["split_hash"] = split_hash
    manifest["prompt"] = {
        "prompt_id": prompt_id,
        "prompt_hash": prompt_hash,
        "prompt_version": "synthetic-demo",
    }
    write_json(path, manifest)


def _demo_prompt_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def run_research_diagnostics(
    *,
    run_dir: Path | None = None,
    mode: str = "diagnose",
    soft_path: Path | None = None,
    vocab_path: Path | None = None,
    states_path: Path | None = None,
    matrices_path: Path | None = None,
    tv_predictions_path: Path | None = None,
    diagnostics_dir: Path | None = None,
    summary_dir: Path | None = None,
    baseline_method: str = "static",
    tail: int = 1,
    iterations: int = 200,
) -> JsonDict:
    """Run available paper-derived diagnostics and write a unified report."""

    paths = _resolve_research_paths(
        run_dir=run_dir,
        soft_path=soft_path,
        vocab_path=vocab_path,
        states_path=states_path,
        matrices_path=matrices_path,
        tv_predictions_path=tv_predictions_path,
        diagnostics_dir=diagnostics_dir,
        summary_dir=summary_dir,
    )
    diagnostics: JsonDict = {}
    artifacts: JsonDict = {}

    if paths.soft_path is not None or paths.vocab_path is not None:
        if paths.soft_path is None or paths.vocab_path is None:
            msg = "Soft-to-hard diagnostics require both --soft and --vocab"
            raise ValueError(msg)
        diagnostics["soft_hard"] = analyze_soft_hard(
            soft_path=paths.soft_path,
            vocab_path=paths.vocab_path,
            out_dir=paths.diagnostics_dir,
        )
        artifacts["soft_hard"] = str(paths.diagnostics_dir / "soft_hard.json")

    if paths.states_path is not None:
        artifacts["hidden_states"] = str(paths.states_path)
        metadata_path = Path(str(paths.states_path) + ".metadata.json")
        if metadata_path.exists():
            artifacts["hidden_state_metadata"] = str(metadata_path)
        diagnostics["trajectory"] = analyze_trajectory(
            states_path=paths.states_path,
            out_dir=paths.diagnostics_dir,
            tail=tail,
        )
        artifacts["trajectory"] = str(paths.diagnostics_dir / "trajectory.json")

    if paths.matrices_path is not None or paths.states_path is not None:
        diagnostics["riccati"] = analyze_riccati(
            matrices_path=paths.matrices_path,
            trajectory_path=None if paths.matrices_path is not None else paths.states_path,
            out_dir=paths.diagnostics_dir,
            iterations=iterations,
        )
        artifacts["riccati"] = str(paths.diagnostics_dir / "riccati.json")

    if paths.tv_predictions_path is not None:
        diagnostics["tv_soft"] = summarize_tv_soft(
            predictions_path=paths.tv_predictions_path,
            out_dir=paths.diagnostics_dir,
            baseline_method=baseline_method,
        )
        artifacts["tv_soft"] = str(paths.diagnostics_dir / "tv_soft.json")

    if not diagnostics:
        bridge_payload = _run_external_bridge_diagnostics(
            run_dir=run_dir,
            mode=mode,
            diagnostics_dir=paths.diagnostics_dir,
            summary_dir=paths.summary_dir,
        )
        if bridge_payload is not None:
            return bridge_payload
        msg = "No research diagnostic inputs found. Provide --run or explicit diagnostic inputs."
        raise ValueError(msg)

    payload: JsonDict = {
        "kind": "research_diagnostics",
        "mode": mode,
        "run_dir": str(run_dir) if run_dir is not None else None,
        "diagnostics_dir": str(paths.diagnostics_dir),
        "summary_dir": str(paths.summary_dir),
        "inputs": _research_input_summary(paths),
        "diagnostics": diagnostics,
        "artifacts": artifacts,
        "paper_mapping": PAPER_MAPPING,
        "interpretation": _interpret_diagnostics(diagnostics),
        "boundary": (
            "These are paper-derived diagnostics and synthetic/demo probes when generated by "
            "`pcl research-demo`. They do not prove full language-model stability or universal "
            "prompt improvement."
        ),
    }
    _write_research_outputs(summary_dir=paths.summary_dir, payload=payload)
    write_evidence_card(paths.summary_dir)
    run_claim_check(
        paths.summary_dir,
        claim="full-research",
        out_path=paths.summary_dir / "claim_check.json",
    )
    write_research_bundle_index(paths.summary_dir)
    return payload


def _run_external_bridge_diagnostics(
    *,
    run_dir: Path | None,
    mode: str,
    diagnostics_dir: Path,
    summary_dir: Path,
) -> JsonDict | None:
    if run_dir is None:
        return None
    ecosystem_path = run_dir / "ecosystem_demo.json"
    external_path = run_dir / "evidence_from_result.json"
    if ecosystem_path.exists():
        ecosystem = read_json(ecosystem_path)
        diagnostic = _summarize_ecosystem_bundle(run_dir=run_dir, payload=ecosystem)
        artifacts = {"ecosystem_demo": str(ecosystem_path)}
        diagnostics: JsonDict = {"ecosystem_bridge": diagnostic}
        interpretation = [
            (
                "External-tool exports were converted into PCL evidence bundles. "
                "Use this diagnosis to see which paper-derived evidence is present "
                "and which research diagnostics still require open-model artifacts."
            )
        ]
    elif external_path.exists():
        external = read_json(external_path)
        diagnostic = _summarize_external_bundle(run_dir=run_dir, fallback=external)
        artifacts = {"external_evidence": str(external_path)}
        diagnostics = {"external_bridge": diagnostic}
        interpretation = [
            (
                f"{diagnostic.get('tool')} export has paired evidence and bridge metadata, "
                "but missing paper diagnostics should not be treated as measured."
            )
        ]
    else:
        return None

    payload: JsonDict = {
        "kind": "research_diagnostics",
        "mode": mode,
        "diagnostic_type": "external_evidence_gap",
        "run_dir": str(run_dir),
        "diagnostics_dir": str(diagnostics_dir),
        "summary_dir": str(summary_dir),
        "inputs": {
            "external_evidence": (
                "external eval/observability artifacts; no hidden states or soft prompts "
                "were inferred"
            )
        },
        "diagnostics": diagnostics,
        "artifacts": artifacts,
        "paper_mapping": PAPER_MAPPING,
        "interpretation": interpretation,
        "boundary": (
            "This diagnosis audits evidence coverage for external-tool exports. It can "
            "identify missing soft-hard, trajectory, Riccati, and time-varying-control "
            "artifacts, but it does not fabricate those measurements."
        ),
    }
    ensure_dir(summary_dir)
    ensure_dir(diagnostics_dir)
    _write_research_outputs(summary_dir=summary_dir, payload=payload)
    write_research_bundle_index(summary_dir)
    return payload


def _write_research_outputs(*, summary_dir: Path, payload: JsonDict) -> None:
    ensure_dir(summary_dir)
    gap_plan = _build_research_gap_plan(payload)
    if gap_plan["actions"]:
        plan_json = summary_dir / "research_gap_plan.json"
        plan_md = summary_dir / "research_gap_plan.md"
        plan_html = summary_dir / "research_gap_plan.html"
        commands_ps1 = summary_dir / "research_gap_commands.ps1"
        commands_sh = summary_dir / "research_gap_commands.sh"
        write_json(plan_json, gap_plan)
        plan_md.write_text(_render_research_gap_plan_markdown(gap_plan), encoding="utf-8")
        plan_html.write_text(render_research_gap_plan_html(gap_plan), encoding="utf-8")
        commands_ps1.write_text(_render_gap_commands_ps1(gap_plan), encoding="utf-8")
        commands_sh.write_text(_render_gap_commands_sh(gap_plan), encoding="utf-8")
        artifacts = payload.get("artifacts")
        artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
        artifacts_dict.update(
            {
                "research_gap_plan": str(plan_json),
                "research_gap_plan_markdown": str(plan_md),
                "research_gap_plan_html": str(plan_html),
                "research_gap_commands_ps1": str(commands_ps1),
                "research_gap_commands_sh": str(commands_sh),
            }
        )
        payload["artifacts"] = artifacts_dict
    diagnostics_html = summary_dir / "research_diagnostics.html"
    bundle_html = summary_dir / "research_bundle.html"
    artifacts = payload.get("artifacts")
    artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
    artifacts_dict["research_diagnostics_html"] = str(diagnostics_html)
    artifacts_dict["research_bundle_html"] = str(bundle_html)
    payload["artifacts"] = artifacts_dict
    write_json(summary_dir / "research_diagnostics.json", payload)
    (summary_dir / "research_diagnostics.md").write_text(
        render_research_diagnostics_markdown(payload),
        encoding="utf-8",
    )
    diagnostics_html.write_text(render_research_diagnostics_html(payload), encoding="utf-8")
    write_research_bundle_index(summary_dir)


def write_research_gap_status(*, run_dir: Path, out_path: Path | None = None) -> JsonDict:
    """Check whether actions in ``research_gap_plan.json`` have been completed."""

    plan_path = run_dir / "research_gap_plan.json"
    if not plan_path.exists():
        msg = f"No research_gap_plan.json found in {run_dir}. Run `pcl diagnose --run {run_dir}`."
        raise ValueError(msg)
    plan = read_json(plan_path)
    actions = _remediation_list(plan.get("actions"))
    rows = [_gap_status_row(run_dir=run_dir, action=action) for action in actions]
    missing = [row for row in rows if row["status"] != "present"]
    payload: JsonDict = {
        "kind": "research_gap_status",
        "run_dir": str(run_dir),
        "plan_path": str(plan_path),
        "status": "complete" if not missing else "needs_work",
        "action_count": len(rows),
        "complete_count": len(rows) - len(missing),
        "missing_count": len(missing),
        "actions": rows,
        "boundary": (
            "This status only checks whether the expected artifact files exist. It does not "
            "judge whether the diagnostic is scientifically sufficient."
        ),
    }
    json_path = _gap_status_json_path(run_dir=run_dir, out_path=out_path)
    md_path = json_path.with_suffix(".md")
    html_path = json_path.with_suffix(".html")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["html_path"] = str(html_path)
    ensure_dir(json_path.parent)
    write_json(json_path, payload)
    md_path.write_text(_render_research_gap_status_markdown(payload), encoding="utf-8")
    html_path.write_text(render_research_gap_status_html(payload), encoding="utf-8")
    write_research_bundle_index(json_path.parent)
    return payload


def _gap_status_json_path(*, run_dir: Path, out_path: Path | None) -> Path:
    if out_path is None:
        return run_dir / "research_gap_status.json"
    if out_path.suffix:
        return out_path
    return out_path / "research_gap_status.json"


def write_research_bundle_index(run_dir: Path) -> JsonDict:
    """Write a browser-first index for the research evidence bundle."""

    ensure_dir(run_dir)
    payload = build_research_bundle_index(run_dir)
    out_path = run_dir / "research_bundle.html"
    out_path.write_text(render_research_bundle_index_html(payload), encoding="utf-8")
    payload["html_path"] = str(out_path)
    write_json(run_dir / "research_bundle.json", payload)
    return payload


def verify_research_bundle_index(run_dir: Path) -> JsonDict:
    """Verify hashes recorded in an existing research bundle index."""

    bundle_path = run_dir / "research_bundle.json"
    if not bundle_path.exists():
        msg = f"Research bundle index does not exist: {bundle_path}"
        raise ValueError(msg)
    bundle = read_json(bundle_path)
    artifacts = bundle.get("artifacts")
    rows = artifacts if isinstance(artifacts, list) else []
    results = [_verify_bundle_artifact(run_dir=run_dir, item=item) for item in rows]
    checked = [item for item in results if item.get("status") in {"ok", "mismatch", "missing"}]
    mismatches = [item for item in results if item.get("status") == "mismatch"]
    missing = [item for item in results if item.get("status") == "missing"]
    payload: JsonDict = {
        "kind": "research_bundle_verification",
        "run_dir": str(run_dir),
        "bundle_path": str(bundle_path),
        "status": "pass" if not mismatches and not missing else "fail",
        "checked_count": len(checked),
        "ok_count": sum(1 for item in results if item.get("status") == "ok"),
        "mismatch_count": len(mismatches),
        "missing_count": len(missing),
        "unchecked_count": sum(1 for item in results if item.get("status") == "unchecked"),
        "self_index_count": sum(1 for item in results if item.get("status") == "self_index"),
        "results": results,
        "boundary": (
            "This check verifies recorded SHA-256 values for linked evidence artifacts. "
            "It is tamper-evidence for this local bundle, not a cryptographic signature "
            "or proof of scientific sufficiency."
        ),
    }
    write_json(run_dir / "research_bundle_verification.json", payload)
    (run_dir / "research_bundle_verification.md").write_text(
        _render_research_bundle_verification_markdown(payload),
        encoding="utf-8",
    )
    (run_dir / "research_bundle_verification.html").write_text(
        render_research_bundle_verification_html(payload),
        encoding="utf-8",
    )
    return payload


def _verify_bundle_artifact(*, run_dir: Path, item: object) -> JsonDict:
    if not isinstance(item, dict):
        return {"path": "", "status": "unchecked", "reason": "invalid artifact row"}
    relative = str(item.get("path") or "")
    path = run_dir / relative
    expected = item.get("sha256")
    if item.get("generated_index_artifact"):
        return {
            "path": relative,
            "status": "self_index",
            "expected_sha256": expected,
            "reason": "generated index artifacts are not self-hashed",
        }
    if not expected:
        return {
            "path": relative,
            "status": "unchecked",
            "expected_sha256": None,
            "reason": "no recorded sha256",
        }
    if not path.exists() or not path.is_file():
        return {
            "path": relative,
            "status": "missing",
            "expected_sha256": expected,
            "actual_sha256": None,
        }
    actual = _sha256_file(path)
    return {
        "path": relative,
        "status": "ok" if actual == expected else "mismatch",
        "expected_sha256": expected,
        "actual_sha256": actual,
        "bytes": path.stat().st_size,
    }


def build_research_bundle_index(run_dir: Path) -> JsonDict:
    """Collect known research artifacts into one navigable index payload."""

    artifacts = _bundle_artifacts(run_dir)
    present_artifacts = [item for item in artifacts if item.get("exists")]
    hashed_artifacts = [item for item in present_artifacts if item.get("sha256")]
    diagnostics = _read_optional_research_json(run_dir / "research_diagnostics.json")
    evidence = _read_optional_research_json(run_dir / "evidence_card.json")
    claim = _read_optional_research_json(run_dir / "claim_check.json")
    gap_status = _read_optional_research_json(run_dir / "research_gap_status.json")
    gap_plan = _read_optional_research_json(run_dir / "research_gap_plan.json")
    diagnostics_payload = diagnostics.get("diagnostics")
    diagnostics_dict = diagnostics_payload if isinstance(diagnostics_payload, dict) else {}
    expected = [
        "research_diagnostics.html",
        "evidence_card.html",
        "claim_check.html",
        "research_gap_plan.html",
        "research_gap_status.html",
        "report.html",
    ]
    return {
        "kind": "research_bundle_index",
        "run_dir": str(run_dir),
        "status": _bundle_status(
            evidence=evidence,
            claim=claim,
            gap_status=gap_status,
            gap_plan=gap_plan,
        ),
        "recommendation": evidence.get("recommendation") or claim.get("status") or "review",
        "evidence_tier": evidence.get("evidence_tier") or claim.get("evidence_tier"),
        "claim_check_status": claim.get("status"),
        "claim_language": claim.get("safe_claim_language") or evidence.get("claim_language"),
        "diagnostic_type": diagnostics.get("diagnostic_type") or diagnostics.get("mode"),
        "diagnostics_present": sorted(diagnostics_dict),
        "gap_status": gap_status.get("status") or ("planned" if gap_plan else "not_planned"),
        "gap_complete_count": gap_status.get("complete_count"),
        "gap_missing_count": gap_status.get("missing_count"),
        "review_order": _bundle_review_order(run_dir),
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "present_artifact_count": len(present_artifacts),
        "hashed_artifact_count": len(hashed_artifacts),
        "missing_html_artifacts": [name for name in expected if not (run_dir / name).exists()],
        "boundary": (
            "This index is a navigation aid. It does not add evidence beyond the linked "
            "artifacts and does not prove scientific sufficiency."
        ),
    }


def _read_optional_research_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _bundle_status(
    *,
    evidence: JsonDict,
    claim: JsonDict,
    gap_status: JsonDict,
    gap_plan: JsonDict,
) -> str:
    if claim.get("status") == "fail":
        return "needs_review"
    if gap_status.get("status") == "needs_work":
        return "needs_work"
    if gap_plan and not gap_status:
        return "gap_status_not_checked"
    if evidence.get("recommendation") == "supported" and claim.get("status") == "pass":
        return "supported"
    if evidence or claim:
        return "review"
    return "incomplete"


def _bundle_review_order(run_dir: Path) -> list[JsonDict]:
    candidates = [
        (
            "Evidence audit",
            "evidence_audit_result.html",
            "One-command audit summary for external imports, gaps, and bundle verification.",
        ),
        (
            "Bridge summary",
            "bridge_summary.html",
            "External-tool provenance, PCL-added evidence, and next review actions.",
        ),
        (
            "Start here",
            "research_diagnostics.html",
            "Paper-derived diagnostic coverage and missing evidence.",
        ),
        ("Evidence card", "evidence_card.html", "Compact prompt optimization evidence card."),
        (
            "Claim check",
            "claim_check.html",
            "Strongest claim currently supported by the artifact bundle.",
        ),
        (
            "Gap plan",
            "research_gap_plan.html",
            "Commands and inputs needed to close missing paper diagnostics.",
        ),
        (
            "Gap status",
            "research_gap_status.html",
            "Whether expected gap-closing artifacts currently exist.",
        ),
        ("Full report", "report.html", "Full run comparison report when available."),
    ]
    return [
        {
            "label": label,
            "path": path,
            "exists": (run_dir / path).exists(),
            "explains": explains,
        }
        for label, path, explains in candidates
    ]


def _bundle_artifacts(run_dir: Path) -> list[JsonDict]:
    names = [
        "research_bundle.html",
        "research_bundle.json",
        "evidence_audit_result.html",
        "evidence_audit_result.md",
        "evidence_audit_result.json",
        "research_bundle_verification.html",
        "research_bundle_verification.md",
        "research_bundle_verification.json",
        "research_diagnostics.html",
        "research_diagnostics.md",
        "research_diagnostics.json",
        "bridge_summary.html",
        "bridge_summary.md",
        "bridge_summary.json",
        "evidence_card.html",
        "evidence_card.md",
        "evidence_card.json",
        "claim_check.html",
        "claim_check.md",
        "claim_check.json",
        "research_gap_plan.html",
        "research_gap_plan.md",
        "research_gap_plan.json",
        "research_gap_status.html",
        "research_gap_status.md",
        "research_gap_status.json",
        "report.html",
        "report.md",
    ]
    return [_bundle_artifact_row(run_dir=run_dir, name=name) for name in names]


def _bundle_artifact_row(*, run_dir: Path, name: str) -> JsonDict:
    path = run_dir / name
    self_generated = name in {"research_bundle.html", "research_bundle.json"}
    audit_summary = name.startswith("evidence_audit_result.")
    exists = path.exists() or self_generated
    row: JsonDict = {
        "path": name,
        "exists": exists,
        "role": _artifact_role(name),
    }
    if self_generated:
        row["generated_index_artifact"] = True
        if not path.exists():
            row["hash_status"] = "generated_during_refresh"
            return row
        row["hash_status"] = "self_index_not_hashed"
        return row
    if audit_summary and path.exists():
        row["bytes"] = path.stat().st_size
        row["hash_status"] = "audit_summary_not_hashed"
        return row
    if path.exists() and path.is_file():
        row["bytes"] = path.stat().st_size
        row["sha256"] = _sha256_file(path)
        row["hash_status"] = "hashed"
    return row


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _artifact_role(name: str) -> str:
    if name.endswith(".html"):
        return "browser_review"
    if name.endswith(".json"):
        return "automation"
    if name.endswith(".md"):
        return "text_review"
    return "artifact"


def render_research_bundle_index_html(payload: JsonDict) -> str:
    """Render the research bundle navigation page."""

    review_order = payload.get("review_order")
    review_rows = []
    if isinstance(review_order, list):
        for item in review_order:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            exists = bool(item.get("exists"))
            link = f'<a href="{_html_attr(path)}">{_html_text(path)}</a>' if exists else path
            review_rows.append(
                [
                    item.get("label", ""),
                    _badge("present" if exists else "missing"),
                    link,
                    item.get("explains", ""),
                ]
            )
    artifacts = payload.get("artifacts")
    artifact_rows = []
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            exists = bool(item.get("exists"))
            link = f'<a href="{_html_attr(path)}">{_html_text(path)}</a>' if exists else path
            artifact_rows.append(
                [
                    item.get("role", ""),
                    _badge("present" if exists else "missing"),
                    link,
                    item.get("bytes", ""),
                    item.get("sha256") or item.get("hash_status", ""),
                ]
            )
    return _html_page(
        title="Research Evidence Bundle",
        subtitle="One browser entry point for paper-derived prompt optimization evidence.",
        body=[
            _metric_grid(
                [
                    ("Status", _badge(str(payload.get("status", "")))),
                    ("Evidence tier", payload.get("evidence_tier", "")),
                    ("Claim check", _badge(str(payload.get("claim_check_status", "")))),
                    ("Gap status", _badge(str(payload.get("gap_status", "")))),
                    ("Diagnostic type", payload.get("diagnostic_type", "")),
                ]
            ),
            _section(
                "Review Order",
                _table(["Step", "Status", "Open", "What it explains"], review_rows),
            ),
            _section(
                "Artifact Inventory",
                _table(
                    ["Role", "Status", "Artifact", "Bytes", "SHA-256 / hash status"],
                    artifact_rows,
                ),
            ),
            _section("Safe Claim Language", _paragraph(payload.get("claim_language"))),
            _section("Boundary", _paragraph(payload.get("boundary"))),
        ],
    )


def _render_research_bundle_verification_markdown(payload: JsonDict) -> str:
    lines = [
        "# Research Bundle Verification",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Checked artifacts: `{payload.get('checked_count')}`",
        f"- OK: `{payload.get('ok_count')}`",
        f"- Mismatches: `{payload.get('mismatch_count')}`",
        f"- Missing: `{payload.get('missing_count')}`",
        f"- Unchecked: `{payload.get('unchecked_count')}`",
        "",
        "| Artifact | Status | Expected SHA-256 | Actual SHA-256 |",
        "|---|---|---|---|",
    ]
    for item in _verification_rows(payload.get("results")):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("path", "")),
                    str(item.get("status", "")),
                    str(item.get("expected_sha256", "")),
                    str(item.get("actual_sha256", "")),
                ]
            )
            + " |"
        )
    lines.extend(["", str(payload.get("boundary", "")), ""])
    return "\n".join(lines)


def render_research_bundle_verification_html(payload: JsonDict) -> str:
    """Render research bundle hash verification as browser-friendly HTML."""

    rows = [
        [
            item.get("path", ""),
            _badge(str(item.get("status", ""))),
            item.get("expected_sha256", ""),
            item.get("actual_sha256", ""),
        ]
        for item in _verification_rows(payload.get("results"))
    ]
    return _html_page(
        title="Research Bundle Verification",
        subtitle="SHA-256 verification for linked paper-evidence artifacts.",
        body=[
            _metric_grid(
                [
                    ("Status", _badge(str(payload.get("status", "")))),
                    ("Checked", payload.get("checked_count", "")),
                    ("OK", payload.get("ok_count", "")),
                    ("Mismatches", payload.get("mismatch_count", "")),
                    ("Missing", payload.get("missing_count", "")),
                ]
            ),
            _section(
                "Artifact Hash Checks",
                _table(["Artifact", "Status", "Expected SHA-256", "Actual SHA-256"], rows),
            ),
            _section("Boundary", _paragraph(payload.get("boundary"))),
        ],
    )


def _verification_rows(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _gap_status_row(*, run_dir: Path, action: JsonDict) -> JsonDict:
    artifact = str(action.get("artifact") or "")
    artifact_path = run_dir / artifact if artifact else run_dir
    exists = bool(artifact and artifact_path.exists())
    required = action.get("required_inputs")
    return {
        "step": action.get("step"),
        "concept": action.get("concept", ""),
        "status": "present" if exists else "missing",
        "artifact": artifact,
        "artifact_path": str(artifact_path),
        "required_inputs": required if isinstance(required, list) else [],
        "command": action.get("command", ""),
        "explains": action.get("explains", ""),
    }


def _render_research_gap_status_markdown(payload: JsonDict) -> str:
    actions = _remediation_list(payload.get("actions"))
    lines = [
        "# Research Evidence Gap Status",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Complete: `{payload.get('complete_count')}/{payload.get('action_count')}`",
        f"- Missing: `{payload.get('missing_count')}`",
        "",
        str(payload.get("boundary", "")),
        "",
        "| Step | Diagnostic | Status | Artifact | Command |",
        "|---:|---|---|---|---|",
    ]
    for action in actions:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(action.get("step", "")),
                    str(action.get("concept", "")),
                    str(action.get("status", "")),
                    f"`{action.get('artifact', '')}`",
                    f"`{action.get('command', '')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def render_research_gap_status_html(payload: JsonDict) -> str:
    """Render research gap closure status as browser-friendly HTML."""

    actions = _remediation_list(payload.get("actions"))
    rows = [
        [
            action.get("step", ""),
            action.get("concept", ""),
            _badge(str(action.get("status", ""))),
            action.get("artifact", ""),
            action.get("command", ""),
        ]
        for action in actions
    ]
    return _html_page(
        title="Research Evidence Gap Status",
        subtitle=(
            f"Status: {payload.get('status')} - "
            f"{payload.get('complete_count')}/{payload.get('action_count')} complete"
        ),
        body=[
            _metric_grid(
                [
                    ("Status", _badge(str(payload.get("status", "")))),
                    ("Complete", f"{payload.get('complete_count')}/{payload.get('action_count')}"),
                    ("Missing", payload.get("missing_count", "")),
                ]
            ),
            _paragraph(payload.get("boundary")),
            _table(["Step", "Diagnostic", "Status", "Artifact", "Command"], rows),
        ],
    )


def _build_research_gap_plan(payload: JsonDict) -> JsonDict:
    actions = _gap_actions_from_payload(payload)
    return {
        "kind": "research_gap_plan",
        "run_dir": payload.get("run_dir"),
        "diagnostic_type": payload.get("diagnostic_type", payload.get("mode")),
        "action_count": len(actions),
        "actions": actions,
        "boundary": (
            "This plan is a copy-paste guide for collecting missing paper-derived evidence. "
            "Commands with placeholders must be edited before use; no missing diagnostic is "
            "treated as measured until its artifact exists."
        ),
    }


def _gap_actions_from_payload(payload: JsonDict) -> list[JsonDict]:
    diagnostics = payload.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    ecosystem = diagnostics_dict.get("ecosystem_bridge")
    if isinstance(ecosystem, dict):
        return _numbered_actions(_remediation_list(ecosystem.get("paper_gap_remediation")))
    external = diagnostics_dict.get("external_bridge")
    if isinstance(external, dict):
        return _numbered_actions(_remediation_list(external.get("paper_gap_remediation")))

    present = {
        "soft-to-hard projection gap": isinstance(diagnostics_dict.get("soft_hard"), dict),
        "HuggingFace hidden-state extraction": _has_hidden_state_input(payload),
        "hidden-state trajectory": isinstance(diagnostics_dict.get("trajectory"), dict),
        "Riccati surrogate": isinstance(diagnostics_dict.get("riccati"), dict),
        "time-varying soft-control lane": isinstance(diagnostics_dict.get("tv_soft"), dict),
    }
    actions = [
        _paper_remediation_for(concept)
        for concept, is_present in present.items()
        if not is_present and _paper_remediation_for(concept)
    ]
    return _numbered_actions(actions)


def _has_hidden_state_input(payload: JsonDict) -> bool:
    artifacts = payload.get("artifacts")
    artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
    if artifacts_dict.get("hidden_states"):
        return True
    inputs = payload.get("inputs")
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    return isinstance(inputs_dict.get("hidden_states"), dict)


def _numbered_actions(actions: list[JsonDict]) -> list[JsonDict]:
    numbered: list[JsonDict] = []
    for index, action in enumerate(actions, start=1):
        row = dict(action)
        row["step"] = index
        numbered.append(row)
    return numbered


def _render_research_gap_plan_markdown(plan: JsonDict) -> str:
    actions = _remediation_list(plan.get("actions"))
    lines = [
        "# Research Evidence Gap Plan",
        "",
        str(plan.get("boundary", "")),
        "",
    ]
    if not actions:
        lines.extend(["No missing paper-derived diagnostic actions were found.", ""])
        return "\n".join(lines)
    lines.extend(
        [
            (
                "| Step | Missing diagnostic | Required inputs | Command | Artifact | "
                "What it explains |"
            ),
            "|---:|---|---|---|---|---|",
        ]
    )
    for action in actions:
        required = action.get("required_inputs")
        required_inputs = (
            ", ".join(str(item) for item in required) if isinstance(required, list) else ""
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(action.get("step", "")),
                    str(action.get("concept", "")),
                    required_inputs,
                    f"`{action.get('command', '')}`",
                    f"`{action.get('artifact', '')}`",
                    str(action.get("explains", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "The companion `research_gap_commands.ps1` and `research_gap_commands.sh` files are "
            "review-first scripts. They intentionally stop before running commands so you can "
            "replace placeholders and confirm paths.",
            "",
        ]
    )
    return "\n".join(lines)


def render_research_gap_plan_html(plan: JsonDict) -> str:
    """Render the research gap plan as browser-friendly HTML."""

    actions = _remediation_list(plan.get("actions"))
    if actions:
        rows = []
        for action in actions:
            required = action.get("required_inputs")
            required_inputs = (
                ", ".join(str(item) for item in required) if isinstance(required, list) else ""
            )
            rows.append(
                [
                    action.get("step", ""),
                    action.get("concept", ""),
                    required_inputs,
                    action.get("command", ""),
                    action.get("artifact", ""),
                    action.get("explains", ""),
                ]
            )
        table = _table(
            [
                "Step",
                "Missing diagnostic",
                "Required inputs",
                "Command",
                "Artifact",
                "What it explains",
            ],
            rows,
        )
    else:
        table = '<div class="empty">No missing paper-derived diagnostic actions were found.</div>'
    return _html_page(
        title="Research Evidence Gap Plan",
        subtitle="Copy-paste guide for collecting missing paper-derived evidence.",
        body=[
            _paragraph(plan.get("boundary")),
            table,
            _paragraph(
                "The companion research_gap_commands.ps1 and research_gap_commands.sh files are "
                "review-first scripts. They stop before running commands so placeholders and paths "
                "can be checked."
            ),
        ],
    )


def _render_gap_commands_ps1(plan: JsonDict) -> str:
    lines = [
        "# PromptControlLab research evidence gap commands",
        (
            "# Review this file, replace placeholders, then remove the exit line "
            "and uncomment commands."
        ),
        'Write-Host "Review research_gap_plan.md before running these commands."',
        "exit 1",
        "",
    ]
    for action in _remediation_list(plan.get("actions")):
        lines.extend(_command_comment_block(action, comment="#"))
    return "\n".join(lines)


def _render_gap_commands_sh(plan: JsonDict) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        (
            "# Review this file, replace placeholders, then remove the exit line "
            "and uncomment commands."
        ),
        'echo "Review research_gap_plan.md before running these commands."',
        "exit 1",
        "",
    ]
    for action in _remediation_list(plan.get("actions")):
        lines.extend(_command_comment_block(action, comment="#"))
    return "\n".join(lines)


def _command_comment_block(action: JsonDict, *, comment: str) -> list[str]:
    required = action.get("required_inputs")
    required_inputs = (
        ", ".join(str(item) for item in required) if isinstance(required, list) else ""
    )
    return [
        f"{comment} Step {action.get('step')}: {action.get('concept')}",
        f"{comment} Requires: {required_inputs}",
        f"{comment} Writes: {action.get('artifact')}",
        f"{comment} {action.get('command')}",
        "",
    ]


def _summarize_ecosystem_bundle(*, run_dir: Path, payload: JsonDict) -> JsonDict:
    runs = payload.get("runs")
    rows: list[JsonDict] = []
    if isinstance(runs, list):
        for item in runs:
            if not isinstance(item, dict):
                continue
            tool_dir = _ecosystem_tool_dir(run_dir=run_dir, item=item)
            rows.append(_summarize_external_bundle(run_dir=tool_dir, fallback=item))
    remediation_items: list[JsonDict] = []
    for row in rows:
        remediation_items.extend(_remediation_list(row.get("paper_gap_remediation")))
    remediation = _dedupe_remediation(remediation_items)
    return {
        "tool_count": len(rows),
        "runs": rows,
        "missing_research_diagnostics": sorted(
            {
                str(missing)
                for row in rows
                for missing in row.get("missing_paper_diagnostics", [])
            }
        ),
        "paper_gap_remediation": remediation,
        "review_first": [
            str(row.get("bridge_summary_path"))
            for row in rows
            if row.get("bridge_summary_path")
        ],
    }


def _ecosystem_tool_dir(*, run_dir: Path, item: JsonDict) -> Path:
    out_dir = item.get("out_dir")
    if isinstance(out_dir, str) and out_dir:
        candidate = Path(out_dir)
        if candidate.exists():
            return candidate
    tool = item.get("tool")
    if isinstance(tool, str) and tool:
        return run_dir / tool
    return run_dir


def _summarize_external_bundle(*, run_dir: Path, fallback: JsonDict) -> JsonDict:
    bridge = _read_optional_json(run_dir / "bridge_summary.json")
    claim = _read_optional_json(run_dir / "claim_check.json")
    evidence = _read_optional_json(run_dir / "evidence_card.json")
    validity = _read_optional_json(run_dir / "comparison_validity.json")
    stats = _read_optional_json(run_dir / "stats.json")
    tool = _external_tool_name(bridge=bridge, fallback=fallback)
    coverage = _paper_coverage_rows(run_dir)
    missing_paper_diagnostics = [
        row["concept"]
        for row in coverage
        if row["category"] == "research_diagnostic" and row["status"] == "missing"
    ]
    paper_gap_remediation = [
        row["remediation"]
        for row in coverage
        if row["category"] in {"research_diagnostic", "research_input"}
        and row["status"] == "missing"
        and isinstance(row.get("remediation"), dict)
    ]
    return {
        "tool": tool,
        "display_name": _display_tool_name(tool),
        "run_dir": str(run_dir),
        "validity": bridge.get("validity") or validity.get("validity") or fallback.get("validity"),
        "evidence_tier": bridge.get("evidence_tier")
        or evidence.get("evidence_tier")
        or fallback.get("evidence_tier"),
        "claim_check_status": bridge.get("claim_check_status")
        or claim.get("status")
        or fallback.get("claim_check_status"),
        "recommendation": bridge.get("recommendation") or evidence.get("recommendation"),
        "mean_delta": bridge.get("mean_delta") or _first_stats_comparison(stats).get("mean_delta"),
        "permutation_p_value": bridge.get("permutation_p_value")
        or _first_stats_comparison(stats).get("permutation_p_value"),
        "paper_coverage": coverage,
        "missing_paper_diagnostics": missing_paper_diagnostics,
        "paper_gap_remediation": paper_gap_remediation,
        "missing_evidence": bridge.get("missing_evidence", fallback.get("missing_evidence", [])),
        "next_actions": bridge.get("next_actions", fallback.get("next_actions", [])),
        "bridge_summary_path": str(run_dir / "bridge_summary.html")
        if (run_dir / "bridge_summary.html").exists()
        else str(run_dir / "bridge_summary.md")
        if (run_dir / "bridge_summary.md").exists()
        else fallback.get("bridge_summary_path"),
        "report_html_path": str(run_dir / "report.html")
        if (run_dir / "report.html").exists()
        else fallback.get("report_html_path"),
    }


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _first_stats_comparison(stats: JsonDict) -> JsonDict:
    comparisons = stats.get("comparisons")
    if isinstance(comparisons, list) and comparisons and isinstance(comparisons[0], dict):
        return comparisons[0]
    return stats


def _remediation_list(value: object) -> list[JsonDict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dedupe_remediation(items: list[JsonDict]) -> list[JsonDict]:
    rows = _remediation_list(items)
    seen: set[str] = set()
    deduped: list[JsonDict] = []
    for row in rows:
        concept = str(row.get("concept") or "")
        if not concept or concept in seen:
            continue
        seen.add(concept)
        deduped.append(row)
    return deduped


def _external_tool_name(*, bridge: JsonDict, fallback: JsonDict) -> str:
    for value in [
        fallback.get("tool"),
        bridge.get("requested_tool"),
    ]:
        if isinstance(value, str) and value:
            return value
    detected = bridge.get("detected_tools")
    if isinstance(detected, list) and detected:
        first = detected[0]
        if isinstance(first, str) and first:
            return first
    return "external"


def _display_tool_name(tool: object) -> str:
    names = {
        "promptfoo": "Promptfoo",
        "langfuse": "Langfuse",
        "langsmith": "LangSmith",
        "deepeval": "DeepEval",
    }
    return names.get(str(tool), str(tool))


def _paper_coverage_rows(run_dir: Path) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for item in PAPER_MAPPING:
        artifact = str(item["artifact"])
        present = (run_dir / artifact).exists()
        concept = str(item["concept"])
        row: JsonDict = {
            "concept": concept,
            "artifact": artifact,
            "status": "present" if present else "missing",
            "category": _paper_concept_category(concept),
            "commands": item.get("commands", []),
            "meaning": item.get("meaning", ""),
        }
        if not present:
            remediation = _paper_remediation_for(concept)
            if remediation:
                row["remediation"] = remediation
        rows.append(row)
    return rows


def _paper_concept_category(concept: str) -> str:
    if concept in {
        "soft-to-hard projection gap",
        "hidden-state trajectory",
        "Riccati surrogate",
        "time-varying soft-control lane",
    }:
        return "research_diagnostic"
    if concept == "HuggingFace hidden-state extraction":
        return "research_input"
    return "evidence_protocol"


def _paper_remediation_for(concept: str) -> JsonDict:
    remediation = PAPER_REMEDIATION.get(concept)
    if not isinstance(remediation, dict):
        return {}
    return {"concept": concept, **remediation}


def render_research_diagnostics_markdown(payload: JsonDict) -> str:
    """Render a readable research diagnostics report."""

    diagnostics = payload.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    lines = [
        "# Research Diagnostics Report",
        "",
        "This report summarizes paper-derived PromptControlLab diagnostics.",
        "",
        "## Paper Concept Map",
        "",
        "| Concept | Commands | Artifact | Meaning |",
        "|---|---|---|---|",
    ]
    for item in PAPER_MAPPING:
        lines.append(
            "| {concept} | `{commands}` | `{artifact}` | {meaning} |".format(
                concept=item["concept"],
                commands="`, `".join(item["commands"]),
                artifact=item["artifact"],
                meaning=item["meaning"],
            )
        )
    lines.extend(["", "## Diagnostic Results", ""])
    ecosystem = diagnostics.get("ecosystem_bridge", {})
    if isinstance(ecosystem, dict) and ecosystem:
        lines.extend(
            [
                "### Ecosystem evidence gap diagnosis",
                "",
                (
                    "| Tool | Validity | Evidence tier | Claim check | "
                    "Missing paper diagnostics | Open first |"
                ),
                "|---|---|---|---|---|---|",
            ]
        )
        rows = ecosystem.get("runs")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                missing = row.get("missing_paper_diagnostics", [])
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(row.get("display_name") or row.get("tool")),
                            str(row.get("validity")),
                            str(row.get("evidence_tier")),
                            str(row.get("claim_check_status")),
                            ", ".join(str(item) for item in missing)
                            if isinstance(missing, list)
                            else str(missing),
                            str(row.get("bridge_summary_path") or ""),
                        ]
                    )
                    + " |"
                )
        remediation = ecosystem.get("paper_gap_remediation")
        lines.extend(_render_remediation_table(remediation))
        lines.extend([""])
    external = diagnostics.get("external_bridge", {})
    if isinstance(external, dict) and external:
        lines.extend(
            [
                "### External evidence gap diagnosis",
                "",
                f"- Tool: `{external.get('display_name') or external.get('tool')}`",
                f"- Validity: `{external.get('validity')}`",
                f"- Evidence tier: `{external.get('evidence_tier')}`",
                f"- Claim check: `{external.get('claim_check_status')}`",
                f"- Missing paper diagnostics: `{external.get('missing_paper_diagnostics', [])}`",
                "",
            ]
        )
        lines.extend(_render_remediation_table(external.get("paper_gap_remediation")))
    inputs = payload.get("inputs", {})
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    hidden_input = inputs_dict.get("hidden_states")
    if isinstance(hidden_input, dict):
        lines.extend(
            [
                "### Hidden-state input",
                "",
                f"- Source: `{hidden_input.get('source')}`",
                f"- Path: `{hidden_input.get('path')}`",
                f"- Model id: `{hidden_input.get('model_id')}`",
                f"- States shape: `{hidden_input.get('states_shape')}`",
                f"- Pool: `{hidden_input.get('pool')}`",
                "",
            ]
        )
    soft = diagnostics.get("soft_hard", {})
    if isinstance(soft, dict) and soft:
        lines.extend(
            [
                "### Soft-to-hard projection gap",
                "",
                f"- Risk: `{soft.get('risk')}`",
                f"- Mean projection distance: `{soft.get('mean_projection_distance')}`",
                f"- Max projection distance: `{soft.get('max_projection_distance')}`",
                "",
            ]
        )
    trajectory = diagnostics.get("trajectory", {})
    if isinstance(trajectory, dict) and trajectory:
        lines.extend(
            [
                "### Hidden-state trajectory",
                "",
                f"- Turnpike-like signal: `{trajectory.get('turnpike_like_signal')}`",
                f"- Log-decay slope: `{trajectory.get('log_decay_slope')}`",
                f"- Decay fit R2: `{trajectory.get('decay_r2')}`",
                "",
            ]
        )
    riccati = diagnostics.get("riccati", {})
    if isinstance(riccati, dict) and riccati:
        lines.extend(
            [
                "### Riccati surrogate",
                "",
                f"- Stable surrogate: `{riccati.get('stable_surrogate')}`",
                f"- Closed-loop spectral radius: `{riccati.get('closed_loop_spectral_radius')}`",
                "",
            ]
        )
    tv_soft = diagnostics.get("tv_soft", {})
    if isinstance(tv_soft, dict) and tv_soft:
        lines.extend(
            [
                "### Time-varying soft-control lane",
                "",
                f"- Method means: `{tv_soft.get('method_means')}`",
                f"- Delta vs baseline: `{tv_soft.get('delta_vs_baseline')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def render_research_diagnostics_html(payload: JsonDict) -> str:
    """Render the paper-derived diagnostics summary as browser-friendly HTML."""

    diagnostics = payload.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    body: list[str] = [
        _paragraph("This report summarizes paper-derived PromptControlLab diagnostics."),
        _section(
            "Paper Concept Map",
            _table(
                ["Concept", "Commands", "Artifact", "Meaning"],
                [
                    [
                        item["concept"],
                        ", ".join(str(command) for command in item["commands"]),
                        item["artifact"],
                        item["meaning"],
                    ]
                    for item in PAPER_MAPPING
                ],
            ),
        ),
    ]
    ecosystem = diagnostics.get("ecosystem_bridge", {})
    if isinstance(ecosystem, dict) and ecosystem:
        rows = []
        raw_rows = ecosystem.get("runs")
        if isinstance(raw_rows, list):
            for row in raw_rows:
                if not isinstance(row, dict):
                    continue
                missing = row.get("missing_paper_diagnostics", [])
                rows.append(
                    [
                        row.get("display_name") or row.get("tool", ""),
                        row.get("validity", ""),
                        row.get("evidence_tier", ""),
                        row.get("claim_check_status", ""),
                        ", ".join(str(item) for item in missing)
                        if isinstance(missing, list)
                        else str(missing),
                        row.get("bridge_summary_path", ""),
                    ]
                )
        body.append(
            _section(
                "Ecosystem Evidence Gap Diagnosis",
                _table(
                    [
                        "Tool",
                        "Validity",
                        "Evidence tier",
                        "Claim check",
                        "Missing paper diagnostics",
                        "Open first",
                    ],
                    rows,
                )
                + _render_remediation_html(ecosystem.get("paper_gap_remediation")),
            )
        )
    external = diagnostics.get("external_bridge", {})
    if isinstance(external, dict) and external:
        body.append(
            _section(
                "External Evidence Gap Diagnosis",
                _metric_grid(
                    [
                        ("Tool", external.get("display_name") or external.get("tool", "")),
                        ("Validity", external.get("validity", "")),
                        ("Evidence tier", external.get("evidence_tier", "")),
                        ("Claim check", external.get("claim_check_status", "")),
                        (
                            "Missing diagnostics",
                            ", ".join(
                                str(item)
                                for item in external.get("missing_paper_diagnostics", [])
                            ),
                        ),
                    ]
                )
                + _render_remediation_html(external.get("paper_gap_remediation")),
            )
        )
    inputs = payload.get("inputs", {})
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    hidden_input = inputs_dict.get("hidden_states")
    if isinstance(hidden_input, dict):
        body.append(
            _section(
                "Hidden-state Input",
                _metric_grid(
                    [
                        ("Source", hidden_input.get("source", "")),
                        ("Path", hidden_input.get("path", "")),
                        ("Model id", hidden_input.get("model_id", "")),
                        ("States shape", hidden_input.get("states_shape", "")),
                        ("Pool", hidden_input.get("pool", "")),
                    ]
                ),
            )
        )
    soft = diagnostics.get("soft_hard", {})
    if isinstance(soft, dict) and soft:
        body.append(
            _section(
                "Soft-to-hard Projection Gap",
                _metric_grid(
                    [
                        ("Risk", _badge(str(soft.get("risk", "")))),
                        ("Mean projection distance", soft.get("mean_projection_distance", "")),
                        ("Max projection distance", soft.get("max_projection_distance", "")),
                    ]
                ),
            )
        )
    trajectory = diagnostics.get("trajectory", {})
    if isinstance(trajectory, dict) and trajectory:
        body.append(
            _section(
                "Hidden-state Trajectory",
                _metric_grid(
                    [
                        ("Turnpike-like signal", trajectory.get("turnpike_like_signal", "")),
                        ("Log-decay slope", trajectory.get("log_decay_slope", "")),
                        ("Decay fit R2", trajectory.get("decay_r2", "")),
                    ]
                ),
            )
        )
    riccati = diagnostics.get("riccati", {})
    if isinstance(riccati, dict) and riccati:
        body.append(
            _section(
                "Riccati Surrogate",
                _metric_grid(
                    [
                        ("Stable surrogate", riccati.get("stable_surrogate", "")),
                        (
                            "Closed-loop spectral radius",
                            riccati.get("closed_loop_spectral_radius", ""),
                        ),
                    ]
                ),
            )
        )
    tv_soft = diagnostics.get("tv_soft", {})
    if isinstance(tv_soft, dict) and tv_soft:
        body.append(
            _section(
                "Time-varying Soft-control Lane",
                _metric_grid(
                    [
                        ("Method means", tv_soft.get("method_means", "")),
                        ("Delta vs baseline", tv_soft.get("delta_vs_baseline", "")),
                    ]
                ),
            )
        )
    body.append(_section("Boundary", _paragraph(payload.get("boundary"))))
    return _html_page(
        title="Research Diagnostics Report",
        subtitle="Paper-derived prompt optimization diagnostics.",
        body=body,
    )


def _render_remediation_table(value: object) -> list[str]:
    rows = _remediation_list(value)
    if not rows:
        return []
    lines = [
        "",
        "#### How to close these gaps",
        "",
        "| Missing diagnostic | Required inputs | Command | Artifact | What it explains |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        required = row.get("required_inputs")
        required_inputs = (
            ", ".join(str(item) for item in required) if isinstance(required, list) else ""
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("concept", "")),
                    required_inputs,
                    f"`{row.get('command', '')}`",
                    f"`{row.get('artifact', '')}`",
                    str(row.get("explains", "")),
                ]
            )
            + " |"
        )
    return lines


def _render_remediation_html(value: object) -> str:
    rows = _remediation_list(value)
    if not rows:
        return ""
    table_rows = []
    for row in rows:
        required = row.get("required_inputs")
        required_inputs = (
            ", ".join(str(item) for item in required) if isinstance(required, list) else ""
        )
        table_rows.append(
            [
                row.get("concept", ""),
                required_inputs,
                row.get("command", ""),
                row.get("artifact", ""),
                row.get("explains", ""),
            ]
        )
    return (
        '<h3 class="subhead">How to close these gaps</h3>'
        + _table(
            ["Missing diagnostic", "Required inputs", "Command", "Artifact", "What it explains"],
            table_rows,
        )
    )


def _html_page(*, title: str, subtitle: str, body: list[str]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html_text(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #61708a;
      --line: #d8e0ec;
      --panel: #ffffff;
      --bg: #f6f8fb;
      --accent: #2463eb;
      --good-bg: #dcfce7;
      --good: #166534;
      --warn-bg: #fef3c7;
      --warn: #92400e;
      --bad-bg: #fee2e2;
      --bad: #991b1b;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px 56px; }}
    .hero {{
      background: linear-gradient(135deg, #ffffff, #edf4ff);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 28px 30px;
      box-shadow: 0 14px 40px rgba(25, 42, 70, 0.08);
    }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 16px; font-size: 22px; }}
    .subtitle {{ color: var(--muted); font-size: 16px; }}
    section {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 22px;
      overflow: hidden;
    }}
    .subhead {{ margin: 18px 0 10px; font-size: 17px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      background: #fbfdff;
    }}
    .metric .label {{ color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
    .metric .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{
      padding: 11px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f1f5fb;
      font-size: 12px;
      text-transform: uppercase;
      color: #44536a;
      letter-spacing: .04em;
    }}
    code {{ background: #eef2f7; border-radius: 6px; padding: 2px 5px; overflow-wrap: anywhere; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 9px;
      font-weight: 700;
      font-size: 12px;
    }}
    .good {{ background: var(--good-bg); color: var(--good); }}
    .warn {{ background: var(--warn-bg); color: var(--warn); }}
    .bad {{ background: var(--bad-bg); color: var(--bad); }}
    .neutral {{ background: #e2e8f0; color: #334155; }}
    .empty {{
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 12px;
      padding: 16px;
    }}
    p {{ margin: 0 0 10px; }}
  </style>
</head>
<body>
<main>
  <div class="hero">
    <h1>{_html_text(title)}</h1>
    <div class="subtitle">{_html_text(subtitle)}</div>
  </div>
  {''.join(body)}
</main>
</body>
</html>
"""


def _section(title: str, body: str) -> str:
    return f"<section><h2>{_html_text(title)}</h2>{body}</section>"


def _metric_grid(items: list[tuple[str, object]]) -> str:
    cells = []
    for label, value in items:
        rendered = str(value) if _is_safe_html(value) else _html_text(_format_value(value))
        cells.append(
            '<div class="metric">'
            f'<div class="label">{_html_text(label)}</div>'
            f'<div class="value">{rendered}</div>'
            "</div>"
        )
    return '<div class="grid">' + "".join(cells) + "</div>"


def _table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return '<div class="empty">No rows recorded.</div>'
    header_html = "".join(f"<th>{_html_text(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        cells = []
        for value in row:
            rendered = str(value) if _is_safe_html(value) else _html_text(_format_value(value))
            cells.append(f"<td>{rendered}</td>")
        row_html.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div style="overflow-x:auto"><table><thead><tr>'
        + header_html
        + "</tr></thead><tbody>"
        + "".join(row_html)
        + "</tbody></table></div>"
    )


def _paragraph(value: object) -> str:
    text = _format_value(value)
    return f"<p>{_html_text(text)}</p>" if text else ""


def _badge(value: str) -> str:
    lower = value.lower()
    if lower in {"pass", "passed", "present", "complete", "clean", "low", "supported", "true"}:
        css = "good"
    elif lower in {"fail", "failed", "missing", "high", "needs_work", "blocked", "false"}:
        css = "bad"
    elif lower in {"needs_review", "medium", "warning", "not_checked", "unknown"}:
        css = "warn"
    else:
        css = "neutral"
    return f'<span class="badge {css}">{_html_text(value)}</span>'


def _is_safe_html(value: object) -> bool:
    return isinstance(value, str) and (
        value.startswith('<span class="badge ') or value.startswith('<a href="')
    )


def _format_value(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))


def _html_attr(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _research_input_summary(paths: ResearchPaths) -> JsonDict:
    inputs: JsonDict = {}
    if paths.states_path is not None:
        inputs["hidden_states"] = _hidden_state_input_summary(paths.states_path)
    return inputs


def _hidden_state_input_summary(states_path: Path) -> JsonDict:
    metadata_path = Path(str(states_path) + ".metadata.json")
    if metadata_path.exists():
        metadata = read_json(metadata_path)
        return {
            "path": str(states_path),
            "metadata_path": str(metadata_path),
            "source": _hidden_source(metadata),
            "kind": metadata.get("kind"),
            "model_id": metadata.get("model_id"),
            "states_shape": metadata.get("states_shape"),
            "layer": metadata.get("layer"),
            "pool": metadata.get("pool"),
            "prompt_count": metadata.get("prompt_count"),
            "boundary": metadata.get("boundary"),
        }
    return {
        "path": str(states_path),
        "metadata_path": None,
        "source": "provided_npz",
        "kind": "hidden_states_npz",
        "model_id": None,
        "states_shape": _npz_states_shape(states_path),
        "layer": None,
        "pool": "unknown",
        "prompt_count": None,
        "boundary": (
            "Hidden states were provided without extraction metadata. Trajectory/Riccati "
            "diagnostics can run, but model id, layer, and pooling provenance are unknown."
        ),
    }


def _hidden_source(metadata: JsonDict) -> str:
    source = metadata.get("source")
    if isinstance(source, str) and source:
        return source
    kind = metadata.get("kind")
    if kind == "hidden_state_extraction":
        return "huggingface_extraction"
    if isinstance(kind, str) and kind:
        return kind
    return "metadata"


def _npz_states_shape(states_path: Path) -> list[int] | None:
    np = cast(Any, require_module("numpy", feature="research diagnostics", extra="research"))
    with np.load(states_path) as data:
        if "states" not in data:
            return None
        states = data["states"]
        return [int(value) for value in states.shape]


def _resolve_research_paths(
    *,
    run_dir: Path | None,
    soft_path: Path | None,
    vocab_path: Path | None,
    states_path: Path | None,
    matrices_path: Path | None,
    tv_predictions_path: Path | None,
    diagnostics_dir: Path | None,
    summary_dir: Path | None,
) -> ResearchPaths:
    input_dir = run_dir / "inputs" if run_dir is not None else None
    resolved_diagnostics = diagnostics_dir or (run_dir / "diagnostics" if run_dir else None)
    if resolved_diagnostics is None:
        resolved_diagnostics = Path("diagnostics")
    resolved_summary = summary_dir or (run_dir if run_dir is not None else resolved_diagnostics)
    return ResearchPaths(
        soft_path=_existing_or_explicit(soft_path, input_dir, "soft_prompt.npz"),
        vocab_path=_existing_or_explicit(vocab_path, input_dir, "vocab_embeddings.npz"),
        states_path=_existing_or_explicit(states_path, input_dir, "hidden_states.npz"),
        matrices_path=_existing_or_explicit(matrices_path, input_dir, "surrogate_mats.npz"),
        tv_predictions_path=_existing_or_explicit(
            tv_predictions_path,
            input_dir,
            "method_predictions.jsonl",
        ),
        diagnostics_dir=resolved_diagnostics,
        summary_dir=resolved_summary,
    )


def _existing_or_explicit(path: Path | None, input_dir: Path | None, filename: str) -> Path | None:
    if path is not None:
        return path
    if input_dir is None:
        return None
    candidate = input_dir / filename
    return candidate if candidate.exists() else None


def _demo_method_predictions() -> list[JsonDict]:
    records: list[JsonDict] = []
    scores = {
        "static": [0.55, 0.60, 0.50],
        "time_varying": [0.82, 0.88, 0.80],
        "shuffled_tv": [0.58, 0.57, 0.54],
        "random_tv": [0.42, 0.45, 0.40],
    }
    for method, method_scores in scores.items():
        for index, score in enumerate(method_scores, start=1):
            records.append(
                {
                    "id": f"{method}-{index}",
                    "output": "ok",
                    "expected": "ok",
                    "score": score,
                    "slice": "synthetic",
                    "method": method,
                }
            )
    return records


def _interpret_diagnostics(diagnostics: JsonDict) -> list[str]:
    interpretations: list[str] = []
    soft = diagnostics.get("soft_hard")
    if isinstance(soft, dict):
        interpretations.append(
            f"Soft-to-hard projection risk is {soft.get('risk')} with mean distance "
            f"{soft.get('mean_projection_distance')}."
        )
    trajectory = diagnostics.get("trajectory")
    if isinstance(trajectory, dict):
        interpretations.append(
            "Trajectory turnpike-like signal is "
            f"{trajectory.get('turnpike_like_signal')} with log-decay slope "
            f"{trajectory.get('log_decay_slope')}."
        )
    riccati = diagnostics.get("riccati")
    if isinstance(riccati, dict):
        interpretations.append(
            "Riccati surrogate stable="
            f"{riccati.get('stable_surrogate')} with spectral radius "
            f"{riccati.get('closed_loop_spectral_radius')}."
        )
    tv_soft = diagnostics.get("tv_soft")
    if isinstance(tv_soft, dict):
        interpretations.append(
            "Time-varying soft-control comparison recorded method means and deltas vs baseline."
        )
    return interpretations
