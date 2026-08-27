"""Interactive allowlisted workflow controls for the local dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from promptcontrollab.core.files import JsonDict
from promptcontrollab.integrations.ui.navigation import _choice_labels, _choice_value
from promptcontrollab.integrations.ui.shared import (
    _confirm_checkbox,
    _optional_bool_label,
    _optional_path,
    _render_workflow_result,
    _split_lines,
)
from promptcontrollab.integrations.ui.workflows import (
    build_agent_run_workflow,
    create_demo_artifacts_workflow,
    export_report_zip_workflow,
    run_analyze_workflow,
    run_audit_workflow,
    run_evidence_card_workflow,
    run_external_evidence_workflow,
    run_gate_workflow,
    run_guard_workflow,
    run_import_external_workflow,
    run_pr_summary_workflow,
)


def _render_workflows_tab(
    st: Any,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    detail: JsonDict,
    runs_dir: Path,
    execution_mode: str,
    overwrite: bool,
    allow_external_outputs: bool,
) -> None:
    """Render workflows tab content without changing dashboard state."""
    run_path = Path(str(detail.get("path") or runs_dir / "quick"))
    st.info(text["write_boundary"])
    demo_confirmed = _confirm_checkbox(st, text, execution_mode, "wf_demo_confirm")
    if st.button(text["create_demo"], key="wf_create_demo"):
        _render_workflow_result(
            st,
            text,
            lambda: create_demo_artifacts_workflow(
                runs_dir=runs_dir,
                execution_mode=execution_mode,
                confirmed=demo_confirmed,
                overwrite=overwrite,
                safe_root=runs_dir,
                allow_external_outputs=allow_external_outputs,
            ),
        )
    with st.expander(text["guard_workflow"], expanded=True):
        prompt = st.text_area(
            text["prompt"],
            "Fix this bug in auth/session.py and run tests.",
            height=100,
            key="wf_guard_prompt",
        )
        out_dir = Path(st.text_input(text["out_dir"], str(runs_dir / "guard"), key="wf_guard_out"))
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_guard_confirm")
        if st.button(text["run_action"], key="wf_guard_run"):
            _render_workflow_result(
                st,
                text,
                lambda: run_guard_workflow(
                    prompt=prompt,
                    out_dir=out_dir,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    policy_path=policy_path,
                    language=language,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["analyze_workflow"]):
        data_path = Path(st.text_input(text["data_path"], "examples/tasks.jsonl", key="wf_data"))
        baseline_path = Path(
            st.text_input(
                text["baseline_predictions"],
                "examples/predictions_baseline.jsonl",
                key="wf_baseline",
            )
        )
        candidate_path = Path(
            st.text_input(
                text["candidate_predictions"],
                "examples/predictions_candidate.jsonl",
                key="wf_candidate",
            )
        )
        out_dir = Path(
            st.text_input(text["out_dir"], str(runs_dir / "quick"), key="wf_analyze_out")
        )
        metric = st.text_input(text["metric"], "exact_match", key="wf_metric")
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_analyze_confirm")
        if st.button(text["run_action"], key="wf_analyze_run"):
            _render_workflow_result(
                st,
                text,
                lambda: run_analyze_workflow(
                    data_path=data_path,
                    baseline_predictions_path=baseline_path,
                    candidate_predictions_path=candidate_path,
                    out_dir=out_dir,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    policy_path=policy_path,
                    metric=metric,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["gate_workflow"]):
        selected_run_dir = Path(st.text_input(text["run_dir"], str(run_path), key="wf_gate_run"))
        gate_policy = Path(
            st.text_input(
                text["policy_path"],
                str(policy_path or Path("examples/gate.policy.yaml")),
                key="wf_gate_policy",
            )
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_gate_confirm")
        if st.button(text["run_action"], key="wf_gate_run_button"):
            _render_workflow_result(
                st,
                text,
                lambda: run_gate_workflow(
                    run_dir=selected_run_dir,
                    policy_path=gate_policy,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["evidence_card_workflow"]):
        selected_run_dir = Path(
            st.text_input(text["run_dir"], str(run_path), key="wf_evidence_run")
        )
        markdown_path = _optional_path(
            st.text_input(
                text["markdown_path"],
                str(selected_run_dir / "evidence_card.md"),
                key="wf_evidence_md",
            )
        )
        json_path = _optional_path(
            st.text_input(
                text["json_path"],
                str(selected_run_dir / "evidence_card.json"),
                key="wf_evidence_json",
            )
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_evidence_confirm")
        if st.button(text["run_action"], key="wf_evidence_run_button"):
            _render_workflow_result(
                st,
                text,
                lambda: run_evidence_card_workflow(
                    run_dir=selected_run_dir,
                    markdown_path=markdown_path,
                    json_path=json_path,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["import_workflow"]):
        tool_label = str(
            st.selectbox(
                text["external_tool"],
                _choice_labels("import_tool", language),
                key="wf_import_tool",
            )
        )
        import_tool = str(_choice_value("import_tool", tool_label, language))
        input_path = Path(
            st.text_input(
                text["external_input"],
                "results.json",
                key="wf_import_input",
            )
        )
        out_dir = Path(
            st.text_input(
                text["out_dir"],
                str(runs_dir / "from-external"),
                key="wf_import_out",
            )
        )
        columns = st.columns(4)
        prompt_id = columns[0].text_input(text["prompt_id"], "", key="wf_import_prompt_id")
        name_filter = columns[1].text_input(text["name_filter"], "", key="wf_import_name")
        experiment_filter = columns[2].text_input(
            text["experiment_filter"],
            "",
            key="wf_import_experiment",
        )
        score_name = columns[3].text_input(text["score_name"], "", key="wf_import_score")
        columns = st.columns(4)
        provider = columns[0].text_input(text["provider"], "", key="wf_import_provider")
        model = columns[1].text_input(text["model"], "", key="wf_import_model")
        method = columns[2].text_input(text["method"], "", key="wf_import_method")
        asset_id = columns[3].text_input(text["asset_id"], "", key="wf_import_asset_id")
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_import_confirm")
        if st.button(text["run_action"], key="wf_import_run_button"):
            _render_workflow_result(
                st,
                text,
                lambda: run_import_external_workflow(
                    tool=import_tool,
                    input_path=input_path,
                    out_dir=out_dir,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    prompt_id=prompt_id.strip() or None,
                    name=name_filter.strip() or None,
                    experiment=experiment_filter.strip() or None,
                    score_name=score_name.strip() or None,
                    provider=provider.strip() or None,
                    model=model.strip() or None,
                    method=method.strip() or None,
                    asset_id=asset_id.strip() or None,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["external_evidence_workflow"]):
        tool_label = str(
            st.selectbox(
                text["external_tool"],
                _choice_labels("external_tool", language),
                key="wf_external_tool",
            )
        )
        external_tool = str(_choice_value("external_tool", tool_label, language))
        baseline_input = Path(
            st.text_input(
                text["baseline_input"],
                "results.json",
                key="wf_external_baseline_input",
            )
        )
        candidate_input = Path(
            st.text_input(
                text["candidate_input"],
                "results.json",
                key="wf_external_candidate_input",
            )
        )
        out_dir = Path(
            st.text_input(
                text["out_dir"],
                str(runs_dir / "external-evidence"),
                key="wf_external_out",
            )
        )
        columns = st.columns(3)
        baseline_prompt_id = columns[0].text_input(
            text["baseline_prompt_id"],
            "baseline",
            key="wf_external_baseline_prompt_id",
        )
        candidate_prompt_id = columns[1].text_input(
            text["candidate_prompt_id"],
            "candidate",
            key="wf_external_candidate_prompt_id",
        )
        score_name = columns[2].text_input(
            text["score_name"],
            "",
            key="wf_external_score_name",
        )
        columns = st.columns(3)
        provider = columns[0].text_input(text["provider"], "", key="wf_external_provider")
        model = columns[1].text_input(text["model"], "", key="wf_external_model")
        split_hash = columns[2].text_input(text["split_hash"], "", key="wf_external_split_hash")
        columns = st.columns(2)
        bootstrap_samples = int(
            columns[0].number_input(
                text["bootstrap_samples"],
                min_value=1,
                value=100,
                key="wf_external_bootstrap",
            )
        )
        permutation_samples = int(
            columns[1].number_input(
                text["permutation_samples"],
                min_value=1,
                value=100,
                key="wf_external_permutation",
            )
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_external_confirm")
        if st.button(text["run_action"], key="wf_external_run_button"):
            _render_workflow_result(
                st,
                text,
                lambda: run_external_evidence_workflow(
                    tool=external_tool,
                    baseline_input=baseline_input,
                    candidate_input=candidate_input,
                    out_dir=out_dir,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    score_name=score_name.strip() or None,
                    provider=provider.strip() or None,
                    model=model.strip() or None,
                    baseline_prompt_id=baseline_prompt_id.strip() or None,
                    candidate_prompt_id=candidate_prompt_id.strip() or None,
                    split_hash=split_hash.strip() or None,
                    bootstrap_samples=bootstrap_samples,
                    permutation_samples=permutation_samples,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["audit_workflow"]):
        repo = Path(st.text_input(text["repo"], ".", key="wf_audit_repo"))
        before = st.text_input(text["before"], "HEAD~1", key="wf_audit_before")
        after = st.text_input(text["after"], "HEAD", key="wf_audit_after")
        out_dir = Path(st.text_input(text["out_dir"], str(runs_dir / "audit"), key="wf_audit_out"))
        tests_run = _split_lines(st.text_area(text["tests_run"], "", key="wf_tests_run"))
        tests_passed_label = str(
            st.selectbox(
                text["tests_passed"],
                _choice_labels("tests_passed", language),
                key="wf_tests_passed",
            )
        )
        tests_passed = _optional_bool_label(
            _choice_value("tests_passed", tests_passed_label, language)
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_audit_confirm")
        if st.button(text["run_action"], key="wf_audit_run"):
            _render_workflow_result(
                st,
                text,
                lambda: run_audit_workflow(
                    repo=repo,
                    before=before,
                    after=after,
                    out_dir=out_dir,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    tests_run=tests_run,
                    tests_passed=tests_passed,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["agent_run_workflow"]):
        selected_run_dir = Path(st.text_input(text["run_dir"], str(run_path), key="wf_agent_run"))
        audit_dir = Path(
            st.text_input(text["audit_dir"], str(runs_dir / "audit"), key="wf_agent_audit")
        )
        agent = st.text_input(text["agent"], "codex", key="wf_agent")
        out_path = Path(
            st.text_input(
                text["agent_run_path"],
                str(selected_run_dir / "agent_run.json"),
                key="wf_agent_out",
            )
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_agent_confirm")
        if st.button(text["run_action"], key="wf_agent_run_button"):
            _render_workflow_result(
                st,
                text,
                lambda: build_agent_run_workflow(
                    run_dir=selected_run_dir,
                    audit_dir=audit_dir,
                    agent=agent,
                    out_path=out_path,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    policy=str(policy_path) if policy_path is not None else None,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["pr_summary_workflow"]):
        audit_path = _optional_path(
            st.text_input(
                text["audit_dir"],
                str(runs_dir / "audit" / "audit_result.json"),
                key="wf_pr_audit",
            )
        )
        gate_path = _optional_path(
            st.text_input(
                text["run_dir"],
                str(run_path / "gate_result.json"),
                key="wf_pr_gate",
            )
        )
        agent_run_path = _optional_path(
            st.text_input(
                text["agent_run_path"],
                str(run_path / "agent_run.json"),
                key="wf_pr_agent",
            )
        )
        markdown_path = _optional_path(
            st.text_input(text["markdown_path"], str(run_path / "pr_summary.md"), key="wf_pr_md")
        )
        json_path = _optional_path(
            st.text_input(text["json_path"], str(run_path / "pr_summary.json"), key="wf_pr_json")
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_pr_confirm")
        if st.button(text["run_action"], key="wf_pr_run"):
            _render_workflow_result(
                st,
                text,
                lambda: run_pr_summary_workflow(
                    audit_path=audit_path,
                    gate_path=gate_path,
                    agent_run_path=agent_run_path,
                    markdown_path=markdown_path,
                    json_path=json_path,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )

    with st.expander(text["export_workflow"]):
        selected_run_dir = Path(st.text_input(text["run_dir"], str(run_path), key="wf_zip_run"))
        zip_path = Path(
            st.text_input(text["zip_path"], str(selected_run_dir / "report.zip"), key="wf_zip")
        )
        confirmed = _confirm_checkbox(st, text, execution_mode, "wf_zip_confirm")
        if st.button(text["run_action"], key="wf_zip_run_button"):
            _render_workflow_result(
                st,
                text,
                lambda: export_report_zip_workflow(
                    run_dir=selected_run_dir,
                    zip_path=zip_path,
                    execution_mode=execution_mode,
                    confirmed=confirmed,
                    overwrite=overwrite,
                    safe_root=runs_dir,
                    allow_external_outputs=allow_external_outputs,
                ),
            )
