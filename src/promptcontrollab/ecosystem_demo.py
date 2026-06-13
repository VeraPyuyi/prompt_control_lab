"""One-command ecosystem bridge demo for bundled external-tool exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.external_evidence import ExternalTool, build_external_evidence
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.research_workflow import run_research_diagnostics


@dataclass(frozen=True)
class EcosystemDemoSpec:
    tool: ExternalTool
    filename: str
    score_name: str | None = None
    baseline_prompt_id: str | None = None
    candidate_prompt_id: str | None = None
    baseline_name: str | None = None
    candidate_name: str | None = None
    baseline_experiment: str | None = None
    candidate_experiment: str | None = None


DEMO_SPECS: tuple[EcosystemDemoSpec, ...] = (
    EcosystemDemoSpec(
        tool="promptfoo",
        filename="promptfoo_results.json",
        baseline_prompt_id="baseline",
        candidate_prompt_id="candidate",
    ),
    EcosystemDemoSpec(
        tool="langfuse",
        filename="langfuse_export.json",
        score_name="exact_match",
        baseline_name="baseline",
        candidate_name="candidate",
    ),
    EcosystemDemoSpec(
        tool="langsmith",
        filename="langsmith_runs.csv",
        score_name="exact_match",
        baseline_experiment="baseline",
        candidate_experiment="candidate",
    ),
)


def run_ecosystem_demo(
    *,
    examples_dir: Path,
    out_dir: Path,
    split_hash: str = "external-demo-split",
    provider: str = "openai",
    model: str = "gpt-4o-mini-20260601",
    bootstrap_samples: int = 1000,
    permutation_samples: int = 1000,
) -> JsonDict:
    """Run all bundled external bridge examples into one reviewer-facing directory."""

    if not examples_dir.exists():
        msg = f"External examples directory does not exist: {examples_dir}"
        raise ValueError(msg)
    if out_dir.exists() and any(out_dir.iterdir()):
        msg = f"Ecosystem demo output directory must be empty: {out_dir}"
        raise ValueError(msg)
    ensure_dir(out_dir)

    runs: list[JsonDict] = []
    for spec in DEMO_SPECS:
        source = examples_dir / spec.filename
        if not source.exists():
            msg = f"Missing {spec.tool} example export: {source}"
            raise ValueError(msg)
        tool_dir = out_dir / spec.tool
        provider_value = f"{provider}:{model}" if spec.tool == "promptfoo" else provider
        build_external_evidence(
            tool=spec.tool,
            baseline_input=source,
            candidate_input=source,
            out_dir=tool_dir,
            score_name=spec.score_name,
            provider=provider_value,
            model=model,
            baseline_prompt_id=spec.baseline_prompt_id,
            candidate_prompt_id=spec.candidate_prompt_id,
            baseline_name=spec.baseline_name,
            candidate_name=spec.candidate_name,
            baseline_experiment=spec.baseline_experiment,
            candidate_experiment=spec.candidate_experiment,
            split_hash=split_hash,
            title=f"PromptControlLab {spec.tool} Evidence Demo",
            bootstrap_samples=bootstrap_samples,
            permutation_samples=permutation_samples,
        )
        bridge = read_json(tool_dir / "bridge_summary.json")
        runs.append(
            {
                "tool": spec.tool,
                "source": str(source),
                "out_dir": str(tool_dir),
                "recommendation": bridge.get("recommendation"),
                "evidence_tier": bridge.get("evidence_tier"),
                "validity": bridge.get("validity"),
                "claim_check_status": bridge.get("claim_check_status"),
                "missing_evidence": bridge.get("missing_evidence", []),
                "next_actions": bridge.get("next_actions", []),
                "result_path": str(tool_dir / "evidence_from_result.json"),
                "bridge_summary_path": str(tool_dir / "bridge_summary.md"),
                "report_html_path": str(tool_dir / "report.html"),
            }
        )

    payload: JsonDict = {
        "kind": "ecosystem_demo",
        "examples_dir": str(examples_dir),
        "out_dir": str(out_dir),
        "positioning": (
            "prompt_control_lab acts as a prompt optimization evidence auditor on top of "
            "external eval and observability exports."
        ),
        "runs": runs,
        "next_steps": [
            "Open each bridge_summary.md to see what the external tool supplied.",
            "Open each evidence_card.md to inspect the prompt optimization evidence.",
            "Open each claim_check.md to see the strongest supported claim.",
            "Open report.html or the local UI Research Overview for reviewer-facing inspection.",
        ],
    }
    write_json(out_dir / "ecosystem_demo.json", payload)
    diagnostics = run_research_diagnostics(
        run_dir=out_dir,
        mode="ecosystem_demo",
        diagnostics_dir=out_dir / "diagnostics",
        summary_dir=out_dir,
    )
    payload["research_diagnostics_path"] = str(out_dir / "research_diagnostics.json")
    payload["research_diagnostics_md_path"] = str(out_dir / "research_diagnostics.md")
    payload["research_diagnostic_type"] = diagnostics.get("diagnostic_type")
    scorecard = _write_scorecard(out_dir=out_dir, payload=payload, diagnostics=diagnostics)
    payload["ecosystem_scorecard_path"] = scorecard["json_path"]
    payload["ecosystem_scorecard_md_path"] = scorecard["markdown_path"]
    write_json(out_dir / "ecosystem_demo.json", payload)
    (out_dir / "README.md").write_text(_render_readme(payload), encoding="utf-8")
    return payload


def _write_scorecard(*, out_dir: Path, payload: JsonDict, diagnostics: JsonDict) -> JsonDict:
    rows = _scorecard_rows(out_dir=out_dir, payload=payload, diagnostics=diagnostics)
    scorecard: JsonDict = {
        "kind": "ecosystem_scorecard",
        "positioning": (
            "Promptfoo, LangSmith, and Langfuse remain the systems of record for evals, "
            "traces, security tests, and prompt management. PCL adds the research evidence "
            "layer for prompt optimization claims."
        ),
        "tool_count": len(rows),
        "rows": rows,
        "recommended_review_order": [
            "Open ecosystem_scorecard.md for the cross-tool summary.",
            "Open each bridge_summary.md for tool-specific provenance.",
            "Open evidence_card.md and claim_check.md before making an optimization claim.",
            "Open research_gap_plan.md, run the reviewed commands, then run pcl gap-status.",
        ],
        "boundary": (
            "This scorecard summarizes evidence coverage. It does not claim that PCL "
            "replaces external eval, tracing, observability, or security-testing platforms."
        ),
    }
    json_path = out_dir / "ecosystem_scorecard.json"
    md_path = out_dir / "ecosystem_scorecard.md"
    write_json(json_path, scorecard)
    md_path.write_text(_render_scorecard(scorecard), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "rows": rows,
    }


def _scorecard_rows(*, out_dir: Path, payload: JsonDict, diagnostics: JsonDict) -> list[JsonDict]:
    diagnostic_rows = _diagnostic_rows_by_tool(diagnostics)
    rows: list[JsonDict] = []
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return rows
    for run in runs:
        if not isinstance(run, dict):
            continue
        tool = str(run.get("tool") or "external")
        tool_dir = Path(str(run.get("out_dir") or out_dir / tool))
        bridge_path = tool_dir / "bridge_summary.json"
        bridge = read_json(bridge_path) if bridge_path.exists() else {}
        diagnostic = diagnostic_rows.get(tool, {})
        rows.append(
            {
                "tool": tool,
                "display_name": _display_tool_name(tool),
                "external_strength": _external_strength(tool),
                "pcl_adds": _pcl_adds(tool),
                "validity": bridge.get("validity") or run.get("validity"),
                "evidence_tier": bridge.get("evidence_tier") or run.get("evidence_tier"),
                "claim_check_status": bridge.get("claim_check_status")
                or run.get("claim_check_status"),
                "recommendation": bridge.get("recommendation") or run.get("recommendation"),
                "paired_n": bridge.get("paired_n"),
                "mean_delta": bridge.get("mean_delta"),
                "missing_paper_diagnostics": diagnostic.get(
                    "missing_paper_diagnostics",
                    bridge.get("missing_paper_diagnostics", []),
                ),
                "research_gap_plan": _relative_to(out_dir, tool_dir / "research_gap_plan.md")
                if (tool_dir / "research_gap_plan.md").exists()
                else "",
                "gap_status_command": f"pcl gap-status --run {_relative_to(out_dir, tool_dir)}",
                "open_first": _relative_to(out_dir, tool_dir / "bridge_summary.md"),
            }
        )
    return rows


def _relative_to(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _diagnostic_rows_by_tool(diagnostics: JsonDict) -> dict[str, JsonDict]:
    diagnostic_payload = diagnostics.get("diagnostics")
    if not isinstance(diagnostic_payload, dict):
        return {}
    ecosystem = diagnostic_payload.get("ecosystem_bridge")
    if not isinstance(ecosystem, dict):
        return {}
    runs = ecosystem.get("runs")
    if not isinstance(runs, list):
        return {}
    rows: dict[str, JsonDict] = {}
    for row in runs:
        if not isinstance(row, dict):
            continue
        tool = row.get("tool")
        if isinstance(tool, str) and tool:
            rows[tool] = row
    return rows


def _external_strength(tool: str) -> str:
    values = {
        "promptfoo": "LLM evals, red-team/security tests, provider matrices, and CI reports.",
        "langfuse": "Open-source tracing, prompt management, scores, costs, and self-hosting.",
        "langsmith": "Agent tracing, datasets, online/offline evals, debugging, and deployment.",
    }
    return values.get(tool, "External eval or observability export.")


def _pcl_adds(tool: str) -> str:
    values = {
        "promptfoo": (
            "Paired uncertainty, prompt-only validity, evidence cards, claim checks, "
            "and paper-diagnostic gap closure."
        ),
        "langfuse": (
            "Export-to-evidence conversion, paired validity checks, local evidence cards, "
            "and diagnostics outside trace platforms."
        ),
        "langsmith": (
            "Prompt optimization evidence bundles that separate prompt effects from model, "
            "metric, and split confounds."
        ),
    }
    return values.get(tool, "Paired prompt optimization evidence and diagnostics.")


def _display_tool_name(tool: str) -> str:
    values = {
        "promptfoo": "Promptfoo",
        "langfuse": "Langfuse",
        "langsmith": "LangSmith",
    }
    return values.get(tool, tool)


def _render_scorecard(payload: JsonDict) -> str:
    lines = [
        "# Ecosystem Scorecard",
        "",
        str(payload.get("positioning", "")),
        "",
        "## Cross-tool summary",
        "",
        (
            "| Tool | External strength | What PCL adds | Validity | Evidence tier | "
            "Missing paper diagnostics |"
        ),
        "|---|---|---|---|---|---|",
    ]
    rows = payload.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            missing = row.get("missing_paper_diagnostics")
            missing_text = (
                ", ".join(str(item) for item in missing)
                if isinstance(missing, list)
                else str(missing or "")
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        str(row.get("external_strength", "")),
                        str(row.get("pcl_adds", "")),
                        str(row.get("validity", "")),
                        str(row.get("evidence_tier", "")),
                        missing_text,
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Gap closure commands",
            "",
            "| Tool | Open first | Gap status command |",
            "|---|---|---|",
        ]
    )
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("display_name", "")),
                        f"`{row.get('open_first', '')}`",
                        f"`{row.get('gap_status_command', '')}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Recommended review order",
            "",
            *[f"- {item}" for item in _string_list(payload.get("recommended_review_order"))],
            "",
            "## Boundary",
            "",
            str(payload.get("boundary", "")),
            "",
        ]
    )
    return "\n".join(lines)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _render_readme(payload: JsonDict) -> str:
    lines = [
        "# prompt_control_lab Ecosystem Demo",
        "",
        (
            "This directory shows how `prompt_control_lab` works as a prompt optimization "
            "evidence auditor for exports from Promptfoo, Langfuse, and LangSmith."
        ),
        "",
        "It does not replace those tools. It adds paired statistics, prompt-only validity, "
        "evidence cards, claim checks, and research-diagnostic hooks on top of their exports.",
        "",
        "Start with `ecosystem_scorecard.md` for the cross-tool positioning and gap-closure view.",
        "",
        "## Generated bundles",
        "",
        "| Tool | Validity | Evidence tier | Claim check | Open first |",
        "|---|---|---|---|---|",
    ]
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            tool = run.get("tool", "")
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(tool),
                        str(run.get("validity", "")),
                        str(run.get("evidence_tier", "")),
                        str(run.get("claim_check_status", "")),
                        f"[bridge_summary.md]({tool}/bridge_summary.md)",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Suggested review order",
            "",
            "1. Read `bridge_summary.md` for each tool.",
            "2. Check `evidence_card.md` for protocol and statistical evidence.",
            "3. Check `claim_check.md` before making any prompt optimization claim.",
            "4. Read `research_diagnostics.md` for paper-evidence gap coverage.",
            "5. Run `pcl gap-status --run <tool-dir>` after closing diagnostic gaps.",
            "6. Open `report.html` or `pcl ui --runs <this-dir>` for a visual review.",
            "",
        ]
    )
    return "\n".join(lines)
