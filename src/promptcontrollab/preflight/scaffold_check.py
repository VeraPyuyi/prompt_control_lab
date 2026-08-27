"""Validation helpers for generated evaluation scaffolds."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, read_jsonl, write_json

PLACEHOLDER_MARKERS = [
    "TODO",
    "Replace with",
    "replace-me",
    "Add another",
]


def check_prompt_optimizer_eval_scaffold(*, scaffold_dir: Path) -> JsonDict:
    """Check whether a prompt-optimizer eval scaffold is ready to score."""

    issues: list[JsonDict] = []
    scaffold_path = scaffold_dir / "prompt_optimizer_eval_scaffold.json"
    tasks_path = scaffold_dir / "tasks.template.jsonl"
    baseline_path = scaffold_dir / "baseline_predictions.template.jsonl"
    candidate_path = scaffold_dir / "candidate_predictions.template.jsonl"
    config_path = scaffold_dir / "promptcontrol.prompt_optimizer.example.yaml"

    scaffold = _read_json_file(scaffold_path, issues=issues)
    tasks = _read_jsonl_file(tasks_path, issues=issues)
    baseline = _read_jsonl_file(baseline_path, issues=issues)
    candidate = _read_jsonl_file(candidate_path, issues=issues)
    _require_file(config_path, issues=issues, code="missing_analyze_config")

    _check_records(
        tasks,
        path=tasks_path,
        required_fields=["id", "input", "expected", "slice"],
        issues=issues,
    )
    _check_records(
        baseline,
        path=baseline_path,
        required_fields=["id", "output", "provider", "model"],
        issues=issues,
    )
    _check_records(
        candidate,
        path=candidate_path,
        required_fields=["id", "output", "provider", "model"],
        issues=issues,
    )
    _check_paired_ids(tasks=tasks, baseline=baseline, candidate=candidate, issues=issues)

    prompt_files = []
    if isinstance(scaffold, dict):
        prompt_files = _prompt_files(scaffold)
    for prompt_file in prompt_files:
        _require_file(Path(prompt_file), issues=issues, code="missing_prompt_file")

    status = _status_from_issues(issues)
    payload: JsonDict = {
        "kind": "prompt_optimizer_eval_scaffold_check",
        "schema": "prompt_control_lab.prompt_optimizer_eval_scaffold_check.v1",
        "status": status,
        "scaffold_dir": str(scaffold_dir),
        "scaffold_path": str(scaffold_path),
        "task_count": len(tasks),
        "baseline_prediction_count": len(baseline),
        "candidate_prediction_count": len(candidate),
        "prompt_file_count": len(prompt_files),
        "issues": issues,
        "next_actions": _next_actions(status, issues),
        "boundary": (
            "This check validates scaffold completeness. It does not score prompts "
            "or prove an improvement claim."
        ),
    }
    return payload


def write_scaffold_check(
    *,
    scaffold_dir: Path,
    out_path: Path | None = None,
) -> JsonDict:
    """Write JSON/Markdown/HTML scaffold check artifacts."""

    payload = check_prompt_optimizer_eval_scaffold(scaffold_dir=scaffold_dir)
    json_path = out_path or scaffold_dir / "scaffold_check.json"
    md_path = json_path.with_suffix(".md")
    html_path = json_path.with_suffix(".html")
    ensure_dir(json_path.parent)
    write_json(json_path, payload)
    md_path.write_text(render_scaffold_check_markdown(payload), encoding="utf-8")
    html_path.write_text(render_scaffold_check_html(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["html_path"] = str(html_path)
    write_json(json_path, payload)
    return payload


def render_scaffold_check_markdown(payload: JsonDict) -> str:
    """Render a human-readable scaffold check."""

    lines = [
        "# Prompt Optimizer Eval Scaffold Check",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Scaffold: `{payload.get('scaffold_dir')}`",
        f"- Tasks: `{payload.get('task_count')}`",
        f"- Baseline predictions: `{payload.get('baseline_prediction_count')}`",
        f"- Candidate predictions: `{payload.get('candidate_prediction_count')}`",
        f"- Prompt files: `{payload.get('prompt_file_count')}`",
        "",
        "## Issues",
        "",
    ]
    issues = payload.get("issues")
    if isinstance(issues, list) and issues:
        for issue in issues:
            if isinstance(issue, dict):
                lines.append(
                    "- "
                    f"`{issue.get('severity')}` `{issue.get('code')}` "
                    f"{issue.get('message')} ({issue.get('path', '')})"
                )
    else:
        lines.append("- No scaffold issues found.")
    lines.extend(["", "## Next actions", ""])
    actions = payload.get("next_actions")
    if isinstance(actions, list):
        lines.extend(f"- {item}" for item in actions)
    lines.append("")
    return "\n".join(lines)


def render_scaffold_check_html(payload: JsonDict) -> str:
    """Render a reviewer-facing scaffold check page."""

    status = str(payload.get("status", "unknown"))
    status_class = {
        "pass": "pass",
        "needs_input": "review",
        "fail": "fail",
    }.get(status, "review")
    issue_rows = _issue_rows_html(payload.get("issues"))
    action_items = "\n".join(
        f"<li>{_html_text(action)}</li>" for action in _string_list(payload.get("next_actions"))
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Prompt Optimizer Eval Scaffold Check</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 32px; color: #172033; }}
    .hero {{ border: 1px solid #d8dee9; border-radius: 10px; padding: 18px; background: #fbfcff; }}
    .status {{
      display: inline-block;
      border-radius: 999px;
      padding: 5px 12px;
      font-weight: 700;
    }}
    .pass {{ background: #dcfce7; color: #166534; }}
    .review {{ background: #fef3c7; color: #92400e; }}
    .fail {{ background: #fee2e2; color: #991b1b; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .card {{ border: 1px solid #d8dee9; border-radius: 8px; padding: 12px; background: #ffffff; }}
    .num {{ font-size: 24px; font-weight: 800; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 14px; }}
    th, td {{
      border: 1px solid #d8dee9;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f5f7fb; }}
    code {{ background: #eef2f7; padding: 2px 4px; border-radius: 4px; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <h1>Prompt Optimizer Eval Scaffold Check</h1>
  <div class="hero">
    <p><span class="status {status_class}">{_html_text(status)}</span></p>
    <p><strong>Scaffold:</strong> <code>{_html_text(payload.get('scaffold_dir'))}</code></p>
    <p class="muted">{_html_text(payload.get('boundary'))}</p>
  </div>
  <div class="grid">
    {_metric_card_html(payload.get('task_count'), 'Tasks')}
    {_metric_card_html(payload.get('baseline_prediction_count'), 'Baseline predictions')}
    {_metric_card_html(payload.get('candidate_prediction_count'), 'Candidate predictions')}
    {_metric_card_html(payload.get('prompt_file_count'), 'Prompt files')}
  </div>
  <h2>Issues</h2>
  {issue_rows}
  <h2>Next actions</h2>
  <ul>{action_items}</ul>
</body>
</html>
"""


def _metric_card_html(value: object, label: str) -> str:
    return (
        '<div class="card">'
        f'<div class="num">{_html_text(value)}</div>'
        f"<div>{_html_text(label)}</div>"
        "</div>"
    )


def _issue_rows_html(raw_issues: object) -> str:
    issues = raw_issues if isinstance(raw_issues, list) else []
    if not issues:
        return "<p>No scaffold issues found.</p>"
    rows = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        rows.append(
            "<tr>"
            f"<td><code>{_html_text(issue.get('severity'))}</code></td>"
            f"<td><code>{_html_text(issue.get('code'))}</code></td>"
            f"<td>{_html_text(issue.get('message'))}</td>"
            f"<td><code>{_html_text(issue.get('path', ''))}</code></td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Severity</th><th>Code</th><th>Message</th><th>Path</th>"
        "</tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def _read_json_file(path: Path, *, issues: list[JsonDict]) -> JsonDict:
    if not path.exists():
        issues.append(
            _issue(
                "error",
                "missing_scaffold_json",
                f"Missing scaffold metadata file `{path.name}`.",
                path,
            )
        )
        return {}
    try:
        return read_json(path)
    except ValueError as exc:
        issues.append(_issue("error", "invalid_json", str(exc), path))
        return {}


def _read_jsonl_file(path: Path, *, issues: list[JsonDict]) -> list[JsonDict]:
    if not path.exists():
        issues.append(
            _issue("error", "missing_jsonl", f"Missing JSONL file `{path.name}`.", path)
        )
        return []
    try:
        return read_jsonl(path)
    except ValueError as exc:
        issues.append(_issue("error", "invalid_jsonl", str(exc), path))
        return []


def _require_file(path: Path, *, issues: list[JsonDict], code: str) -> None:
    if not path.exists():
        issues.append(_issue("error", code, f"Missing file `{path.name}`.", path))


def _check_records(
    records: list[JsonDict],
    *,
    path: Path,
    required_fields: list[str],
    issues: list[JsonDict],
) -> None:
    for index, record in enumerate(records):
        for field in required_fields:
            value = record.get(field)
            if value in (None, ""):
                issues.append(
                    _issue(
                        "error",
                        "missing_field",
                        f"Record {index} is missing required field `{field}`.",
                        path,
                    )
                )
                continue
            if isinstance(value, str) and _has_placeholder(value):
                issues.append(
                    _issue(
                        "warning",
                        "placeholder_value",
                        f"Record {index} field `{field}` still looks like a template.",
                        path,
                    )
                )


def _check_paired_ids(
    *,
    tasks: list[JsonDict],
    baseline: list[JsonDict],
    candidate: list[JsonDict],
    issues: list[JsonDict],
) -> None:
    task_ids = _ids(tasks)
    baseline_ids = _ids(baseline)
    candidate_ids = _ids(candidate)
    if not task_ids:
        return
    if task_ids != baseline_ids:
        issues.append(
            _issue(
                "error",
                "baseline_id_mismatch",
                "Baseline prediction ids must exactly match task ids for paired evaluation.",
                None,
            )
        )
    if task_ids != candidate_ids:
        issues.append(
            _issue(
                "error",
                "candidate_id_mismatch",
                "Candidate prediction ids must exactly match task ids for paired evaluation.",
                None,
            )
        )


def _ids(records: list[JsonDict]) -> set[str]:
    ids: set[str] = set()
    for record in records:
        raw_id = record.get("id")
        if isinstance(raw_id, str):
            ids.add(raw_id)
    return ids


def _prompt_files(scaffold: JsonDict) -> list[str]:
    raw_files = scaffold.get("asset_prompt_files")
    if not isinstance(raw_files, list):
        return []
    files: list[str] = []
    for item in raw_files:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            files.append(item["path"])
    return files


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _html_text(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _has_placeholder(value: str) -> bool:
    return any(marker.lower() in value.lower() for marker in PLACEHOLDER_MARKERS)


def _status_from_issues(issues: list[JsonDict]) -> str:
    if any(issue.get("severity") == "error" for issue in issues):
        return "fail"
    if issues:
        return "needs_input"
    return "pass"


def _next_actions(status: str, issues: list[JsonDict]) -> list[str]:
    if status == "pass":
        return [
            "Run pcl analyze with the generated promptcontrol.prompt_optimizer.example.yaml.",
            "Run pcl diagnose on the scored run before making an improvement claim.",
        ]
    if any(issue.get("severity") == "error" for issue in issues):
        return [
            "Restore or regenerate missing scaffold files.",
            "Make sure task ids, baseline ids, and candidate ids match exactly.",
        ]
    return [
        "Replace TODO/template values with real tasks, outputs, provider, and model ids.",
        "Then rerun pcl scaffold-check before running pcl analyze.",
    ]


def _issue(severity: str, code: str, message: str, path: Path | None) -> JsonDict:
    payload: JsonDict = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path is not None:
        payload["path"] = str(path)
    return payload
