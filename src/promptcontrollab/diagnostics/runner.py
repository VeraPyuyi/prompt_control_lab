"""Execute reproducible research diagnostic workflows and write their artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from promptcontrollab.audit.claim_check import run_claim_check
from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json, write_jsonl
from promptcontrollab.core.optional import require_module
from promptcontrollab.core.version import __version__
from promptcontrollab.diagnostics.bundle import (
    _summarize_ecosystem_bundle,
    _summarize_external_bundle,
    write_research_bundle_index,
)
from promptcontrollab.diagnostics.constants import PAPER_MAPPING
from promptcontrollab.diagnostics.gap import _build_research_gap_plan
from promptcontrollab.diagnostics.gap_renderers import (
    _render_gap_commands_ps1,
    _render_gap_commands_sh,
    _render_research_gap_plan_markdown,
    render_research_gap_plan_html,
)
from promptcontrollab.diagnostics.green_certificate import analyze_green_certificate
from promptcontrollab.diagnostics.interpretation import (
    _interpret_diagnostics,
    _plain_language_research_insights,
    _research_at_a_glance,
)
from promptcontrollab.diagnostics.models import ResearchPaths
from promptcontrollab.diagnostics.posterior_certificate import analyze_posterior_certificate
from promptcontrollab.diagnostics.renderers import (
    render_research_diagnostics_html,
    render_research_diagnostics_markdown,
    render_research_overview_svg,
)
from promptcontrollab.diagnostics.riccati import analyze_riccati
from promptcontrollab.diagnostics.soft_hard import analyze_soft_hard
from promptcontrollab.diagnostics.terminal_sensitivity import analyze_terminal_sensitivity
from promptcontrollab.diagnostics.trajectory import analyze_trajectory
from promptcontrollab.diagnostics.tv_soft import summarize_tv_soft
from promptcontrollab.evaluation.evaluation import run_import_eval
from promptcontrollab.evaluation.splitting import load_tasks, make_split, write_split
from promptcontrollab.evaluation.statistics import compare_prediction_files
from promptcontrollab.evaluation.validity import run_comparison_validity
from promptcontrollab.evidence_card import write_evidence_card


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
    terminal_surrogate_path = inputs_dir / "terminal_surrogate.npz"
    green_surrogate_path = inputs_dir / "green_surrogate.npz"
    green_premises_path = inputs_dir / "green_premises.json"
    posterior_bounds_path = inputs_dir / "posterior_bounds.json"
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
    hyperbolic = np.diag([0.5, 2.0])
    boundary_start = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=float)
    boundary_terminal = np.array([[0.0, 0.0], [0.0, 1.0]], dtype=float)
    np.savez(
        terminal_surrogate_path,
        M=hyperbolic,
        B0=boundary_start,
        BN=boundary_terminal,
        terminal_perturbations=np.array([[0.0, 1.0]], dtype=float),
        control_readout=np.array([[0.0, 1.0]], dtype=float),
    )
    np.savez(
        green_surrogate_path,
        M=hyperbolic,
        B0=boundary_start,
        BN=boundary_terminal,
        graph_S=np.array([[0.0]], dtype=float),
    )
    write_json(
        green_premises_path,
        {
            "schema": "prompt_control_lab.green_premises.v1",
            "source_kind": "synthetic_demo",
            "scope": "synthetic two-dimensional research-demo surrogate",
            "fixed_dimension": True,
            "existing_local_branch": True,
            "interior_control": True,
            "uniform_c3_neighborhood": False,
            "provenance": {
                "kind": "synthetic_fixture",
                "conservative": False,
                "source": "pcl research-demo",
            },
        },
    )
    write_json(
        posterior_bounds_path,
        {
            "schema": "prompt_control_lab.posterior_bounds.v1",
            "residual_norm_upper": 0.05,
            "jacobian_inverse_norm_upper": 1.0,
            "jacobian_lipschitz_upper": 1.0,
            "neighborhood_radius": 0.5,
            "bound_provenance": {
                "kind": "estimated_bounds",
                "conservative": False,
                "scope": "synthetic two-dimensional research-demo surrogate",
                "source": "pcl research-demo",
            },
        },
    )
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
            "control_certificates": (
                "Synthetic low-dimensional examples only; they do not certify an operational "
                "language model."
            ),
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
        terminal_surrogate_path=terminal_surrogate_path,
        green_surrogate_path=green_surrogate_path,
        green_premises_path=green_premises_path,
        posterior_bounds_path=posterior_bounds_path,
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
    terminal_records_path: Path | None = None,
    terminal_surrogate_path: Path | None = None,
    green_surrogate_path: Path | None = None,
    green_premises_path: Path | None = None,
    posterior_bounds_path: Path | None = None,
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
        terminal_records_path=terminal_records_path,
        terminal_surrogate_path=terminal_surrogate_path,
        green_surrogate_path=green_surrogate_path,
        green_premises_path=green_premises_path,
        posterior_bounds_path=posterior_bounds_path,
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

    if paths.terminal_records_path is not None or paths.terminal_surrogate_path is not None:
        diagnostics["terminal_sensitivity"] = analyze_terminal_sensitivity(
            records_path=paths.terminal_records_path,
            surrogate_path=paths.terminal_surrogate_path,
            horizons=[16, 32, 64] if paths.terminal_surrogate_path is not None else None,
            early_steps=[0, 1] if paths.terminal_surrogate_path is not None else None,
            out_dir=paths.diagnostics_dir,
        )
        artifacts["terminal_sensitivity"] = str(
            paths.diagnostics_dir / "terminal_sensitivity.json"
        )

    if paths.green_surrogate_path is not None:
        diagnostics["green_certificate"] = analyze_green_certificate(
            surrogate_path=paths.green_surrogate_path,
            horizons=[16, 32, 64],
            premises_path=paths.green_premises_path,
            out_dir=paths.diagnostics_dir,
        )
        artifacts["green_certificate"] = str(
            paths.diagnostics_dir / "green_certificate.json"
        )

    if paths.posterior_bounds_path is not None:
        diagnostics["posterior_certificate"] = analyze_posterior_certificate(
            input_path=paths.posterior_bounds_path,
            out_dir=paths.diagnostics_dir,
        )
        artifacts["posterior_certificate"] = str(
            paths.diagnostics_dir / "posterior_certificate.json"
        )

    for name in ("terminal_sensitivity", "green_certificate", "posterior_certificate"):
        artifact_path = paths.diagnostics_dir / f"{name}.json"
        if name not in diagnostics and artifact_path.is_file():
            diagnostics[name] = read_json(artifact_path)
            artifacts[name] = str(artifact_path)

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
    _write_research_outputs(summary_dir=paths.summary_dir, payload=payload)
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
    payload["plain_language_insights"] = _plain_language_research_insights(payload)
    payload["at_a_glance"] = _research_at_a_glance(payload, summary_dir=summary_dir)
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
    overview_svg = summary_dir / "research_overview.svg"
    artifacts_dict["research_overview_svg"] = str(overview_svg)
    payload["artifacts"] = artifacts_dict
    overview_svg.write_text(render_research_overview_svg(payload), encoding="utf-8")
    write_json(summary_dir / "research_diagnostics.json", payload)
    (summary_dir / "research_diagnostics.md").write_text(
        render_research_diagnostics_markdown(payload),
        encoding="utf-8",
    )
    diagnostics_html.write_text(render_research_diagnostics_html(payload), encoding="utf-8")
    write_research_bundle_index(summary_dir)


def _research_input_summary(paths: ResearchPaths) -> JsonDict:
    inputs: JsonDict = {}
    if paths.states_path is not None:
        inputs["hidden_states"] = _hidden_state_input_summary(paths.states_path)
    for key, path in (
        ("terminal_records", paths.terminal_records_path),
        ("terminal_surrogate", paths.terminal_surrogate_path),
        ("green_surrogate", paths.green_surrogate_path),
        ("green_premises", paths.green_premises_path),
        ("posterior_bounds", paths.posterior_bounds_path),
    ):
        if path is not None:
            inputs[key] = {"path": str(path), "source": "provided_or_discovered"}
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
    terminal_records_path: Path | None,
    terminal_surrogate_path: Path | None,
    green_surrogate_path: Path | None,
    green_premises_path: Path | None,
    posterior_bounds_path: Path | None,
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
        terminal_records_path=_existing_or_explicit(
            terminal_records_path,
            input_dir,
            "terminal_interventions.jsonl",
        ),
        terminal_surrogate_path=_existing_or_explicit(
            terminal_surrogate_path,
            input_dir,
            "terminal_surrogate.npz",
        ),
        green_surrogate_path=_existing_or_explicit(
            green_surrogate_path,
            input_dir,
            "green_surrogate.npz",
        ),
        green_premises_path=_existing_or_explicit(
            green_premises_path,
            input_dir,
            "green_premises.json",
        ),
        posterior_bounds_path=_existing_or_explicit(
            posterior_bounds_path,
            input_dir,
            "posterior_bounds.json",
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
