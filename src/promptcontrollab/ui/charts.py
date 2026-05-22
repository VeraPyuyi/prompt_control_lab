"""Plotly chart builders for the local dashboard."""

from __future__ import annotations

import importlib
from typing import Any, cast

from promptcontrollab.files import JsonDict


def risk_category_bar(
    counts: dict[str, int],
    *,
    title: str = "Risk Categories",
    category_label: str = "category",
    count_label: str = "count",
    none_label: str = "none",
) -> Any:
    """Build a risk category bar chart."""

    px = _plotly_express()
    rows = [{category_label: key, count_label: value} for key, value in sorted(counts.items())]
    if not rows:
        rows = [{category_label: none_label, count_label: 0}]
    return px.bar(rows, x=category_label, y=count_label, title=title)


def score_delta_ci(
    stats: JsonDict,
    *,
    title: str = "Score Delta CI",
    mean_label: str = "mean_delta",
) -> Any:
    """Build a score delta chart with CI when available."""

    go = _plotly_graph_objects()
    mean_delta = _number(stats.get("mean_delta")) or 0.0
    ci = stats.get("bootstrap_ci")
    lower = upper = mean_delta
    if isinstance(ci, list) and len(ci) >= 2:
        lower = _number(ci[0]) or mean_delta
        upper = _number(ci[1]) or mean_delta
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=[mean_label],
            y=[mean_delta],
            error_y={
                "type": "data",
                "array": [max(0.0, upper - mean_delta)],
                "arrayminus": [max(0.0, mean_delta - lower)],
            },
        )
    )
    figure.add_hline(y=0, line_dash="dash", line_color="#64748b")
    figure.update_layout(title=f"{title} [{lower:.3f}, {upper:.3f}]")
    return figure


def slice_score_heatmap(
    rows: list[JsonDict],
    *,
    title: str = "Slice Scores",
    baseline_label: str = "baseline",
    candidate_label: str = "candidate",
) -> Any:
    """Build a simple baseline/candidate slice heatmap."""

    go = _plotly_graph_objects()
    slices = [str(row["slice"]) for row in rows] or ["none"]
    baseline = [_number(row.get("baseline")) for row in rows] or [None]
    candidate = [_number(row.get("candidate")) for row in rows] or [None]
    figure = go.Figure(
        data=go.Heatmap(
            z=[baseline, candidate],
            x=slices,
            y=[baseline_label, candidate_label],
            colorscale="Viridis",
            zmin=0,
            zmax=1,
        )
    )
    figure.update_layout(title=title)
    return figure


def file_breakdown_bar(
    audit: JsonDict,
    *,
    title: str = "Touched Files Breakdown",
    kind_label: str = "kind",
    count_label: str = "count",
    source_label: str = "source",
    tests_label: str = "tests",
    docs_label: str = "docs",
    config_label: str = "config",
) -> Any:
    """Build changed-file breakdown chart."""

    px = _plotly_express()
    rows = [
        {kind_label: source_label, count_label: int(audit.get("source_files_changed") or 0)},
        {kind_label: tests_label, count_label: int(audit.get("test_files_changed") or 0)},
        {kind_label: docs_label, count_label: int(audit.get("docs_files_changed") or 0)},
        {kind_label: config_label, count_label: int(audit.get("config_files_changed") or 0)},
    ]
    return px.bar(rows, x=kind_label, y=count_label, title=title)


def _plotly_express() -> Any:
    return cast(Any, importlib.import_module("plotly.express"))


def _plotly_graph_objects() -> Any:
    return cast(Any, importlib.import_module("plotly.graph_objects"))


def _number(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
