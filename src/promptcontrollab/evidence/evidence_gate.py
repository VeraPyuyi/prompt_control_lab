"""Reviewer and CI gate for prompt-optimization evidence artifacts."""

from __future__ import annotations

import html
from pathlib import Path

from promptcontrollab.core.files import JsonDict, read_json, write_json
from promptcontrollab.evidence.external_evidence import verify_source_inputs
from promptcontrollab.diagnostics.research_workflow import verify_research_bundle_index

DYNAMIC_BUNDLE_ARTIFACTS = {
    "bridge_summary.html",
    "bridge_summary.json",
    "bridge_summary.md",
    "source_input_verification.html",
    "source_input_verification.json",
    "source_input_verification.md",
    "research_bundle_verification.html",
    "research_bundle_verification.json",
    "research_bundle_verification.md",
    "evidence_gate_result.html",
    "evidence_gate_result.json",
    "evidence_gate_result.md",
}


def run_evidence_gate(
    *,
    run_dir: Path,
    out_path: Path | None = None,
    require_source: bool = False,
    allow_missing_bundle: bool = False,
) -> JsonDict:
    """Run a compact gate over source-input and research-bundle evidence."""

    json_path = out_path or (run_dir / "evidence_gate_result.json")
    source_payload = verify_source_inputs(run_dir=run_dir)
    source_check = _source_check(source_payload, require_source=require_source)
    bundle_payload = _verify_bundle(run_dir=run_dir, allow_missing_bundle=allow_missing_bundle)
    bundle_check = _bundle_check(bundle_payload, allow_missing_bundle=allow_missing_bundle)
    advisory_checks = {
        "gap_status": _gap_check(run_dir),
        "claim_check": _claim_check(run_dir),
    }
    required_checks = {
        "source_inputs": source_check,
        "research_bundle": bundle_check,
        "eval_scaffold": _scaffold_check(run_dir),
    }
    status = _overall_status(required_checks)
    markdown_path = json_path.with_suffix(".md")
    html_path = json_path.with_suffix(".html")
    payload: JsonDict = {
        "kind": "evidence_gate_result",
        "run_dir": str(run_dir),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "html_path": str(html_path),
        "status": status,
        "required_checks": required_checks,
        "advisory_checks": advisory_checks,
        "source_verification_path": source_payload.get("json_path"),
        "research_bundle_verification_path": bundle_payload.get("json_path"),
        "summary": _summary(status, required_checks, advisory_checks),
        "next_actions": _next_actions(status, required_checks, advisory_checks),
        "boundary": (
            "This gate verifies local source-input hashes and research-bundle artifact hashes. "
            "It is a reviewer/CI evidence check, not proof of provider-side logs, hidden model "
            "weights, or scientific sufficiency."
        ),
    }
    write_json(json_path, payload)
    markdown_path.write_text(_render_markdown(payload), encoding="utf-8")
    html_path.write_text(_render_html(payload), encoding="utf-8")
    return payload


def _verify_bundle(*, run_dir: Path, allow_missing_bundle: bool) -> JsonDict:
    try:
        payload = verify_research_bundle_index(run_dir)
    except ValueError as exc:
        if not (run_dir / "research_bundle.json").exists():
            status = "needs_review" if allow_missing_bundle else "fail"
            return {
                "kind": "research_bundle_verification",
                "run_dir": str(run_dir),
                "json_path": "",
                "status": status,
                "checked_count": 0,
                "ok_count": 0,
                "mismatch_count": 0,
                "missing_count": 1,
                "unchecked_count": 0,
                "reason": str(exc),
            }
        raise
    payload["json_path"] = str(run_dir / "research_bundle_verification.json")
    return payload


def _source_check(payload: JsonDict, *, require_source: bool) -> JsonDict:
    status = str(payload.get("status") or "unknown")
    base = {
        "source_status": status,
        "checked_count": payload.get("checked_count"),
        "mismatch_count": payload.get("mismatch_count"),
        "missing_count": payload.get("missing_count"),
        "unchecked_count": payload.get("unchecked_count"),
        "json_path": payload.get("json_path"),
        "html_path": payload.get("html_path"),
    }
    if status == "pass":
        return {**base, "status": "pass", "severity": "required"}
    if status == "missing_source_inputs" and not require_source:
        return {
            **base,
            "status": "skipped",
            "severity": "info",
            "reason": "No external source_inputs were recorded for this run.",
        }
    if status == "needs_review":
        return {**base, "status": "needs_review", "severity": "required"}
    return {**base, "status": "fail", "severity": "required"}


def _bundle_check(payload: JsonDict, *, allow_missing_bundle: bool) -> JsonDict:
    status = str(payload.get("status") or "unknown")
    dynamic_mismatches = _dynamic_mismatches(payload)
    mismatch_count = int(payload.get("mismatch_count") or 0)
    stable_mismatch_count = max(0, mismatch_count - len(dynamic_mismatches))
    base = {
        "bundle_status": status,
        "checked_count": payload.get("checked_count"),
        "mismatch_count": stable_mismatch_count,
        "ignored_dynamic_mismatch_count": len(dynamic_mismatches),
        "ignored_dynamic_mismatches": dynamic_mismatches,
        "missing_count": payload.get("missing_count"),
        "unchecked_count": payload.get("unchecked_count"),
        "json_path": payload.get("json_path"),
    }
    if status == "pass" or (status == "fail" and stable_mismatch_count == 0):
        return {**base, "status": "pass", "severity": "required"}
    if status == "needs_review" and allow_missing_bundle:
        return {
            **base,
            "status": "needs_review",
            "severity": "required",
            "reason": payload.get("reason"),
        }
    return {
        **base,
        "status": "fail",
        "severity": "required",
        "reason": payload.get("reason"),
    }


def _dynamic_mismatches(payload: JsonDict) -> list[str]:
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    paths = []
    for item in results:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if item.get("status") == "mismatch" and path in DYNAMIC_BUNDLE_ARTIFACTS:
            paths.append(path)
    return paths


def _gap_check(run_dir: Path) -> JsonDict:
    path = run_dir / "research_gap_status.json"
    if not path.exists():
        return {
            "status": "not_recorded",
            "severity": "advisory",
            "reason": "No research_gap_status.json artifact was found.",
        }
    payload = read_json(path)
    status = str(payload.get("status") or "unknown")
    return {
        "status": status,
        "severity": "advisory",
        "complete_count": payload.get("complete_count"),
        "missing_count": payload.get("missing_count"),
        "json_path": str(path),
    }


def _claim_check(run_dir: Path) -> JsonDict:
    path = run_dir / "claim_check.json"
    if not path.exists():
        return {
            "status": "not_recorded",
            "severity": "advisory",
            "reason": "No claim_check.json artifact was found.",
        }
    payload = read_json(path)
    return {
        "status": payload.get("status", "unknown"),
        "severity": "advisory",
        "evidence_tier": payload.get("evidence_tier"),
        "requested_claim": payload.get("requested_claim"),
        "json_path": str(path),
    }


def _scaffold_check(run_dir: Path) -> JsonDict:
    """Assess whether imported prompt assets have a complete evaluation scaffold."""

    scaffold_dir = run_dir / "eval_scaffold"
    check_path = scaffold_dir / "scaffold_check.json"
    has_prompt_optimizer_context = any(
        path.exists()
        for path in [
            run_dir / "prompt_assets.json",
            run_dir / "prompt_optimizer_gap_plan.json",
            scaffold_dir,
        ]
    )
    if not has_prompt_optimizer_context:
        return {
            "status": "skipped",
            "severity": "info",
            "reason": "No prompt-optimizer eval scaffold was recorded for this run.",
        }
    if not check_path.exists():
        return {
            "status": "needs_review",
            "severity": "required",
            "reason": "Prompt-optimizer eval scaffold exists but scaffold_check.json is missing.",
            "json_path": str(check_path),
        }
    payload = read_json(check_path)
    scaffold_status = str(payload.get("status") or "unknown")
    issues = payload.get("issues")
    issue_count = len(issues) if isinstance(issues, list) else 0
    base = {
        "scaffold_status": scaffold_status,
        "issue_count": issue_count,
        "task_count": payload.get("task_count"),
        "baseline_prediction_count": payload.get("baseline_prediction_count"),
        "candidate_prediction_count": payload.get("candidate_prediction_count"),
        "prompt_file_count": payload.get("prompt_file_count"),
        "json_path": str(check_path),
    }
    if scaffold_status == "pass":
        return {**base, "status": "pass", "severity": "required"}
    if scaffold_status == "fail":
        return {
            **base,
            "status": "fail",
            "severity": "required",
            "reason": "Prompt-optimizer eval scaffold check failed.",
        }
    return {
        **base,
        "status": "needs_review",
        "severity": "required",
        "reason": "Prompt-optimizer eval scaffold is not ready for paired scoring.",
    }


def _overall_status(required_checks: dict[str, JsonDict]) -> str:
    statuses = [str(item.get("status") or "unknown") for item in required_checks.values()]
    if "fail" in statuses:
        return "fail"
    if any(status in {"needs_review", "unknown"} for status in statuses):
        return "needs_review"
    return "pass"


def _summary(
    status: str,
    required_checks: dict[str, JsonDict],
    advisory_checks: dict[str, JsonDict],
) -> str:
    required = ", ".join(f"{name}={check.get('status')}" for name, check in required_checks.items())
    advisory = ", ".join(f"{name}={check.get('status')}" for name, check in advisory_checks.items())
    return f"Evidence gate {status}: required checks [{required}], advisory checks [{advisory}]."


def _next_actions(
    status: str,
    required_checks: dict[str, JsonDict],
    advisory_checks: dict[str, JsonDict],
) -> list[str]:
    actions: list[str] = []
    source_status = required_checks["source_inputs"].get("status")
    bundle_status = required_checks["research_bundle"].get("status")
    scaffold_status = required_checks["eval_scaffold"].get("status")
    if source_status == "fail":
        actions.append(
            "Open source_input_verification.html and restore or re-import source exports."
        )
    if source_status == "needs_review":
        actions.append(
            "Review unchecked source inputs before treating the comparison as reproducible."
        )
    if bundle_status == "fail":
        actions.append(
            "Open research_bundle_verification.html and refresh or restore changed artifacts."
        )
    if bundle_status == "needs_review":
        actions.append(
            "Create or refresh research_bundle.json before using this run as reviewer evidence."
        )
    if scaffold_status == "fail":
        actions.append("Open eval_scaffold/scaffold_check.html and fix failed scaffold checks.")
    if scaffold_status == "needs_review":
        actions.append(
            "Run `pcl scaffold-check --run <run>` and fill real tasks/predictions before scoring."
        )
    if advisory_checks["gap_status"].get("status") == "needs_work":
        actions.append(
            "Open research_gap_status.html to see which paper-derived diagnostics are missing."
        )
    if advisory_checks["claim_check"].get("status") not in {"pass", "not_recorded"}:
        actions.append("Open claim_check.html to review the supported claim boundary.")
    if not actions and status == "pass":
        actions.append("Use evidence_gate_result.html as the CI/reviewer summary.")
    return actions


def _render_markdown(payload: JsonDict) -> str:
    required_rows = _check_rows(payload.get("required_checks"))
    advisory_rows = _check_rows(payload.get("advisory_checks"))
    actions = "\n".join(
        f"{index}. {item}" for index, item in enumerate(_list(payload.get("next_actions")), 1)
    )
    return "\n".join(
        [
            "# Evidence Gate Result",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Run: `{payload.get('run_dir')}`",
            f"- Summary: {payload.get('summary')}",
            "",
            "## Required checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
            *required_rows,
            "",
            "## Advisory checks",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
            *advisory_rows,
            "",
            "## Next actions",
            "",
            actions,
            "",
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )


def _render_html(payload: JsonDict) -> str:
    required_table = _html_table(_check_html_rows(payload.get("required_checks")))
    advisory_table = _html_table(_check_html_rows(payload.get("advisory_checks")))
    actions = "".join(f"<li>{_html_text(item)}</li>" for item in _list(payload.get("next_actions")))
    body = f"""
    <section class="hero">
      <p class="eyebrow">prompt_control_lab evidence gate</p>
      <h1>Evidence Gate Result</h1>
      <p>{_html_text(payload.get("summary"))}</p>
    </section>
    <section class="cards">
      {_card("Status", payload.get("status"))}
      {_card("Run", payload.get("run_dir"))}
      {_card("Source verification", payload.get("source_verification_path"))}
      {_card("Bundle verification", payload.get("research_bundle_verification_path"))}
    </section>
    <section>
      <h2>Required checks</h2>
      {required_table}
    </section>
    <section>
      <h2>Advisory checks</h2>
      {advisory_table}
    </section>
    <section>
      <h2>Next actions</h2>
      <ol>{actions}</ol>
    </section>
    <section>
      <h2>Boundary</h2>
      <p>{_html_text(payload.get("boundary"))}</p>
    </section>
    """
    return _html_page("Evidence Gate Result", body)


def _check_rows(value: object) -> list[str]:
    checks = value if isinstance(value, dict) else {}
    rows = []
    for name, check in checks.items():
        if not isinstance(check, dict):
            continue
        rows.append(
            "| "
            f"{_markdown_cell(name)} | "
            f"`{_markdown_cell(check.get('status'))}` | "
            f"{_markdown_cell(_detail(check))} |"
        )
    return rows or ["| _missing_ |  |  |"]


def _check_html_rows(value: object) -> list[str]:
    checks = value if isinstance(value, dict) else {}
    rows = []
    for name, check in checks.items():
        if not isinstance(check, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{_html_text(name)}</td>"
            f"<td><strong>{_html_text(check.get('status'))}</strong></td>"
            f"<td>{_html_text(_detail(check))}</td>"
            "</tr>"
        )
    return rows


def _detail(check: JsonDict) -> str:
    parts = []
    for key in [
        "source_status",
        "bundle_status",
        "scaffold_status",
        "checked_count",
        "issue_count",
        "mismatch_count",
        "ignored_dynamic_mismatch_count",
        "missing_count",
        "unchecked_count",
        "evidence_tier",
        "reason",
        "json_path",
    ]:
        value = check.get(key)
        if value not in {None, ""}:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _html_page(title: str, body: str) -> str:
    """Wrap the evidence-gate body in a standalone HTML document."""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html_text(title)}</title>
  <style>
    body {{
      margin: 0;
      background: #f7f9fc;
      color: #172033;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 40px 24px 56px; }}
    section {{
      background: #fff;
      border: 1px solid #d8e0ec;
      border-radius: 14px;
      margin: 18px 0;
      padding: 22px;
      box-shadow: 0 12px 32px rgba(15, 23, 42, .06);
    }}
    .hero {{ background: linear-gradient(135deg, #fff, #edf4ff); }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: .08em;
      color: #2563eb;
      font-size: 13px;
      font-weight: 700;
    }}
    h1 {{ margin: 8px 0 12px; font-size: 34px; }}
    h2 {{ margin-top: 0; font-size: 20px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      background: transparent;
      border: 0;
      box-shadow: none;
      padding: 0;
    }}
    .card {{
      background: #fff;
      border: 1px solid #d8e0ec;
      border-radius: 12px;
      padding: 16px;
    }}
    .label {{ color: #64748b; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .value {{ margin-top: 7px; font-weight: 700; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{
      border-bottom: 1px solid #d8e0ec;
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: #64748b; font-size: 13px; }}
  </style>
</head>
<body><main>{body}</main></body>
</html>
"""


def _html_table(rows: list[str]) -> str:
    if not rows:
        return "<p>No checks recorded.</p>"
    return (
        "<table><thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _card(label: str, value: object) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{_html_text(label)}</div>'
        f'<div class="value">{_html_text(value)}</div>'
        "</div>"
    )


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _markdown_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _html_text(value: object) -> str:
    return html.escape(str(value or ""))
