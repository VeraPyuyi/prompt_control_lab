"""Human-readable report generation."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.files import JsonDict, read_json


def generate_report(run_dir: Path, *, title: str) -> tuple[Path, Path]:
    """Generate Markdown and HTML reports for a run directory."""

    manifest = _read_optional_json(run_dir / "manifest.json")
    metrics = _read_optional_json(run_dir / "metrics.json")
    stats = _read_optional_json(run_dir / "stats.json")
    splits = _read_optional_json(run_dir / "splits.json")
    diagnostics = _collect_diagnostics(run_dir / "diagnostics")
    markdown = render_markdown(
        title=title,
        manifest=manifest,
        metrics=metrics,
        stats=stats,
        splits=splits,
        diagnostics=diagnostics,
    )
    md_path = run_dir / "report.md"
    html_path = run_dir / "report.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(render_html(markdown, title=title), encoding="utf-8")
    return md_path, html_path


def render_markdown(
    *,
    title: str,
    manifest: JsonDict,
    metrics: JsonDict,
    stats: JsonDict,
    splits: JsonDict,
    diagnostics: dict[str, JsonDict],
) -> str:
    """Render a compact diagnostic report."""

    lines: list[str] = [f"# {title}", ""]
    if manifest:
        lines += [
            "## Run",
            "",
            f"- Method: `{manifest.get('method', 'unknown')}`",
            f"- Metric: `{manifest.get('metric', 'unknown')}`",
            f"- Tool version: `{manifest.get('tool_version', 'unknown')}`",
            "",
        ]
    if splits:
        leakage = splits.get("leakage", {})
        has_leakage = (
            leakage.get("has_leakage", "unknown") if isinstance(leakage, dict) else "unknown"
        )
        lines += [
            "## Split Hygiene",
            "",
            f"- Split hash: `{splits.get('split_hash', 'missing')}`",
            f"- Counts: `{splits.get('counts', {})}`",
            f"- Leakage detected: `{has_leakage}`",
            "",
            "This section explains whether train, validation, and withheld examples were "
            "kept apart.",
            "",
        ]
    if metrics:
        lines += [
            "## Metrics",
            "",
            f"- Count: `{metrics.get('count', 0)}`",
            f"- Mean score: `{metrics.get('mean_score', 0.0)}`",
            f"- Slice scores: `{metrics.get('by_slice', {})}`",
            "",
            "This section shows how the prompt performed overall and by task slice.",
            "",
        ]
    if stats:
        lines += ["## Statistical Comparison", ""]
        comparisons = stats.get("comparisons", [])
        if isinstance(comparisons, list):
            for comparison in comparisons:
                if isinstance(comparison, dict):
                    lines += [
                        f"- Mean delta: `{comparison.get('mean_delta')}`",
                        f"- Bootstrap CI: `{comparison.get('bootstrap_ci')}`",
                        f"- Permutation p-value: `{comparison.get('permutation_p_value')}`",
                        f"- Holm-adjusted p-value: `{comparison.get('holm_adjusted_p_value')}`",
                        f"- Interpretation: `{comparison.get('interpretation')}`",
                    ]
        lines += [
            "",
            "This section explains whether the observed change is reliable or still uncertain.",
            "",
        ]
    if diagnostics:
        lines += ["## Diagnostics", ""]
        for name, payload in sorted(diagnostics.items()):
            lines += [f"### {name}", "", f"```json\n{_pretty(payload)}\n```", ""]
        lines += [
            "Diagnostics explain deployment risk, trajectory drift, surrogate stability, or "
            "time-varying control behavior depending on which commands were run.",
            "",
        ]
    lines += [
        "## What To Check Next",
        "",
        "- If the withheld score regressed, inspect the affected task slices before keeping "
        "the prompt.",
        "- If the confidence interval crosses zero, treat the apparent change as uncertain.",
        "- If soft-hard or trajectory diagnostics are high risk, inspect deployment assumptions.",
        "",
    ]
    return "\n".join(lines)


def render_html(markdown: str, *, title: str) -> str:
    """Render a dependency-free HTML wrapper around the Markdown text."""

    escaped = html.escape(markdown)
    return (
        "<!doctype html>\n"
        "<html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:920px;margin:40px auto;"
        "line-height:1.55;padding:0 20px}pre{background:#f6f8fa;padding:16px;"
        "overflow:auto}code{background:#f6f8fa;padding:2px 4px}</style>"
        "</head><body>"
        f"<pre>{escaped}</pre>"
        "</body></html>\n"
    )


def _read_optional_json(path: Path) -> JsonDict:
    if not path.exists():
        return {}
    return read_json(path)


def _collect_diagnostics(path: Path) -> dict[str, JsonDict]:
    if not path.exists():
        return {}
    diagnostics: dict[str, JsonDict] = {}
    for item in sorted(path.glob("*.json")):
        diagnostics[item.stem] = read_json(item)
    return diagnostics


def _pretty(value: JsonDict) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True)
