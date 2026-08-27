"""Build research evidence gap plans and completion status artifacts."""

from __future__ import annotations

from pathlib import Path

from promptcontrollab.core.files import JsonDict, ensure_dir, read_json, write_json
from promptcontrollab.diagnostics.bundle import (
    _paper_remediation_for,
    write_research_bundle_index,
)
from promptcontrollab.diagnostics.common import _remediation_list
from promptcontrollab.diagnostics.gap_renderers import (
    _render_gap_commands_ps1,
    _render_gap_commands_sh,
    _render_research_gap_plan_markdown,
    _render_research_gap_status_markdown,
    render_research_gap_plan_html,
    render_research_gap_status_html,
)


def write_peoc_research_gap_plan(run_dir: Path) -> JsonDict:
    """Write fail-closed follow-up actions for imported PEOC evidence gaps."""

    evidence_path = run_dir / "peoc_evidence.json"
    if not evidence_path.exists():
        msg = (
            f"No peoc_evidence.json found in {run_dir}. "
            "Run `pcl research-import peoc` before creating a PEOC gap plan."
        )
        raise ValueError(msg)
    evidence = read_json(evidence_path)
    sections_value = evidence.get("sections")
    if not isinstance(sections_value, dict):
        msg = f"Invalid peoc_evidence.json in {run_dir}: expected a sections object."
        raise ValueError(msg)
    sections = sections_value

    actions = [
        action
        for section_name, action in [
            (
                "hard_evaluation",
                _peoc_hard_evaluation_action(
                    source_status=_peoc_section_status(sections, "hard_evaluation")
                ),
            ),
            (
                "soft_evaluation",
                _peoc_soft_evaluation_action(
                    source_status=_peoc_section_status(sections, "soft_evaluation")
                ),
            ),
            (
                "trajectory",
                _peoc_trajectory_action(source_status=_peoc_section_status(sections, "trajectory")),
            ),
            (
                "stage_heterogeneity",
                _peoc_stage_action(
                    source_status=_peoc_section_status(sections, "stage_heterogeneity")
                ),
            ),
            (
                "riccati",
                _peoc_riccati_action(source_status=_peoc_section_status(sections, "riccati")),
            ),
            (
                "soft_hard",
                _peoc_soft_hard_action(source_status=_peoc_section_status(sections, "soft_hard")),
            ),
        ]
        if _peoc_section_status(sections, section_name) != "available" and action
    ]

    numbered_actions = _numbered_actions([action for action in actions if action])
    plan: JsonDict = {
        "kind": "research_gap_plan",
        "run_dir": str(run_dir),
        "diagnostic_type": "peoc_replication_evidence_gap",
        "source_evidence": "peoc_evidence.json",
        "action_count": len(numbered_actions),
        "actions": numbered_actions,
        "boundary": (
            "This plan is a copy-paste guide for collecting missing paper-derived evidence. "
            "Commands with placeholders must be edited before use; no missing diagnostic is "
            "treated as measured until its artifact exists. For PEOC imports, existing missing, "
            "partial, unusable, and failed-validation sources remain incomplete; actions target "
            "future usable outputs. PromptControlLab commands are listed only where "
            "PromptControlLab can generate the diagnostic."
        ),
    }
    ensure_dir(run_dir)
    write_json(run_dir / "research_gap_plan.json", plan)
    (run_dir / "research_gap_plan.md").write_text(
        _render_research_gap_plan_markdown(plan),
        encoding="utf-8",
    )
    (run_dir / "research_gap_plan.html").write_text(
        render_research_gap_plan_html(plan),
        encoding="utf-8",
    )
    (run_dir / "research_gap_commands.ps1").write_text(
        _render_gap_commands_ps1(plan),
        encoding="utf-8",
    )
    (run_dir / "research_gap_commands.sh").write_text(
        _render_gap_commands_sh(plan),
        encoding="utf-8",
    )
    return plan


def _peoc_section(sections: dict[object, object], name: str) -> JsonDict:
    value = sections.get(name)
    return value if isinstance(value, dict) else {}


def _peoc_section_status(sections: dict[object, object], name: str) -> str:
    return str(_peoc_section(sections, name).get("status") or "missing")


def _peoc_hard_evaluation_action(*, source_status: str) -> JsonDict:
    return {
        "concept": "hard prompt evaluation",
        "required_inputs": [
            "PEOC hard-prompt evaluation configuration",
            "matching task/model/seed evaluation samples",
        ],
        "command": (
            "<PEOC-hard-evaluation-rerun-command writing "
            "peoc_reruns/hard_evaluation_summary.usable.json>"
        ),
        "artifact": "peoc_reruns/hard_evaluation_summary.usable.json",
        "explains": (
            "Re-collects a future usable hard-prompt aggregate because the imported hard "
            f"evaluation status is {source_status}; it does not infer a universally best method."
        ),
    }


def _peoc_soft_evaluation_action(*, source_status: str) -> JsonDict:
    return {
        "concept": "segmented soft evaluation",
        "required_inputs": [
            "PEOC segmented-soft experiment configuration",
            "non-empty task/model evaluation samples",
        ],
        "command": (
            "<PEOC-segmented-soft-rerun-command writing "
            "peoc_reruns/summary_soft_segmented.usable.json>"
        ),
        "artifact": "peoc_reruns/summary_soft_segmented.usable.json",
        "explains": (
            "Re-collects a future usable segmented-soft summary with finite, positive-count "
            f"results because the imported soft evaluation status is {source_status}."
        ),
    }


def _peoc_trajectory_action(*, source_status: str) -> JsonDict:
    return {
        "concept": "trajectory replication",
        "required_inputs": [
            "PEOC stationary and heterogeneous trajectory summaries",
            "matching model/seed raw trajectory references",
        ],
        "command": (
            "<PEOC-trajectory-rerun-command writing "
            "peoc_reruns/trajectory_replication_summary.json>"
        ),
        "artifact": "peoc_reruns/trajectory_replication_summary.json",
        "explains": (
            "Re-collects a complete paired trajectory summary because the imported trajectory "
            f"evidence status is {source_status}."
        ),
    }


def _peoc_stage_action(*, source_status: str) -> JsonDict:
    return {
        "concept": "stage heterogeneity validation",
        "required_inputs": [
            "PEOC stage-heterogeneity validation configuration",
            "held-out validation cells and rerun seeds",
        ],
        "command": (
            "<PEOC-stage-heterogeneity-rerun-command writing "
            "peoc_reruns/stage_heterogeneity_validation.usable.json>"
        ),
        "artifact": "peoc_reruns/stage_heterogeneity_validation.usable.json",
        "explains": (
            "Records a future usable validation rerun because the imported stage-heterogeneity "
            f"status is {source_status}; the imported result remains negative or incomplete."
        ),
    }


def _peoc_riccati_action(*, source_status: str) -> JsonDict:
    return {
        "concept": "Riccati surrogate",
        "required_inputs": ["inputs/hidden_states.npz"],
        "command": "pcl riccati --trajectory inputs/hidden_states.npz --out peoc_reruns",
        "artifact": "peoc_reruns/riccati.json",
        "explains": (
            "Creates a fresh fitted surrogate diagnostic because the imported Riccati evidence "
            f"status is {source_status}; it does not validate the operational model itself."
        ),
    }


def _peoc_soft_hard_action(*, source_status: str) -> JsonDict:
    return {
        "concept": "soft-to-hard projection gap",
        "required_inputs": ["inputs/soft_prompt.npz", "inputs/vocab_embeddings.npz"],
        "command": (
            "pcl soft-hard --soft inputs/soft_prompt.npz "
            "--vocab inputs/vocab_embeddings.npz --out peoc_reruns"
        ),
        "artifact": "peoc_reruns/soft_hard.json",
        "explains": (
            "Creates a fresh deployment-gap diagnostic because the imported soft-to-hard "
            f"evidence status is {source_status}."
        ),
    }


def write_research_gap_status(*, run_dir: Path, out_path: Path | None = None) -> JsonDict:
    """Check whether actions in ``research_gap_plan.json`` have been completed."""

    plan_path = run_dir / "research_gap_plan.json"
    if not plan_path.exists():
        msg = f"No research_gap_plan.json found in {run_dir}. Run `pcl diagnose --run {run_dir}`."
        raise ValueError(msg)
    plan = read_json(plan_path)
    actions = _remediation_list(plan.get("actions"))
    rows = [_gap_status_row(run_dir=run_dir, action=action) for action in actions]
    missing = [row for row in rows if row["status"] != "present"]
    payload: JsonDict = {
        "kind": "research_gap_status",
        "run_dir": str(run_dir),
        "plan_path": str(plan_path),
        "status": "complete" if not missing else "needs_work",
        "action_count": len(rows),
        "complete_count": len(rows) - len(missing),
        "missing_count": len(missing),
        "actions": rows,
        "boundary": (
            "This status only checks whether the expected artifact files exist. It does not "
            "judge whether the diagnostic is scientifically sufficient."
        ),
    }
    json_path = _gap_status_json_path(run_dir=run_dir, out_path=out_path)
    md_path = json_path.with_suffix(".md")
    html_path = json_path.with_suffix(".html")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["html_path"] = str(html_path)
    ensure_dir(json_path.parent)
    write_json(json_path, payload)
    md_path.write_text(_render_research_gap_status_markdown(payload), encoding="utf-8")
    html_path.write_text(render_research_gap_status_html(payload), encoding="utf-8")
    write_research_bundle_index(json_path.parent)
    return payload


def _gap_status_json_path(*, run_dir: Path, out_path: Path | None) -> Path:
    if out_path is None:
        return run_dir / "research_gap_status.json"
    if out_path.suffix:
        return out_path
    return out_path / "research_gap_status.json"


def _gap_status_row(*, run_dir: Path, action: JsonDict) -> JsonDict:
    artifact = str(action.get("artifact") or "")
    artifact_path = run_dir / artifact if artifact else run_dir
    exists = bool(artifact and artifact_path.exists())
    required = action.get("required_inputs")
    return {
        "step": action.get("step"),
        "concept": action.get("concept", ""),
        "status": "present" if exists else "missing",
        "artifact": artifact,
        "artifact_path": str(artifact_path),
        "required_inputs": required if isinstance(required, list) else [],
        "command": action.get("command", ""),
        "explains": action.get("explains", ""),
    }


def _build_research_gap_plan(payload: JsonDict) -> JsonDict:
    actions = _gap_actions_from_payload(payload)
    return {
        "kind": "research_gap_plan",
        "run_dir": payload.get("run_dir"),
        "diagnostic_type": payload.get("diagnostic_type", payload.get("mode")),
        "action_count": len(actions),
        "actions": actions,
        "boundary": (
            "This plan is a copy-paste guide for collecting missing paper-derived evidence. "
            "Commands with placeholders must be edited before use; no missing diagnostic is "
            "treated as measured until its artifact exists."
        ),
    }


def _gap_actions_from_payload(payload: JsonDict) -> list[JsonDict]:
    diagnostics = payload.get("diagnostics")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    ecosystem = diagnostics_dict.get("ecosystem_bridge")
    if isinstance(ecosystem, dict):
        return _numbered_actions(_remediation_list(ecosystem.get("paper_gap_remediation")))
    external = diagnostics_dict.get("external_bridge")
    if isinstance(external, dict):
        return _numbered_actions(_remediation_list(external.get("paper_gap_remediation")))

    present = {
        "soft-to-hard projection gap": isinstance(diagnostics_dict.get("soft_hard"), dict),
        "HuggingFace hidden-state extraction": _has_hidden_state_input(payload),
        "hidden-state trajectory": isinstance(diagnostics_dict.get("trajectory"), dict),
        "Riccati surrogate": isinstance(diagnostics_dict.get("riccati"), dict),
        "time-varying soft-control lane": isinstance(diagnostics_dict.get("tv_soft"), dict),
    }
    actions = [
        _paper_remediation_for(concept)
        for concept, is_present in present.items()
        if not is_present and _paper_remediation_for(concept)
    ]
    return _numbered_actions(actions)


def _has_hidden_state_input(payload: JsonDict) -> bool:
    artifacts = payload.get("artifacts")
    artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
    if artifacts_dict.get("hidden_states"):
        return True
    inputs = payload.get("inputs")
    inputs_dict = inputs if isinstance(inputs, dict) else {}
    return isinstance(inputs_dict.get("hidden_states"), dict)


def _numbered_actions(actions: list[JsonDict]) -> list[JsonDict]:
    numbered: list[JsonDict] = []
    for index, action in enumerate(actions, start=1):
        row = dict(action)
        row["step"] = index
        numbered.append(row)
    return numbered
