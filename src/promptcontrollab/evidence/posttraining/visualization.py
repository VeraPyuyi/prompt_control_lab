"""Normalize checkpoint metrics for public-safe visualization and local review."""
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import html
import io
import math
import re
from collections.abc import Iterable
from pathlib import Path

from promptcontrollab.core.files import JsonDict, write_json

MAX_CHECKPOINT_CSV_BYTES = 1024 * 1024
MAX_CHECKPOINT_ROWS = 1000

_NAMED_STAGE_ORDER = {"initial": 0.0, "mid": 1.0, "final": 2.0}
_REQUIRED_FIELDS = {"seed", "checkpoint_id", "mean_score"}
_OPTIONAL_NUMERIC_FIELDS = (
    "generation_mismatch",
    "selective_aurc",
    "trajectory_drift",
    "format_following_score",
    "mean_tokens",
    "mean_latency_ms",
    "readout_alignment_gap",
    "reachability_shift",
)
_OUTPUT_FIELDS = (
    "seed",
    "stage",
    "step",
    "checkpoint_id",
    "mean_score",
    *_OPTIONAL_NUMERIC_FIELDS,
)
_DIAGNOSTICS = {
    "generation_mismatch": "lower_is_better",
    "selective_aurc": "lower_is_better",
    "trajectory_drift": "context_dependent",
}


def parse_checkpoint_csv(
    csv_text: str,
    *,
    max_bytes: int = MAX_CHECKPOINT_CSV_BYTES,
    max_rows: int = MAX_CHECKPOINT_ROWS,
) -> list[JsonDict]:
    """Validate CSV text and return normalized checkpoint observations.

    Args:
        csv_text: UTF-8 checkpoint table content.
        max_bytes: Maximum encoded upload size.
        max_rows: Maximum number of data rows.

    Returns:
        Normalized rows containing only the public visualization allowlist.

    Raises:
        ValueError: If the table is oversized, ambiguous, or contains invalid values.
    """

    if len(csv_text.encode("utf-8")) > max_bytes:
        raise ValueError("Checkpoint CSV exceeds the 1 MB local upload limit")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    fieldnames = {str(name).strip() for name in (reader.fieldnames or []) if name}
    missing = sorted(_REQUIRED_FIELDS - fieldnames)
    if missing:
        raise ValueError(f"Checkpoint CSV is missing required field(s): {', '.join(missing)}")
    if "stage" not in fieldnames and "step" not in fieldnames:
        raise ValueError("Checkpoint CSV requires either a stage or numeric step field")

    rows: list[JsonDict] = []
    identities: set[tuple[str, str]] = set()
    for index, raw in enumerate(reader, start=2):
        if len(rows) >= max_rows:
            raise ValueError(f"Checkpoint CSV may contain at most {max_rows} rows")
        seed = str(raw.get("seed") or "").strip()
        checkpoint_id = str(raw.get("checkpoint_id") or "").strip()
        if not seed or not checkpoint_id:
            raise ValueError(f"Checkpoint CSV row {index} requires seed and checkpoint_id")
        identity = (seed, checkpoint_id)
        if identity in identities:
            raise ValueError(
                f"Checkpoint CSV contains duplicate seed + checkpoint_id at row {index}"
            )
        identities.add(identity)

        stage, order, step = _normalize_stage(raw, index=index)
        row: JsonDict = {
            "seed": seed,
            "stage": stage,
            "checkpoint_id": checkpoint_id,
            "mean_score": _finite_number(raw.get("mean_score"), "mean_score", index),
            "order": order,
        }
        if step is not None:
            row["step"] = step
        for field in _OPTIONAL_NUMERIC_FIELDS:
            value = raw.get(field)
            if value not in (None, ""):
                row[field] = _finite_number(value, field, index)
        rows.append(row)

    if not rows:
        raise ValueError("Checkpoint CSV does not contain any data rows")
    if len({str(row["stage"]) for row in rows}) < 2:
        raise ValueError("Checkpoint CSV requires at least two distinct stages or steps")
    return sorted(rows, key=lambda row: (float(row["order"]), str(row["seed"])))


def build_checkpoint_visualization(
    rows: Iterable[JsonDict],
    *,
    decision: str = "insufficient_evidence",
    triggered_checks: Iterable[JsonDict] = (),
    evidence_level: str = "descriptive_checkpoint_metrics",
) -> JsonDict:
    """Build the canonical visualization payload from normalized checkpoint rows.

    Notes:
        The payload is descriptive. It does not infer significance or causation from
        aggregate checkpoint observations.
    """

    normalized = sorted(
        (dict(row) for row in rows),
        key=lambda row: (float(row["order"]), str(row["seed"])),
    )
    if not normalized:
        raise ValueError("Checkpoint visualization requires at least one observation")
    stage_order = _stage_order(normalized)
    aggregates = [_aggregate_stage(normalized, stage) for stage in stage_order]
    diagnostics: JsonDict = {}
    for field, direction in _DIAGNOSTICS.items():
        available = any(isinstance(row.get(field), (int, float)) for row in normalized)
        diagnostics[field] = {
            "available": available,
            "direction": direction,
            "aggregates": [
                {"stage": aggregate["stage"], "value": aggregate.get(field)}
                for aggregate in aggregates
            ]
            if available
            else [],
        }
    return {
        "schema": "prompt_control_lab.checkpoint_visualization.v1",
        "decision": decision,
        "evidence_level": evidence_level,
        "stage_order": stage_order,
        "seeds": sorted({str(row["seed"]) for row in normalized}),
        "points": [_public_point(row) for row in normalized],
        "aggregates": aggregates,
        "diagnostics": diagnostics,
        "triggered_checks": [dict(item) for item in triggered_checks],
        "narrative": _narrative(aggregates, decision),
        "claim_boundary": (
            "These plots describe recorded checkpoint associations. They do not establish "
            "a unique causal training mechanism or deployment safety."
        ),
    }


def save_checkpoint_run(runs_dir: Path, run_name: str, csv_text: str) -> Path:
    """Save one validated checkpoint table as a bounded local run.

    The run records descriptive metrics only. Missing prompt, model, split, and gate
    provenance is explicit, so imported scores cannot be mistaken for a release decision.
    """

    slug = _safe_run_slug(run_name)
    root = runs_dir.resolve(strict=False)
    output = (root / slug).resolve(strict=False)
    if output.parent != root:
        raise ValueError("Run name must resolve directly below the configured runs directory")
    if output.exists():
        raise FileExistsError(f"Checkpoint run already exists: {slug}")
    rows = parse_checkpoint_csv(csv_text)
    visualization = build_checkpoint_visualization(
        rows,
        decision="insufficient_evidence",
        evidence_level="user_imported_descriptive_metrics",
    )

    output.mkdir(parents=True)
    (output / "checkpoint_metrics.csv").write_text(
        normalized_checkpoint_csv(rows), encoding="utf-8", newline=""
    )
    write_json(output / "checkpoint_visualization.json", visualization)
    write_json(
        output / "manifest.json",
        {
            "schema": "prompt_control_lab.checkpoint_import_manifest.v1",
            "mode": "checkpoint_import",
            "row_count": len(rows),
            "seed_count": len(visualization["seeds"]),
            "prompt": {"status": "not_recorded"},
            "model": {"status": "not_recorded"},
            "split": {"status": "not_recorded"},
            "gate": {"status": "not_recorded"},
        },
    )
    write_json(
        output / "case_manifest.json",
        {
            "schema": "prompt_control_lab.local_checkpoint_import.v1",
            "decision": "insufficient_evidence",
            "display": {
                "featured": False,
                "category": "checkpoint",
                "evidence_level": "user_imported_descriptive_metrics",
                "technical_change_kind": "checkpoint_change",
                "title": {"en": run_name.strip(), "zh": run_name.strip()},
            },
            "claim_boundary": visualization["claim_boundary"],
        },
    )
    return output


def _normalize_stage(raw: dict[str, str | None], *, index: int) -> tuple[str, float, float | None]:
    """Return a display stage, sortable order, and optional numeric step."""

    stage_value = str(raw.get("stage") or "").strip().lower()
    step_value = str(raw.get("step") or "").strip()
    if stage_value:
        if stage_value not in _NAMED_STAGE_ORDER:
            raise ValueError(
                f"Checkpoint CSV row {index} has unknown stage {stage_value!r}; "
                "use initial, mid, final, or a numeric step"
            )
        if step_value:
            step = _finite_number(step_value, "step", index)
            return stage_value, step, step
        return stage_value, _NAMED_STAGE_ORDER[stage_value], None
    step = _finite_number(step_value, "step", index)
    return _number_text(step), step, step


def _finite_number(value: object, field: str, index: int) -> float:
    """Parse one finite numeric cell with a row-aware error."""

    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Checkpoint CSV row {index} has invalid {field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Checkpoint CSV row {index} requires finite {field}")
    return number


def _stage_order(rows: list[JsonDict]) -> list[str]:
    """Return distinct stage labels in numeric training order."""

    order_by_stage: dict[str, float] = {}
    for row in rows:
        stage = str(row["stage"])
        order = float(row["order"])
        order_by_stage[stage] = min(order, order_by_stage.get(stage, order))
    return [stage for stage, _ in sorted(order_by_stage.items(), key=lambda item: item[1])]


def _aggregate_stage(rows: list[JsonDict], stage: str) -> JsonDict:
    """Aggregate every available numeric metric for one stage."""

    selected = [row for row in rows if row.get("stage") == stage]
    aggregate: JsonDict = {"stage": stage, "seed_count": len(selected)}
    for field in ("mean_score", *_OPTIONAL_NUMERIC_FIELDS):
        values = [float(row[field]) for row in selected if isinstance(row.get(field), (int, float))]
        if values:
            aggregate[field] = round(sum(values) / len(values), 12)
    return aggregate


def _public_point(row: JsonDict) -> JsonDict:
    """Remove internal sort helpers from one visualization point."""

    return {key: row[key] for key in _OUTPUT_FIELDS if key in row and row[key] not in (None, "")}


def normalized_checkpoint_csv(rows: Iterable[JsonDict]) -> str:
    """Render allowlisted checkpoint rows with deterministic columns and ordering."""

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(_OUTPUT_FIELDS), lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=lambda item: (float(item["order"]), str(item["seed"]))):
        writer.writerow(_public_point(row))
    return buffer.getvalue()


def render_checkpoint_svg(payload: JsonDict, *, language: str) -> str:
    """Render the linked score, diagnostic, and decision views as one static SVG."""

    if language not in {"en", "zh"}:
        raise ValueError("Checkpoint SVG language must be `en` or `zh`")
    points = [dict(item) for item in payload.get("points", []) if isinstance(item, dict)]
    aggregates = [
        dict(item) for item in payload.get("aggregates", []) if isinstance(item, dict)
    ]
    stages = [str(item) for item in payload.get("stage_order", [])]
    if not points or not aggregates or len(stages) < 2:
        raise ValueError("Checkpoint SVG requires points and at least two stages")
    seeds = [str(item) for item in payload.get("seeds", [])]
    title = "Checkpoint 发布审查" if language == "zh" else "Checkpoint promotion review"
    subtitle = (
        "真实 Seed 轨迹、独立风险量纲与发布门禁"
        if language == "zh"
        else "Recorded seed trajectories, separate risk scales, and release gate"
    )
    score_title = "各 Seed 的 Checkpoint 分数" if language == "zh" else "Checkpoint score by seed"
    decision_label = "当前决策" if language == "zh" else "Current decision"
    decision = str(payload.get("decision") or "insufficient_evidence")
    colors = ("#2563eb", "#0f766e", "#c26a18", "#7c3aed", "#be123c")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="900" '
        'viewBox="0 0 1280 900" role="img">',
        '<rect width="1280" height="900" fill="#f7f9f8"/>',
        f'<text x="64" y="62" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="30" font-weight="700" fill="#142624">{html.escape(title)}</text>',
        f'<text x="64" y="96" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="18" fill="#526461">{html.escape(subtitle)}</text>',
        f'<text x="64" y="144" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="20" font-weight="700" fill="#1f3532">{html.escape(score_title)}</text>',
    ]
    parts.extend(
        _score_svg(
            points,
            aggregates,
            stages,
            seeds,
            colors,
            language=language,
            x=64,
            y=166,
            width=730,
            height=340,
        )
    )
    diagnostic_titles = {
        "generation_mismatch": ("生成阶段错配", "Generation mismatch"),
        "selective_aurc": ("选择性风险 AURC", "Selective risk AURC"),
        "trajectory_drift": ("表示轨迹漂移", "Representation trajectory drift"),
    }
    for index, field in enumerate(_DIAGNOSTICS):
        label = diagnostic_titles[field][0 if language == "zh" else 1]
        values = [
            (str(row.get("stage")), float(row[field]))
            for row in aggregates
            if isinstance(row.get(field), (int, float))
        ]
        top = 138 + index * 170
        parts.append(
            f'<text x="850" y="{top}" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="16" font-weight="700" fill="#1f3532">{html.escape(label)}</text>'
        )
        if values:
            parts.extend(
                _mini_metric_svg(
                    values,
                    language=language,
                    x=850,
                    y=top + 18,
                    width=360,
                    height=118,
                )
            )
        else:
            missing = "未记录" if language == "zh" else "Not recorded"
            parts.append(
                f'<text x="850" y="{top + 70}" font-family="Arial, Microsoft YaHei, sans-serif" '
                f'font-size="16" fill="#7a8492">{missing}</text>'
            )
    parts.extend(
        [
            '<rect x="64" y="560" width="1152" height="122" rx="8" fill="#fff7e8" '
            'stroke="#ead0a6"/>',
            f'<text x="90" y="602" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="16" font-weight="700" fill="#7a4708">{decision_label}</text>',
            f'<text x="90" y="648" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="30" font-weight="700" fill="#7a4708">'
            f"{html.escape(decision.upper())}</text>",
        ]
    )
    checks = [item for item in payload.get("triggered_checks", []) if isinstance(item, dict)]
    check_names = [str(item.get("check") or "") for item in checks if item.get("check")]
    reason = " / ".join(check_names[:3])
    if len(check_names) > 3:
        reason = f"{reason} +{len(check_names) - 3}"
    reason = reason or (
        "需要检查稳定性、生成错配与风险证据"
        if language == "zh"
        else "Review stability, generation mismatch, and risk evidence"
    )
    parts.append(
        f'<text x="310" y="630" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="16" fill="#5f4a2f">{html.escape(reason)}</text>'
    )
    initial = aggregates[0]
    final = aggregates[-1]
    footer = (
        f"平均分数 {float(initial['mean_score']):.4f} → {float(final['mean_score']):.4f}；"
        "分数提高不能覆盖门禁中的阻断项。"
        if language == "zh"
        else f"Mean score {float(initial['mean_score']):.4f} → "
        f"{float(final['mean_score']):.4f}; a higher score does not override hold signals."
    )
    boundary = (
        "聚合轨迹只支持有边界的关联解释，不证明唯一因果机制或部署安全。"
        if language == "zh"
        else "Aggregate trajectories support bounded association, not unique causation or safety."
    )
    parts.extend(
        [
            f'<text x="64" y="744" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="19" font-weight="700" fill="#1f3532">{html.escape(footer)}</text>',
            '<line x1="64" y1="782" x2="1216" y2="782" stroke="#d7e0de"/>',
            f'<text x="64" y="820" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="16" fill="#526461">{html.escape(boundary)}</text>',
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def _score_svg(
    points: list[JsonDict],
    aggregates: list[JsonDict],
    stages: list[str],
    seeds: list[str],
    colors: tuple[str, ...],
    *,
    language: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[str]:
    """Render seed trajectories and a heavier aggregate mean line."""

    values = [float(row["mean_score"]) for row in points]
    maximum = max(values)
    minimum = min(0.0, min(values))
    span = max(maximum - minimum, 0.05)
    upper = maximum + span * 0.15
    left = x + 54
    right = x + width - 24
    top = y + 18
    bottom = y + height - 48
    x_by_stage = {
        stage: left + index * (right - left) / max(1, len(stages) - 1)
        for index, stage in enumerate(stages)
    }

    def y_value(value: float) -> float:
        return bottom - (value - minimum) * (bottom - top) / max(upper - minimum, 1e-12)

    result = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" '
        'fill="#ffffff" stroke="#d7e0de"/>',
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#cbd5e1"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#cbd5e1"/>',
    ]
    for index in range(4):
        value = minimum + (upper - minimum) * index / 3
        py = y_value(value)
        result.extend(
            [
                f'<line x1="{left}" y1="{py:.2f}" x2="{right}" y2="{py:.2f}" '
                'stroke="#eef1f4"/>',
                f'<text x="{left - 10}" y="{py + 5:.2f}" text-anchor="end" '
                'font-family="Arial, sans-serif" font-size="13" fill="#657083">'
                f'{value:.2f}</text>',
            ]
        )
    for index, stage in enumerate(stages):
        px = x_by_stage[stage]
        anchor = "start" if index == 0 else "end" if index == len(stages) - 1 else "middle"
        stage_text = (
            {"initial": "初始", "mid": "中间", "final": "最终"}.get(stage, stage)
            if language == "zh"
            else stage.title()
        )
        result.append(
            f'<text x="{px:.2f}" y="{bottom + 28}" text-anchor="{anchor}" '
            f'font-family="Arial, sans-serif" font-size="13" fill="#526461">'
            f'{html.escape(stage_text)}</text>'
        )
    for seed_index, seed in enumerate(seeds):
        seed_points = [row for row in points if str(row.get("seed")) == seed]
        coordinates = [
            (x_by_stage[str(row["stage"])], y_value(float(row["mean_score"])))
            for row in seed_points
            if str(row["stage"]) in x_by_stage
        ]
        if not coordinates:
            continue
        color = colors[seed_index % len(colors)]
        joined = " ".join(f"{px:.2f},{py:.2f}" for px, py in coordinates)
        result.append(
            f'<polyline points="{joined}" fill="none" stroke="{color}" stroke-width="2"/>'
        )
        for px, py in coordinates:
            result.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="{color}"/>')
        legend_x = x + 24 + seed_index * 112
        result.extend(
            [
                f'<line x1="{legend_x}" y1="{y + 16}" x2="{legend_x + 20}" '
                f'y2="{y + 16}" stroke="{color}" stroke-width="3"/>',
                f'<text x="{legend_x + 27}" y="{y + 21}" font-family="Arial, sans-serif" '
                f'font-size="12" fill="#526461">Seed {html.escape(seed)}</text>',
            ]
        )
    mean_coordinates = [
        (x_by_stage[str(row["stage"])], y_value(float(row["mean_score"])))
        for row in aggregates
    ]
    result.append(
        '<polyline points="'
        + " ".join(f"{px:.2f},{py:.2f}" for px, py in mean_coordinates)
        + '" fill="none" stroke="#172033" stroke-width="4"/>'
    )
    mean_legend_x = x + 24 + len(seeds) * 112
    mean_label = "阶段均值" if language == "zh" else "Stage mean"
    result.extend(
        [
            f'<line x1="{mean_legend_x}" y1="{y + 16}" x2="{mean_legend_x + 20}" '
            f'y2="{y + 16}" stroke="#172033" stroke-width="4"/>',
            f'<text x="{mean_legend_x + 27}" y="{y + 21}" '
            'font-family="Arial, Microsoft YaHei, sans-serif" font-size="12" '
            f'fill="#526461">{mean_label}</text>',
        ]
    )
    return result


def _mini_metric_svg(
    values: list[tuple[str, float]],
    *,
    language: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[str]:
    """Render one independent diagnostic scale without cross-metric normalization."""

    numbers = [value for _, value in values]
    minimum = min(numbers)
    maximum = max(numbers)
    padding = max((maximum - minimum) * 0.2, max(abs(maximum), 1.0) * 0.02)
    lower = minimum - padding
    upper = maximum + padding
    left = x + 8
    right = x + width - 8
    top = y + 8
    bottom = y + height - 25

    def px(index: int) -> float:
        return left + index * (right - left) / max(1, len(values) - 1)

    def py(value: float) -> float:
        return bottom - (value - lower) * (bottom - top) / max(upper - lower, 1e-12)

    coordinates = [(px(index), py(value)) for index, (_, value) in enumerate(values)]
    result = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" '
        'fill="#ffffff" stroke="#d7e0de"/>',
        '<polyline points="'
        + " ".join(f"{cx:.2f},{cy:.2f}" for cx, cy in coordinates)
        + '" fill="none" stroke="#0f766e" stroke-width="2.5"/>',
    ]
    for index, ((stage, value), (cx, cy)) in enumerate(zip(values, coordinates, strict=True)):
        anchor = "start" if index == 0 else "end" if index == len(values) - 1 else "middle"
        stage_text = (
            {"initial": "初始", "mid": "中间", "final": "最终"}.get(stage, stage)
            if language == "zh"
            else stage.title()
        )
        result.extend(
            [
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="3.5" fill="#0f766e"/>',
                f'<text x="{cx:.2f}" y="{cy - 9:.2f}" text-anchor="{anchor}" '
                f'font-family="Arial, sans-serif" font-size="12" fill="#334155">{value:.3f}</text>',
                f'<text x="{cx:.2f}" y="{y + height - 8}" text-anchor="{anchor}" '
                f'font-family="Arial, sans-serif" font-size="11" fill="#657083">'
                f'{html.escape(stage_text)}</text>',
            ]
        )
    return result


def _safe_run_slug(run_name: str) -> str:
    """Normalize a user label without permitting path syntax."""

    stripped = run_name.strip()
    if not stripped or ".." in stripped or any(marker in stripped for marker in ("/", "\\")):
        raise ValueError("Run name must be a non-empty local label without path markers")
    slug = re.sub(r"[^\w-]+", "-", stripped, flags=re.UNICODE).strip("-_").lower()
    if not slug:
        raise ValueError("Run name must contain at least one letter or number")
    return slug[:80]


def _number_text(value: float) -> str:
    """Format integral steps without a decimal suffix."""

    return str(int(value)) if value.is_integer() else format(value, "g")


def _narrative(aggregates: list[JsonDict], decision: str) -> JsonDict:
    """Build bounded bilingual explanation slots without causal claims."""

    first = aggregates[0]
    last = aggregates[-1]
    score_before = float(first.get("mean_score") or 0.0)
    score_after = float(last.get("mean_score") or 0.0)
    return {
        "en": {
            "changed": f"Checkpoint stage changed from {first['stage']} to {last['stage']}.",
            "observed": (
                f"Recorded mean score changed from {score_before:.4f} "
                f"to {score_after:.4f}."
            ),
            "meaning": "Training stage is associated with a changed performance and risk profile.",
            "boundary": "The aggregate trajectory does not identify a unique causal mechanism.",
            "next_action": f"Review the recorded gate evidence before acting on {decision}.",
        },
        "zh": {
            "changed": f"Checkpoint 阶段从 {first['stage']} 变为 {last['stage']}。",
            "observed": f"已记录平均分数从 {score_before:.4f} 变为 {score_after:.4f}。",
            "meaning": "训练阶段与性能和风险画像的变化存在关联。",
            "boundary": "聚合轨迹不能识别唯一的因果机制。",
            "next_action": f"在执行 {decision} 决策前检查已记录的门禁证据。",
        },
    }
