"""One-command ecosystem bridge demo for bundled external-tool exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from promptcontrollab.external_evidence import ExternalTool, build_external_evidence
from promptcontrollab.files import JsonDict, ensure_dir, read_json, write_json


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
    (out_dir / "README.md").write_text(_render_readme(payload), encoding="utf-8")
    return payload


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
            "4. Open `report.html` or `pcl ui --runs <this-dir>` for a visual review.",
            "",
        ]
    )
    return "\n".join(lines)
