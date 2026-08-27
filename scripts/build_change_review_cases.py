"""Build public-safe Change Review cases from existing real aggregate artifacts."""

# ruff: noqa: E402, RUF001

from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from promptcontrollab.control.control_protocol import ControlEvent
from promptcontrollab.core.files import JsonDict, read_json, write_json, write_jsonl
from promptcontrollab.evaluation.change_review import review_changes

_MODEL_BASELINE = "Qwen/Qwen2.5-7B-Instruct"
_MODEL_CANDIDATE = "mistralai/Mistral-7B-Instruct-v0.3"


def main() -> int:
    """Build the three public-safe flagship Change Review cases."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint-source",
        type=Path,
        default=REPO_ROOT / "docs" / "case_studies" / "sft_checkpoint_pilot",
    )
    parser.add_argument(
        "--checkpoint-out",
        type=Path,
        default=REPO_ROOT / "docs" / "case_studies" / "checkpoint_change_review",
    )
    parser.add_argument(
        "--agent-source",
        type=Path,
        default=REPO_ROOT / "docs" / "case_studies" / "agent_change_review" / "pilot.csv",
    )
    parser.add_argument(
        "--agent-out",
        type=Path,
        default=REPO_ROOT / "docs" / "case_studies" / "agent_change_review",
    )
    parser.add_argument(
        "--model-source",
        type=Path,
        default=(REPO_ROOT / "docs" / "case_studies" / "peoc_real" / "research_case_study.json"),
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=REPO_ROOT / "docs" / "case_studies" / "model_change_review",
    )
    args = parser.parse_args()
    build_checkpoint_case(source_dir=args.checkpoint_source, out_dir=args.checkpoint_out)
    print(f"Wrote checkpoint Change Review to {args.checkpoint_out}")
    if args.agent_source.is_file():
        build_agent_case(pilot_csv=args.agent_source, out_dir=args.agent_out)
        print(f"Wrote Agent execution Change Review to {args.agent_out}")
    build_model_case(source_case=args.model_source, out_dir=args.model_out)
    print(f"Wrote model Change Review to {args.model_out}")
    return 0


def build_checkpoint_case(*, source_dir: Path, out_dir: Path) -> JsonDict:
    """Build a three-seed initial-to-final review from the published pilot table."""

    rows = _read_csv(source_dir / "checkpoint_metrics.csv")
    provenance = read_json(source_dir / "provenance.json")
    decisions = read_json(source_dir / "gate_decisions.json")
    initial = [row for row in rows if row.get("stage") == "initial"]
    final = [row for row in rows if row.get("stage") == "final"]
    if len(initial) != 3 or len(final) != 3:
        raise ValueError("Checkpoint case requires exactly three initial and three final rows")
    _clear_generated_case_artifacts(out_dir)
    baseline = out_dir / "baseline"
    candidate = out_dir / "candidate"
    baseline.mkdir(parents=True)
    candidate.mkdir(parents=True)
    split_hash = str(provenance.get("split_sha256") or "")
    model_value = provenance.get("model")
    model = model_value if isinstance(model_value, dict) else {}
    shared: JsonDict = {
        "schema": "prompt_control_lab.public_checkpoint_run.v1",
        "agent": "pcl-posttrain-pilot",
        "metric": "withheld_exact_match",
        "prompt": {"prompt_hash": "recorded-shared-evaluation-prompt"},
        "model": {
            "provider": "huggingface",
            "model_id": model.get("id"),
            "revision": model.get("revision"),
        },
        "split_hash": split_hash,
        "evidence_origin": "real_three_seed_sft_pilot",
        "claim_boundary": (
            "This aggregate comparison preserves the real pilot observations. It does not "
            "establish a unique causal training mechanism."
        ),
    }
    write_json(
        baseline / "manifest.json",
        {**shared, "checkpoint": {"checkpoint_id": "aggregate-initial", "stage": "initial"}},
    )
    write_json(
        candidate / "manifest.json",
        {**shared, "checkpoint": {"checkpoint_id": "aggregate-final", "stage": "final"}},
    )
    write_json(baseline / "metrics.json", _checkpoint_metrics(initial))
    write_json(candidate / "metrics.json", _checkpoint_metrics(final))
    overall_decision = str(decisions.get("decision") or "insufficient_evidence")
    write_json(
        candidate / "posttrain_gate.json",
        {
            "schema": "prompt_control_lab.public_checkpoint_gate.v1",
            "decision": overall_decision,
            "plain_summary": (
                "The candidate improved mean score, while the recorded generation, stability, "
                "and selective-risk checks still required a hold."
            ),
            "source": "../sft_checkpoint_pilot/gate_decisions.json",
        },
    )
    review = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=out_dir / "review",
        kind="auto",
        mode="shadow",
    )
    review["baseline_run"] = "../baseline"
    review["candidate_run"] = "../candidate"
    write_json(out_dir / "review" / "change_review.json", review)
    case: JsonDict = {
        "schema": "prompt_control_lab.checkpoint_change_review_case.v1",
        "source": "../sft_checkpoint_pilot/checkpoint_metrics.csv",
        "seed_count": 3,
        "checkpoint_count": 9,
        "comparison": "aggregate_initial_to_final",
        "decision": review["decision"],
        "observed": {
            "baseline_mean_score": _mean(initial, "mean_score"),
            "candidate_mean_score": _mean(final, "mean_score"),
            "candidate_generation_mismatch": _mean(final, "generation_mismatch"),
            "candidate_selective_aurc": _mean(final, "selective_aurc"),
            "candidate_trajectory_drift": _mean(final, "trajectory_drift"),
        },
        "claim_boundary": shared["claim_boundary"],
        "next_action": review["next_action"],
        "display": {
            "featured": True,
            "order": 3,
            "category": "checkpoint",
            "evidence_level": "real_three_seed_pilot",
            "review_path": "review",
            "technical_change_kind": "checkpoint_change",
            "title": {
                "en": "Checkpoint promotion review",
                "zh": "Checkpoint 发布审查",
            },
            "summary": {
                "en": (
                    "Compare initial and final checkpoints across three seeds and nine "
                    "recorded checkpoints."
                ),
                "zh": "比较三个 Seed、九个已记录 Checkpoint 的初始与最终状态。",
            },
            "boundary": {
                "en": (
                    "A higher aggregate score does not override the recorded stability, "
                    "generation-mismatch, or selective-risk hold signals."
                ),
                "zh": "总体分数提高不能覆盖已记录的稳定性、生成错配和选择性风险阻断项。",
            },
        },
    }
    write_json(out_dir / "case_manifest.json", case)
    return case


def build_agent_case(*, pilot_csv: Path, out_dir: Path) -> JsonDict:
    """Build a public prompt-change review from repeated real Agent executions.

    The source rows must come from actual Agent processes. The generated case keeps only
    aggregate execution signals and deterministic events; raw logs and temporary repositories
    remain outside the public case.
    """

    rows = _read_csv(pilot_csv)
    if not rows:
        raise ValueError("Agent Change Review requires at least one paired execution row")
    _clear_generated_case_artifacts(out_dir)
    baseline = out_dir / "baseline"
    candidate = out_dir / "candidate"
    baseline.mkdir(parents=True)
    candidate.mkdir(parents=True)
    agent_names = sorted({str(row.get("agent") or "unknown") for row in rows})
    shared: JsonDict = {
        "schema": "prompt_control_lab.public_agent_execution_run.v1",
        "agent": {"name": agent_names[0] if len(agent_names) == 1 else "mixed"},
        "metric": "paired_task_success",
        "split_hash": "controlled-coding-fixtures-v1",
        "evidence_origin": "real_repeated_agent_processes",
        "capture": "aggregate_public_safe",
        "claim_boundary": (
            "These are real Agent executions on controlled coding fixtures. They do not "
            "establish performance on production repositories or other Agent versions."
        ),
    }
    write_json(
        baseline / "manifest.json",
        {**shared, "run_id": "agent-pilot-raw", "prompt": {"prompt_hash": "raw-set-v1"}},
    )
    write_json(
        candidate / "manifest.json",
        {
            **shared,
            "run_id": "agent-pilot-guarded",
            "prompt": {"prompt_hash": "guarded-set-v1"},
        },
    )
    write_json(baseline / "metrics.json", _agent_metrics(rows, side="raw"))
    write_json(candidate / "metrics.json", _agent_metrics(rows, side="guarded"))
    write_jsonl(baseline / "events.jsonl", _agent_events(rows, side="raw"))
    write_jsonl(candidate / "events.jsonl", _agent_events(rows, side="guarded"))

    review = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=out_dir / "review",
        kind="auto",
        mode="shadow",
    )
    review["baseline_run"] = "../baseline"
    review["candidate_run"] = "../candidate"
    write_json(out_dir / "review" / "change_review.json", review)
    raw_metrics = _agent_metrics(rows, side="raw")
    guarded_metrics = _agent_metrics(rows, side="guarded")
    _write_agent_comparison_svg(
        out_dir / "comparison.en.svg",
        raw_metrics=raw_metrics,
        guarded_metrics=guarded_metrics,
        language="en",
    )
    _write_agent_comparison_svg(
        out_dir / "comparison.zh.svg",
        raw_metrics=raw_metrics,
        guarded_metrics=guarded_metrics,
        language="zh",
    )
    case: JsonDict = {
        "schema": "prompt_control_lab.agent_change_review_case.v1",
        "comparison": "raw_prompt_to_guarded_prompt",
        "task_count": len({str(row.get("base_task_id") or "") for row in rows}),
        "paired_rows": len(rows),
        "execution_count": len(rows) * 2,
        "decision": review["decision"],
        "observed": {
            "raw_success_rate": raw_metrics["mean_score"],
            "guarded_success_rate": guarded_metrics["mean_score"],
            "raw_mean_total_tokens": raw_metrics["mean_total_tokens"],
            "guarded_mean_total_tokens": guarded_metrics["mean_total_tokens"],
            "raw_mean_tool_calls": raw_metrics["mean_tool_calls"],
            "guarded_mean_tool_calls": guarded_metrics["mean_tool_calls"],
            "raw_mean_touched_files": raw_metrics["mean_touched_files"],
            "guarded_mean_touched_files": guarded_metrics["mean_touched_files"],
        },
        "claim_boundary": shared["claim_boundary"],
        "next_action": review["next_action"],
        "display": {
            "featured": True,
            "order": 1,
            "category": "agent",
            "evidence_level": "real_repeated_runs",
            "review_path": "review",
            "technical_change_kind": "prompt_change",
            "title": {
                "en": "Agent workflow optimization",
                "zh": "Agent 运行优化",
            },
            "summary": {
                "en": (
                    "Compare 60 real Codex executions across ten controlled tasks and "
                    "three repeated trials."
                ),
                "zh": "比较十个受控任务、三次重复中的 60 次真实 Codex 执行。",
            },
            "boundary": {
                "en": (
                    "This is a prompt change within the same Agent, not a comparison of "
                    "two Agent identities or production repositories."
                ),
                "zh": "这是同一 Agent 下的 Prompt 变更，不是两个 Agent 身份或生产仓库的比较。",
            },
        },
    }
    write_json(out_dir / "case_manifest.json", case)
    return case


def build_model_case(*, source_case: Path, out_dir: Path) -> JsonDict:
    """Build a bounded cross-model review from real historical aggregate cells.

    The source contains repeated aggregate cells rather than paired per-example records.
    This builder therefore reports descriptive model and slice differences, forces human
    review, and intentionally omits significance tests.
    """

    source = read_json(source_case)
    raw_rows = source.get("hard_method_rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("Model case source must contain non-empty `hard_method_rows`")
    rows = [dict(row) for row in raw_rows if isinstance(row, dict)]
    if len(rows) != len(raw_rows):
        raise ValueError("Every model case source row must be a JSON object")
    source_models = sorted({str(row.get("model") or "") for row in rows})
    baseline_rows = [row for row in rows if row.get("model") == _MODEL_BASELINE]
    candidate_rows = [row for row in rows if row.get("model") == _MODEL_CANDIDATE]
    _validate_model_grid(baseline_rows, candidate_rows)

    _clear_generated_case_artifacts(out_dir)
    baseline = out_dir / "baseline"
    candidate = out_dir / "candidate"
    baseline.mkdir(parents=True)
    candidate.mkdir(parents=True)
    tasks = sorted({str(row["task"]) for row in baseline_rows})
    methods = sorted({str(row["method"]) for row in baseline_rows})
    shared: JsonDict = {
        "schema": "prompt_control_lab.public_model_aggregate_run.v1",
        "agent": "pcl-evidence-import",
        "metric": "acc_hard_test",
        "split_hash": "peoc-hard-test-aggregate-grid-v1",
        "evidence_origin": "real_historical_aggregate",
        "capture": "aggregate_public_safe",
        "claim_boundary": (
            "These historical aggregate cells describe an association between recorded model "
            "identity and outcomes. They do not provide paired per-example significance, a "
            "verified shared prompt identity, or unique causal attribution."
        ),
    }
    write_json(
        baseline / "manifest.json",
        {
            **shared,
            "run_id": "historical-qwen-aggregate",
            "model": {"provider": "huggingface", "model_id": _MODEL_BASELINE},
        },
    )
    write_json(
        candidate / "manifest.json",
        {
            **shared,
            "run_id": "historical-mistral-aggregate",
            "model": {"provider": "huggingface", "model_id": _MODEL_CANDIDATE},
        },
    )
    baseline_metrics = _model_metrics(baseline_rows)
    candidate_metrics = _model_metrics(candidate_rows)
    write_json(baseline / "metrics.json", baseline_metrics)
    write_json(candidate / "metrics.json", candidate_metrics)
    write_json(
        candidate / "gate_result.json",
        {
            "schema": "prompt_control_lab.gate_result.v1",
            "status": "needs_review",
            "plain_summary": (
                "Historical aggregate evidence lacks paired per-example records and a shared "
                "recorded prompt identity. Collect a controlled paired model run before promotion."
            ),
            "warnings": [
                "No paired per-example evidence was recorded.",
                "A common prompt hash was not recorded for both model aggregates.",
            ],
        },
    )
    review = review_changes(
        baseline_dir=baseline,
        candidate_dir=candidate,
        out_dir=out_dir / "review",
        kind="auto",
        mode="shadow",
    )
    review["baseline_run"] = "../baseline"
    review["candidate_run"] = "../candidate"
    write_json(out_dir / "review" / "change_review.json", review)
    _write_model_comparison_csv(
        out_dir / "comparison.csv",
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
    )
    _write_model_comparison_svg(
        out_dir / "comparison.en.svg",
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        language="en",
    )
    _write_model_comparison_svg(
        out_dir / "comparison.zh.svg",
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
        language="zh",
    )
    case: JsonDict = {
        "schema": "prompt_control_lab.model_change_review_case.v1",
        "source": "../peoc_real/research_case_study.json",
        "source_model_count": len(source_models),
        "task_count": len(tasks),
        "method_count": len(methods),
        "aggregation_units_per_model": len(baseline_rows),
        "source_replicates_per_model": sum(int(row["n"]) for row in baseline_rows),
        "baseline_model": _MODEL_BASELINE,
        "candidate_model": _MODEL_CANDIDATE,
        "decision": review["decision"],
        "observed": {
            "baseline_mean_score": baseline_metrics["mean_score"],
            "candidate_mean_score": candidate_metrics["mean_score"],
            "baseline_by_slice": baseline_metrics["by_slice"],
            "candidate_by_slice": candidate_metrics["by_slice"],
        },
        "claim_boundary": shared["claim_boundary"],
        "next_action": (
            "Run both models on the same per-example task set with three repetitions and "
            "record the prompt identity before making a promotion decision."
        ),
        "display": {
            "featured": True,
            "order": 2,
            "category": "model",
            "evidence_level": "historical_aggregate",
            "review_path": "review",
            "technical_change_kind": "model_change",
            "title": {"en": "Model change review", "zh": "模型切换审查"},
            "summary": {
                "en": (
                    "Compare Qwen2.5-7B and Mistral-7B across the same four tasks and "
                    "six recorded methods."
                ),
                "zh": "比较 Qwen2.5-7B 与 Mistral-7B 在相同四个任务和六种方法上的记录。",
            },
            "boundary": {
                "en": (
                    "The source is real historical aggregate evidence, not a paired "
                    "per-example model experiment."
                ),
                "zh": "来源是真实历史聚合证据，不是逐样本配对模型实验。",
            },
        },
    }
    write_json(out_dir / "case_manifest.json", case)
    return case


def _clear_generated_case_artifacts(out_dir: Path) -> None:
    """Remove only generated case artifacts while preserving authored documentation."""

    for name in ("baseline", "candidate", "review"):
        path = out_dir / name
        if path.is_dir():
            shutil.rmtree(path)
    for name in (
        "case_manifest.json",
        "comparison.csv",
        "comparison.en.svg",
        "comparison.zh.svg",
    ):
        path = out_dir / name
        if path.is_file():
            path.unlink()


def _checkpoint_metrics(rows: list[JsonDict]) -> JsonDict:
    return {
        "count": len(rows),
        "mean_score": _mean(rows, "mean_score"),
        "by_slice": {
            "gsm8k": _mean(rows, "gsm8k_score"),
            "format_following": _mean(rows, "format_following_score"),
        },
        "mean_tokens": _mean(rows, "mean_tokens"),
        "mean_latency_ms": _mean(rows, "mean_latency_ms"),
        "generation_mismatch": _mean(rows, "generation_mismatch"),
        "selective_aurc": _mean(rows, "selective_aurc"),
        "trajectory_drift": _mean(rows, "trajectory_drift"),
    }


def _agent_metrics(rows: list[JsonDict], *, side: str) -> JsonDict:
    """Aggregate one side of a paired Agent execution table."""

    return {
        "count": len(rows),
        "mean_score": _mean_boolean(rows, f"{side}_success"),
        "tests_pass_rate": _mean_boolean(rows, f"{side}_tests_passed"),
        "mean_total_tokens": _mean_optional(rows, f"{side}_total_tokens"),
        "mean_tool_calls": _mean_optional(rows, f"{side}_tool_calls"),
        "mean_touched_files": _mean_optional(rows, f"{side}_touched_files"),
        "mean_unnecessary_file_edits": _mean_optional(
            rows,
            f"{side}_unnecessary_file_edits",
        ),
        "mean_duration_seconds": _mean_optional(rows, f"{side}_duration_seconds"),
    }


def _agent_events(rows: list[JsonDict], *, side: str) -> list[JsonDict]:
    """Create deterministic aggregate events without copying Agent logs or prompts."""

    run_id = f"agent-pilot-{side}"
    events: list[JsonDict] = []
    for index, row in enumerate(rows, start=1):
        base_sequence = (index - 1) * 2
        timestamp = f"2026-01-01T00:{(index - 1) // 60:02d}:{(index - 1) % 60:02d}Z"
        test_passed = _csv_boolean(row.get(f"{side}_tests_passed"))
        events.append(
            ControlEvent.create(
                run_id=run_id,
                sequence=base_sequence + 1,
                event_type="tests/result",
                timestamp=timestamp,
                idempotency_key=f"{side}:{row.get('task_id')}:tests",
                payload={"passed": test_passed, "command": "python -m pytest -q"},
            ).to_json()
        )
        usage = _optional_float(row.get(f"{side}_total_tokens"))
        duration = _optional_float(row.get(f"{side}_duration_seconds"))
        payload: JsonDict = {
            "status": "completed" if _csv_boolean(row.get(f"{side}_success")) else "failed",
            "tool_calls": _optional_float(row.get(f"{side}_tool_calls")),
        }
        if usage is not None:
            payload["total_tokens"] = usage
        if duration is not None:
            payload["duration_ms"] = duration * 1000
        events.append(
            ControlEvent.create(
                run_id=run_id,
                sequence=base_sequence + 2,
                event_type="turn/end",
                timestamp=timestamp,
                idempotency_key=f"{side}:{row.get('task_id')}:turn",
                payload=payload,
            ).to_json()
        )
    return events


def _write_agent_comparison_svg(
    path: Path,
    *,
    raw_metrics: JsonDict,
    guarded_metrics: JsonDict,
    language: str,
) -> None:
    """Render a compact bilingual comparison from the committed aggregate metrics."""

    labels = (
        ("Task success rate", "任务成功率"),
        ("Test pass rate", "测试通过率"),
        ("Mean full-run tokens", "平均完整运行 Token"),
        ("Mean tool calls", "平均工具调用次数"),
    )
    keys = ("mean_score", "tests_pass_rate", "mean_total_tokens", "mean_tool_calls")
    rows: list[tuple[str, float, float, str]] = []
    for key, label_pair in zip(keys, labels, strict=True):
        raw = _optional_float(raw_metrics.get(key))
        guarded = _optional_float(guarded_metrics.get(key))
        if raw is None or guarded is None:
            continue
        display = "percent" if key in {"mean_score", "tests_pass_rate"} else "number"
        rows.append((label_pair[1 if language == "zh" else 0], raw, guarded, display))
    title = (
        "真实 Agent 成对执行对比" if language == "zh" else "Real paired Agent execution comparison"
    )
    subtitle = (
        "10 个任务 × 3 次重复；完整运行成本，不是只比较 Prompt 长度"
        if language == "zh"
        else "10 tasks × 3 trials; full-run cost, not prompt length alone"
    )
    legend_raw = "原始 Prompt" if language == "zh" else "Raw prompt"
    legend_guarded = "Guard 后" if language == "zh" else "After guard"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="620" '
        'viewBox="0 0 1280 620" role="img">',
        '<rect width="1280" height="620" fill="#f7f9f8"/>',
        f'<text x="64" y="68" font-family="Arial, sans-serif" font-size="30" '
        f'font-weight="700" fill="#142624">{title}</text>',
        f'<text x="64" y="102" font-family="Arial, sans-serif" font-size="18" '
        f'fill="#526461">{subtitle}</text>',
        '<rect x="900" y="48" width="18" height="18" rx="3" fill="#64748b"/>',
        f'<text x="928" y="63" font-family="Arial, sans-serif" font-size="16" '
        f'fill="#334155">{legend_raw}</text>',
        '<rect x="1060" y="48" width="18" height="18" rx="3" fill="#0f766e"/>',
        f'<text x="1088" y="63" font-family="Arial, sans-serif" font-size="16" '
        f'fill="#334155">{legend_guarded}</text>',
    ]
    for index, (label, raw, guarded, display) in enumerate(rows):
        top = 142 + index * 112
        maximum = max(raw, guarded, 1e-12)
        raw_width = 650 * raw / maximum
        guarded_width = 650 * guarded / maximum
        raw_text = f"{raw * 100:.1f}%" if display == "percent" else f"{raw:,.1f}"
        guarded_text = f"{guarded * 100:.1f}%" if display == "percent" else f"{guarded:,.1f}"
        parts.extend(
            [
                f'<text x="64" y="{top + 20}" font-family="Arial, sans-serif" '
                f'font-size="18" font-weight="600" fill="#1f3532">{label}</text>',
                f'<rect x="330" y="{top}" width="{raw_width:.2f}" height="30" '
                'rx="4" fill="#64748b"/>',
                f'<text x="1000" y="{top + 21}" font-family="Arial, sans-serif" '
                f'font-size="17" fill="#334155">{raw_text}</text>',
                f'<rect x="330" y="{top + 40}" width="{guarded_width:.2f}" height="30" '
                'rx="4" fill="#0f766e"/>',
                f'<text x="1000" y="{top + 61}" font-family="Arial, sans-serif" '
                f'font-size="17" fill="#0f5f59">{guarded_text}</text>',
            ]
        )
    footer = (
        "两侧均为 30/30 成功；该小样本只说明受控 fixture 上的执行效率差异。"
        if language == "zh"
        else "Both sides completed 30/30; this small fixture pilot only measures this setup."
    )
    parts.extend(
        [
            '<line x1="64" y1="584" x2="1216" y2="584" stroke="#d7e0de"/>',
            f'<text x="64" y="610" font-family="Arial, sans-serif" font-size="16" '
            f'fill="#526461">{footer}</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _validate_model_grid(
    baseline_rows: list[JsonDict],
    candidate_rows: list[JsonDict],
) -> None:
    """Require two complete, finite, and directly comparable aggregate grids."""

    if len(baseline_rows) != 24 or len(candidate_rows) != 24:
        raise ValueError("Model case requires 24 aggregate cells for each selected model")
    baseline_grid = {(str(row.get("task")), str(row.get("method"))) for row in baseline_rows}
    candidate_grid = {(str(row.get("task")), str(row.get("method"))) for row in candidate_rows}
    if len(baseline_grid) != 24 or baseline_grid != candidate_grid:
        raise ValueError("Selected model aggregates must cover the same unique task-method grid")
    for row in [*baseline_rows, *candidate_rows]:
        if row.get("metric") != "acc_hard_test":
            raise ValueError("Model case supports only the recorded `acc_hard_test` metric")
        mean = _optional_float(row.get("mean"))
        count = _optional_float(row.get("n"))
        if mean is None or count is None or count <= 0:
            raise ValueError("Model aggregate cells require finite means and positive counts")


def _model_metrics(rows: list[JsonDict]) -> JsonDict:
    """Aggregate historical task-method cells without inventing paired statistics."""

    tasks = sorted({str(row["task"]) for row in rows})
    methods = sorted({str(row["method"]) for row in rows})
    return {
        "count": len(rows),
        "mean_score": _mean(rows, "mean"),
        "by_slice": {
            task: _mean([row for row in rows if row.get("task") == task], "mean") for task in tasks
        },
        "by_method": {
            method: _mean([row for row in rows if row.get("method") == method], "mean")
            for method in methods
        },
        "aggregation_unit": "task_method_cell",
        "source_replicates": sum(int(row["n"]) for row in rows),
        "paired_per_example": False,
    }


def _write_model_comparison_csv(
    path: Path,
    *,
    baseline_metrics: JsonDict,
    candidate_metrics: JsonDict,
) -> None:
    """Write task-level descriptive values that can be checked without private data."""

    baseline = baseline_metrics.get("by_slice")
    candidate = candidate_metrics.get("by_slice")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        raise ValueError("Model metrics require task slices before CSV rendering")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("task", "qwen_mean", "mistral_mean", "descriptive_delta"),
        )
        writer.writeheader()
        for task in sorted(baseline):
            old = float(baseline[task])
            new = float(candidate[task])
            writer.writerow(
                {
                    "task": task,
                    "qwen_mean": f"{old:.12f}",
                    "mistral_mean": f"{new:.12f}",
                    "descriptive_delta": f"{new - old:.12f}",
                }
            )


def _write_model_comparison_svg(
    path: Path,
    *,
    baseline_metrics: JsonDict,
    candidate_metrics: JsonDict,
    language: str,
) -> None:
    """Render the four task slices while keeping aggregate-only limits visible."""

    baseline = baseline_metrics.get("by_slice")
    candidate = candidate_metrics.get("by_slice")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        raise ValueError("Model metrics require task slices before SVG rendering")
    title = "真实历史模型切换审查" if language == "zh" else "Real historical model change review"
    subtitle = (
        "相同 4 个任务 × 6 种方法；描述性聚合，不是逐样本配对检验"
        if language == "zh"
        else "Same 4 tasks × 6 methods; descriptive aggregates, not a paired test"
    )
    footer = (
        "总体均值接近，但任务切片方向不同，因此结论为需要复核。"
        if language == "zh"
        else "Overall means are close, but task slices move in different directions: review needed."
    )
    baseline_label = "Qwen2.5-7B"
    candidate_label = "Mistral-7B"
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="660" '
        'viewBox="0 0 1280 660" role="img">',
        '<rect width="1280" height="660" fill="#f7f9f8"/>',
        f'<text x="64" y="68" font-family="Arial, sans-serif" font-size="30" '
        f'font-weight="700" fill="#142624">{title}</text>',
        f'<text x="64" y="102" font-family="Arial, sans-serif" font-size="18" '
        f'fill="#526461">{subtitle}</text>',
        '<rect x="888" y="48" width="18" height="18" rx="3" fill="#64748b"/>',
        f'<text x="916" y="63" font-family="Arial, sans-serif" font-size="16" '
        f'fill="#334155">{baseline_label}</text>',
        '<rect x="1058" y="48" width="18" height="18" rx="3" fill="#0f766e"/>',
        f'<text x="1086" y="63" font-family="Arial, sans-serif" font-size="16" '
        f'fill="#334155">{candidate_label}</text>',
    ]
    for index, task in enumerate(sorted(baseline)):
        top = 146 + index * 116
        old = float(baseline[task])
        new = float(candidate[task])
        parts.extend(
            [
                f'<text x="64" y="{top + 25}" font-family="Arial, sans-serif" '
                f'font-size="18" font-weight="600" fill="#1f3532">{task}</text>',
                f'<rect x="300" y="{top}" width="{old * 850:.2f}" height="32" '
                'rx="4" fill="#64748b"/>',
                f'<text x="1170" y="{top + 23}" text-anchor="end" '
                f'font-family="Arial, sans-serif" font-size="17" fill="#334155">{old:.3f}</text>',
                f'<rect x="300" y="{top + 42}" width="{new * 850:.2f}" height="32" '
                'rx="4" fill="#0f766e"/>',
                f'<text x="1170" y="{top + 65}" text-anchor="end" '
                f'font-family="Arial, sans-serif" font-size="17" fill="#0f5f59">{new:.3f}</text>',
            ]
        )
    parts.extend(
        [
            '<line x1="64" y1="614" x2="1216" y2="614" stroke="#d7e0de"/>',
            f'<text x="64" y="642" font-family="Arial, sans-serif" font-size="16" '
            f'fill="#526461">{footer}</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[JsonDict]:
    if not path.is_file():
        raise ValueError(f"Missing checkpoint metrics: {path}")
    return [dict(row) for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines())]


def _mean(rows: list[JsonDict], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key) not in {None, ""}]
    if not values:
        raise ValueError(f"Checkpoint rows do not contain numeric `{key}` values")
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"Checkpoint rows contain non-finite `{key}` values")
    return round(sum(values) / len(values), 12)


def _mean_boolean(rows: list[JsonDict], key: str) -> float:
    return round(sum(_csv_boolean(row.get(key)) for row in rows) / len(rows), 12)


def _mean_optional(rows: list[JsonDict], key: str) -> float | None:
    values = [_optional_float(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return round(sum(present) / len(present), 12) if present else None


def _optional_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(str(value))
    except ValueError as exc:
        raise ValueError(f"Expected a numeric pilot value, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Expected a finite pilot value, got {value!r}")
    return number


def _csv_boolean(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"Expected a boolean pilot value, got {value!r}")
    return normalized == "true"


if __name__ == "__main__":
    raise SystemExit(main())
