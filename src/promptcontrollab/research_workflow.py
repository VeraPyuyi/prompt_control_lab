"""One-command research workflows for paper-derived diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from promptcontrollab.evidence_card import write_evidence_card
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json, write_jsonl
from promptcontrollab.optional import require_module
from promptcontrollab.riccati import analyze_riccati
from promptcontrollab.soft_hard import analyze_soft_hard
from promptcontrollab.trajectory import analyze_trajectory
from promptcontrollab.tv_soft import summarize_tv_soft

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
    ensure_dir(paths.summary_dir)
    write_json(paths.summary_dir / "research_diagnostics.json", payload)
    (paths.summary_dir / "research_diagnostics.md").write_text(
        render_research_diagnostics_markdown(payload),
        encoding="utf-8",
    )
    write_evidence_card(paths.summary_dir)
    return payload


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
    if isinstance(soft, dict):
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
    if isinstance(trajectory, dict):
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
    if isinstance(riccati, dict):
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
    if isinstance(tv_soft, dict):
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
