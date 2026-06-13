"""Streamlit app for the local prompt_control_lab dashboard."""
# ruff: noqa: E501,RUF001

from __future__ import annotations

import base64
import html
import importlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from promptcontrollab.files import JsonDict
from promptcontrollab.prompt_context import load_prompt_context
from promptcontrollab.prompt_guard import guard_prompt
from promptcontrollab.ui.charts import (
    file_breakdown_bar,
    history_category_timeline,
    history_numeric_trend,
    research_diagnostic_bar,
    risk_category_bar,
    score_delta_ci,
    slice_score_heatmap,
)
from promptcontrollab.ui.components import (
    badge,
    dashboard_css,
    empty_state,
    evidence_ladder_html,
    metric_cards,
    paper_card_html,
    prompt_diff,
    research_evidence_map_html,
    stat_card_html,
)
from promptcontrollab.ui.data import (
    audit_detail_sections,
    changed_line_rows,
    claim_check_summary,
    claim_evidence_ladder,
    ecosystem_demo_rows,
    ecosystem_scorecard_rows,
    evidence_card_rows,
    evidence_gap_action_rows,
    evidence_gap_rows,
    external_bridge_summary,
    filter_history_rows,
    first_comparison,
    guard_download_payloads,
    history_rows,
    list_runs,
    load_run_detail,
    model_rows,
    research_diagnostic_rows,
    research_evidence_map,
    research_gap_plan_rows,
    research_gap_script_rows,
    research_gap_status_rows,
    research_status_counts,
    slice_rows,
)
from promptcontrollab.ui.workflows import (
    build_agent_run_workflow,
    create_demo_artifacts_workflow,
    export_report_zip_workflow,
    run_analyze_workflow,
    run_audit_workflow,
    run_evidence_card_workflow,
    run_external_evidence_workflow,
    run_gate_workflow,
    run_guard_workflow,
    run_pr_summary_workflow,
    save_guard_outputs,
)

TEXT = {
    "en": {
        "title": "prompt_control_lab dashboard",
        "subtitle": "Local preflight, provenance, and audit views. No artifacts are uploaded.",
        "research": "Research Overview",
        "research_title": "Control diagnostics for prompt optimization",
        "research_subtitle": (
            "A paper-first view of tri-split evaluation, paired statistics, "
            "soft-hard gap, trajectory, Riccati surrogate, and time-varying soft-control."
        ),
        "research_empty": "No research diagnostics found for this run.",
        "research_demo_command": "pcl research-demo --out runs/research-demo",
        "research_pipeline": "Research workflow",
        "research_evidence_map": "Research evidence map",
        "research_diagnostics": "Paper-derived diagnostics",
        "research_coverage": "Diagnostic coverage",
        "paper_protocol": "Protocol hygiene",
        "diagnostic_coverage": "Diagnostics ready",
        "artifact_evidence": "Evidence artifacts",
        "evidence_card": "Evidence card",
        "evidence_card_missing": "No evidence_card.json found yet.",
        "evidence_card_command": "pcl evidence-card --run <selected-run>",
        "claim_check": "Claim check",
        "claim_ladder": "Evidence ladder",
        "claim_check_missing": "No claim_check.json found yet.",
        "claim_check_command": "pcl claim-check --run <selected-run> --claim full-research",
        "claim_check_status": "Claim status",
        "claim_check_requested": "Requested claim",
        "claim_check_tier": "Evidence tier",
        "claim_check_safe": "Safe claim",
        "claim_check_reason": "Reason",
        "claim_check_next_missing": "Missing for next tier",
        "ecosystem_bridge": "Ecosystem bridge",
        "ecosystem_scorecard": "Ecosystem scorecard",
        "ecosystem_demo": "Ecosystem demo bundles",
        "evidence_gap_diagnosis": "Paper evidence gap diagnosis",
        "evidence_gap_actions": "How to close these gaps",
        "research_gap_plan": "Research gap plan",
        "research_gap_scripts": "Review-first command scripts",
        "research_gap_status": "Research gap closure status",
        "ecosystem_bridge_missing": "No external evidence bridge artifact found.",
        "external_tools": "External tools",
        "pcl_added_evidence": "PCL-added evidence",
        "missing_evidence": "Missing evidence",
        "bridge_next_actions": "Bridge next actions",
        "evidence_recommendation": "Evidence recommendation",
        "evidence_summary": "Evidence summary",
        "evidence_sections": "Evidence card sections",
        "hidden_state_input": "Hidden-state input",
        "research_boundary": (
            "These diagnostics make prompt experiments easier to inspect. They are not "
            "a proof of full language-model stability or universal prompt improvement."
        ),
        "tri_split": "Tri-split",
        "paired_stats": "Paired stats",
        "soft_hard": "Soft-hard",
        "trajectory_diag": "Trajectory",
        "riccati_diag": "Riccati",
        "tv_soft_diag": "TV-soft",
        "runs": "Runs directory",
        "policy": "Guard policy",
        "guard": "Guard Prompt",
        "workflows": "Workflows",
        "tutorial": "Tutorial",
        "tutorial_intro": (
            "Follow the cards below from top to bottom. Each card shows what to do, "
            "what artifact you get, what the result means, and what to do next."
        ),
        "tutorial_framework_note": "",
        "tutorial_operation": "Operation",
        "tutorial_result": "What you get",
        "tutorial_meaning": "What it means",
        "tutorial_next_step": "Next step",
        "tutorial_command": "CLI equivalent",
        "tutorial_steps": "Steps",
        "execution_mode": "Execution mode",
        "overwrite": "Overwrite existing artifacts",
        "allow_external_outputs": "Allow writing outside runs directory",
        "write_boundary": (
            "Workflow writes should stay under the selected runs directory. "
            "External output paths are warned and blocked in auto mode unless explicitly allowed."
        ),
        "confirm_write": "Confirm write",
        "run_action": "Run",
        "create_demo": "Create demo artifacts",
        "workflow_preview": "Preview",
        "workflow_result": "Workflow result",
        "guard_workflow": "Guard prompt",
        "analyze_workflow": "Run analyze",
        "gate_workflow": "Run gate",
        "evidence_card_workflow": "Build evidence card",
        "external_evidence_workflow": "External evidence bundle",
        "audit_workflow": "Run audit-diff",
        "agent_run_workflow": "Build agent-run",
        "pr_summary_workflow": "Generate PR summary",
        "export_workflow": "Export report zip",
        "external_tool": "External tool",
        "baseline_input": "Baseline export",
        "candidate_input": "Candidate export",
        "score_name": "Score name",
        "provider": "Provider",
        "model": "Model",
        "baseline_prompt_id": "Baseline prompt ID",
        "candidate_prompt_id": "Candidate prompt ID",
        "baseline_name": "Baseline name",
        "candidate_name": "Candidate name",
        "baseline_experiment": "Baseline experiment",
        "candidate_experiment": "Candidate experiment",
        "split_hash": "Split hash",
        "bootstrap_samples": "Bootstrap samples",
        "permutation_samples": "Permutation samples",
        "out_dir": "Output directory",
        "data_path": "Task JSONL",
        "baseline_predictions": "Baseline predictions",
        "candidate_predictions": "Candidate predictions",
        "metric": "Metric",
        "policy_path": "Policy path",
        "run_dir": "Run directory",
        "repo": "Repository",
        "before": "Before ref",
        "after": "After ref",
        "tests_run": "Recorded tests",
        "audit_dir": "Audit directory",
        "agent": "Agent",
        "agent_run_path": "agent_run.json path",
        "markdown_path": "Markdown path",
        "json_path": "JSON path",
        "zip_path": "Zip path",
        "report": "Run Report",
        "drift": "Model Drift",
        "audit": "Agent Diff Audit",
        "history": "History",
        "prompt": "Prompt",
        "run_guard": "Run guard",
        "selected_run": "Selected run",
        "missing_run": "No run directories found.",
        "empty_run": "This run has no recognized artifacts.",
        "decision": "Decision",
        "risk": "Risk",
        "review": "Required review",
        "categories": "Risk categories",
        "violations": "Policy violations",
        "token_cost": "Estimated token cost",
        "diff": "Prompt diff",
        "recommendation": "Recommendation",
        "gate": "Gate status",
        "candidate_score": "Candidate score",
        "comparison_validity": "Comparison validity",
        "prompt_only": "Prompt-only",
        "mean_delta": "Mean delta",
        "p_value": "p-value",
        "model_provenance": "Model provenance",
        "drift_risk": "Drift risk",
        "audit_review": "Human review required",
        "dangerous_paths": "Dangerous paths",
        "changed_files": "Changed files",
        "profile": "Profile",
        "mode": "Mode",
        "token_mode": "Token mode",
        "max_tokens": "Max tokens",
        "guarded_prompt": "Guarded prompt",
        "save_guard": "Save guard artifacts",
        "save_guard_dir": "Guard save directory",
        "saved_guard": "Saved guard artifacts",
        "download_guard_json": "Download guard_result.json",
        "download_improved_prompt": "Download improved_prompt.txt",
        "risk_chart": "Risk Categories",
        "count": "count",
        "category": "category",
        "none": "none",
        "score_ci": "Score Delta CI",
        "slice_scores": "Slice Scores",
        "baseline": "baseline",
        "candidate": "candidate",
        "model_timeline": "Model timeline",
        "no_model": "No model provenance recorded.",
        "no_audit": "No audit_result.json found.",
        "public_api": "Public API",
        "tests_passed": "Tests passed",
        "file_breakdown": "Touched Files Breakdown",
        "file_kind": "kind",
        "source_files": "source",
        "test_files": "tests",
        "docs_files": "docs",
        "config_files": "config",
        "path": "path",
        "no_history": "No history_index.json found.",
        "run_timeline": "Run timeline",
        "gate_trend": "Gate trend",
        "score_trend": "Score trend",
        "risk_trend": "Risk trend",
        "review_trend": "Review trend",
        "prompt_identity": "Prompt identity",
        "model_changes": "Model/provider changes",
        "audit_details": "Audit details",
        "secret_findings": "Secret findings",
        "dependency_files": "Dependency files",
        "lockfiles": "Lockfiles",
        "workflow_files": "Workflow files",
        "deleted_test_files": "Deleted test files",
        "unexpected_files": "Unexpected files",
        "test_results": "Test results",
        "changed_lines": "Changed lines",
        "file": "file",
        "added": "added",
        "deleted": "deleted",
        "only_review_required": "Only review-required runs",
        "only_high_risk": "Only high-risk runs",
        "provider_filter": "Provider filter",
        "model_filter": "Model filter",
        "risk_categories": "Risk categories",
    },
    "zh": {
        "title": "prompt_control_lab 本地仪表盘",
        "subtitle": "面向 prompt 优化的研究诊断、可复现评测和本地 agent 审计视图。不会上传 prompt、代码或 artifact。",
        "research": "研究总览",
        "research_title": "Prompt 优化的控制论诊断工作台",
        "research_subtitle": (
            "以论文功能为主线查看 tri-split、成对统计、soft-hard gap、trajectory、"
            "Riccati surrogate 和 time-varying soft-control。"
        ),
        "research_empty": "当前 run 还没有研究诊断 artifact。",
        "research_demo_command": "pcl research-demo --out runs/research-demo",
        "research_pipeline": "研究流程",
        "research_evidence_map": "研究证据地图",
        "research_diagnostics": "论文诊断模块",
        "research_coverage": "诊断覆盖情况",
        "paper_protocol": "协议洁净度",
        "diagnostic_coverage": "已完成诊断",
        "artifact_evidence": "证据 artifact",
        "evidence_card": "证据卡",
        "evidence_card_missing": "当前还没有 evidence_card.json。",
        "evidence_card_command": "pcl evidence-card --run <选中的 run>",
        "claim_check": "主张检查",
        "claim_ladder": "证据阶梯",
        "claim_check_missing": "当前还没有 claim_check.json。",
        "claim_check_command": "pcl claim-check --run <选中的 run> --claim full-research",
        "claim_check_status": "主张状态",
        "claim_check_requested": "请求主张",
        "claim_check_tier": "证据层级",
        "claim_check_safe": "安全主张",
        "claim_check_reason": "原因",
        "claim_check_next_missing": "下一层级缺失证据",
        "ecosystem_bridge": "生态桥接",
        "ecosystem_scorecard": "生态证据总览",
        "ecosystem_demo": "生态 demo 证据包",
        "evidence_gap_diagnosis": "论文证据缺口诊断",
        "evidence_gap_actions": "如何补齐这些缺口",
        "research_gap_plan": "研究证据缺口计划",
        "research_gap_scripts": "Review-first 命令脚本",
        "research_gap_status": "研究缺口补齐状态",
        "ecosystem_bridge_missing": "当前还没有外部证据桥接 artifact。",
        "external_tools": "外部工具",
        "pcl_added_evidence": "PCL 补充证据",
        "missing_evidence": "缺失证据",
        "bridge_next_actions": "桥接后下一步",
        "evidence_recommendation": "证据推荐",
        "evidence_summary": "证据摘要",
        "evidence_sections": "证据卡分段",
        "hidden_state_input": "hidden-state 输入",
        "research_boundary": (
            "这些诊断让 prompt 实验更容易被检查和复现，但它们不是完整语言模型稳定性"
            "或通用 prompt 提升的数学证明。"
        ),
        "tri_split": "三段切分",
        "paired_stats": "成对统计",
        "soft_hard": "软转硬",
        "trajectory_diag": "轨迹诊断",
        "riccati_diag": "Riccati",
        "tv_soft_diag": "TV-soft",
        "runs": "Runs 目录",
        "policy": "Guard 策略",
        "guard": "Prompt 守护",
        "workflows": "工作流",
        "tutorial": "教程",
        "tutorial_intro": (
            "建议从上到下阅读。每个卡片都会说明：怎么操作、会得到什么文件、"
            "这个结果说明什么问题，以及下一步该怎么做。"
        ),
        "tutorial_framework_note": "",
        "tutorial_operation": "操作",
        "tutorial_result": "得到什么",
        "tutorial_meaning": "说明什么问题",
        "tutorial_next_step": "下一步",
        "tutorial_command": "CLI 等价命令",
        "tutorial_steps": "操作步骤",
        "execution_mode": "执行模式",
        "overwrite": "覆盖已有 artifact",
        "allow_external_outputs": "允许写入 runs 目录之外",
        "write_boundary": (
            "工作流默认应写入当前 runs 目录下。"
            "外部输出路径会提示风险, 并在 auto 模式下被阻止, 除非显式允许。"
        ),
        "confirm_write": "确认写入",
        "run_action": "运行",
        "create_demo": "创建 demo artifact",
        "workflow_preview": "预览",
        "workflow_result": "工作流结果",
        "guard_workflow": "守护 Prompt",
        "analyze_workflow": "运行 analyze",
        "gate_workflow": "运行 gate",
        "evidence_card_workflow": "生成证据卡",
        "external_evidence_workflow": "生成外部证据包",
        "audit_workflow": "运行 audit-diff",
        "agent_run_workflow": "生成 agent-run",
        "pr_summary_workflow": "生成 PR summary",
        "export_workflow": "导出报告 zip",
        "external_tool": "外部工具",
        "baseline_input": "Baseline 导出文件",
        "candidate_input": "Candidate 导出文件",
        "score_name": "分数字段名",
        "provider": "Provider",
        "model": "模型",
        "baseline_prompt_id": "Baseline prompt ID",
        "candidate_prompt_id": "Candidate prompt ID",
        "baseline_name": "Baseline 名称",
        "candidate_name": "Candidate 名称",
        "baseline_experiment": "Baseline 实验名",
        "candidate_experiment": "Candidate 实验名",
        "split_hash": "Split hash",
        "bootstrap_samples": "Bootstrap 采样数",
        "permutation_samples": "Permutation 采样数",
        "out_dir": "输出目录",
        "data_path": "任务 JSONL",
        "baseline_predictions": "Baseline predictions",
        "candidate_predictions": "Candidate predictions",
        "metric": "指标",
        "policy_path": "策略路径",
        "run_dir": "Run 目录",
        "repo": "仓库",
        "before": "Before ref",
        "after": "After ref",
        "tests_run": "已记录测试",
        "audit_dir": "Audit 目录",
        "agent": "Agent",
        "agent_run_path": "agent_run.json 路径",
        "markdown_path": "Markdown 路径",
        "json_path": "JSON 路径",
        "zip_path": "Zip 路径",
        "report": "运行报告",
        "drift": "模型漂移",
        "audit": "Agent 改动审计",
        "history": "历史",
        "prompt": "提示词",
        "run_guard": "运行守护",
        "selected_run": "选择 run",
        "missing_run": "没有找到 run 目录。",
        "empty_run": "这个 run 没有识别到 artifact。",
        "decision": "决策",
        "risk": "风险",
        "review": "需要人工复核",
        "categories": "风险类别",
        "violations": "策略违规",
        "token_cost": "估算 token 成本",
        "diff": "Prompt 差异",
        "recommendation": "部署建议",
        "gate": "门禁状态",
        "candidate_score": "候选分数",
        "comparison_validity": "比较有效性",
        "prompt_only": "Prompt-only",
        "mean_delta": "均值差异",
        "p_value": "p-value",
        "model_provenance": "模型来源",
        "drift_risk": "漂移风险",
        "audit_review": "需要人工复核",
        "dangerous_paths": "危险路径",
        "changed_files": "改动文件",
        "profile": "场景",
        "mode": "模式",
        "token_mode": "Token 模式",
        "max_tokens": "最大 Token",
        "guarded_prompt": "守护后的提示词",
        "save_guard": "保存 guard artifact",
        "save_guard_dir": "Guard 保存目录",
        "saved_guard": "已保存 guard artifact",
        "download_guard_json": "下载 guard_result.json",
        "download_improved_prompt": "下载 improved_prompt.txt",
        "risk_chart": "风险类别",
        "count": "数量",
        "category": "类别",
        "none": "无",
        "score_ci": "分数差异置信区间",
        "slice_scores": "任务切片分数",
        "baseline": "基线",
        "candidate": "候选",
        "model_timeline": "模型时间线",
        "no_model": "没有记录模型来源。",
        "no_audit": "没有找到 audit_result.json。",
        "public_api": "公共 API",
        "tests_passed": "测试通过",
        "file_breakdown": "改动文件类型",
        "file_kind": "类型",
        "source_files": "源码",
        "test_files": "测试",
        "docs_files": "文档",
        "config_files": "配置",
        "path": "路径",
        "no_history": "没有找到 history_index.json。",
        "run_timeline": "Run 时间线",
        "gate_trend": "门禁趋势",
        "score_trend": "分数趋势",
        "risk_trend": "风险趋势",
        "review_trend": "复核趋势",
        "prompt_identity": "Prompt 身份",
        "model_changes": "模型 / provider 变化",
        "audit_details": "审计明细",
        "secret_findings": "疑似密钥",
        "dependency_files": "依赖文件",
        "lockfiles": "锁文件",
        "workflow_files": "Workflow 文件",
        "deleted_test_files": "删除的测试文件",
        "unexpected_files": "意外文件",
        "test_results": "测试结果",
        "changed_lines": "改动行数",
        "file": "文件",
        "added": "新增",
        "deleted": "删除",
        "only_review_required": "只看需要复核的 run",
        "only_high_risk": "只看高风险 run",
        "provider_filter": "Provider 过滤",
        "model_filter": "模型过滤",
        "risk_categories": "风险类别",
    },
}

CHOICE_OPTIONS = {
    "execution_mode": [
        ("confirm", "confirm", "确认后执行"),
        ("auto", "auto", "自动执行"),
        ("command", "command", "只生成命令"),
    ],
    "profile": [
        ("coding", "coding", "编程"),
        ("general", "general", "通用"),
        ("research", "research", "研究"),
    ],
    "guard_mode": [
        ("suggest", "suggest", "给出建议"),
        ("auto", "auto", "自动改写"),
        ("gate", "gate", "门禁检查"),
    ],
    "token_mode": [
        ("balanced", "balanced", "平衡省 token"),
        ("aggressive", "aggressive", "激进省 token"),
    ],
    "tests_passed": [
        ("unknown", "unknown", "未知"),
        ("true", "true", "通过"),
        ("false", "false", "失败"),
    ],
    "external_tool": [
        ("auto", "auto", "自动识别"),
        ("promptfoo", "promptfoo", "Promptfoo"),
        ("langfuse", "langfuse", "Langfuse"),
        ("langsmith", "langsmith", "LangSmith"),
    ],
}

TUTORIAL_IMAGES = {
    "overview": ("tutorial_overview.svg", "tutorial_overview.zh.svg"),
    "guard": ("tutorial_guard.svg", "tutorial_guard.zh.svg"),
    "report": ("tutorial_report.svg", "tutorial_report.zh.svg"),
    "audit_history": ("tutorial_audit_history.svg", "tutorial_audit_history.zh.svg"),
}

TUTORIAL_SCREENSHOTS = {
    "workflows": ("tutorial_workflows.en.png", "tutorial_workflows.zh.png"),
    "guard": ("tutorial_guard.en.png", "tutorial_guard.zh.png"),
    "report": ("tutorial_report.en.png", "tutorial_report.zh.png"),
    "model_drift": ("tutorial_model_drift.en.png", "tutorial_model_drift.zh.png"),
    "audit": ("tutorial_audit.en.png", "tutorial_audit.zh.png"),
    "history": ("tutorial_history.en.png", "tutorial_history.zh.png"),
}

TUTORIAL_SECTION_SCREENSHOTS = {
    "guard": "guard",
    "workflows": "workflows",
    "report": "report",
    "drift": "model_drift",
    "audit": "audit",
    "history": "history",
    "project_defaults": "workflows",
    "export_pr": "workflows",
}

TUTORIAL_STEPS = {
    "en": {
        "guard": [
            "Open the Guard Prompt tab.",
            "Paste the prompt the agent would run.",
            "Choose the coding profile and your guard policy.",
            "Click Run guard, then read the decision, risk categories, and improved prompt.",
        ],
        "workflows": [
            "Open the Workflows tab.",
            "Keep Execution mode on confirm for the first run.",
            "Click Create demo artifacts and confirm the files that will be written.",
            "Use the generated run in Run Report, Audit, and History.",
        ],
        "report": [
            "Select a run in the sidebar.",
            "Open Run Report.",
            "Read the recommendation, gate status, score delta, confidence interval, and model provenance.",
            "Use fixed or broken examples to decide what to inspect next.",
        ],
        "drift": [
            "Open Model Drift after selecting a run.",
            "Check baseline and candidate provider/model values.",
            "If drift is unknown, run model-drift between two run directories.",
            "Treat model mismatch as a comparison-validity warning.",
        ],
        "audit": [
            "Run audit-diff after an agent changes the repository.",
            "Open Agent Diff Audit and inspect touched files, changed lines, and dangerous paths.",
            "Check dependency, workflow, secret-like, deleted-test, and unexpected-file sections.",
            "Require human review before merging high-risk changes.",
        ],
        "history": [
            "Run history index over the runs directory.",
            "Open History and filter by review-required, high-risk, provider, or model.",
            "Read score, gate, risk, and model trends together.",
            "Use the table to open the run that needs attention.",
        ],
        "project_defaults": [
            "Create or edit .promptcontrol.yaml at the repository root.",
            "Set guard_policy, gate_policy, runs_dir, expected_paths, and test_commands.",
            "Restart or refresh the UI so sidebar defaults reflect the project file.",
            "Override any default from the CLI or UI when a run needs a one-off value.",
        ],
        "export_pr": [
            "Open Workflows and select PR summary or export report zip.",
            "Review the output path before confirming the write.",
            "Attach pr_summary.md to a pull request, or archive the report zip with the run.",
            "Keep the JSON artifact for later automation.",
        ],
    },
    "zh": {
        "guard": [
            "打开“Prompt 守护”页。",
            "粘贴准备交给 Agent 执行的 prompt。",
            "选择“编程”场景和团队 guard policy。",
            "点击“运行守护”，查看决策、风险类别和改写后的 prompt。",
        ],
        "workflows": [
            "打开“工作流”页。",
            "第一次使用时保持“确认后执行”模式。",
            "点击“创建演示数据”，先检查将写入的文件，再确认执行。",
            "用生成的 run 去查看“运行报告”“审计”和“历史”。",
        ],
        "report": [
            "在侧边栏选择一个 run。",
            "打开“运行报告”页。",
            "查看部署建议、gate 状态、分数差、置信区间和模型来源。",
            "根据修复样本和失败样本决定下一步检查哪里。",
        ],
        "drift": [
            "选择 run 后打开“模型漂移”页。",
            "检查 baseline 和 candidate 的 provider/model 是否一致。",
            "如果没有 drift artifact，按页面提示运行 model-drift。",
            "如果模型不一致，把它当成 prompt-only 比较有效性的风险。",
        ],
        "audit": [
            "Agent 改完代码后运行 audit-diff。",
            "打开“Agent 改动审计”，查看改动文件、行数和危险路径。",
            "继续检查依赖、workflow、疑似密钥、删除测试和意外文件。",
            "高风险改动合并前需要人工复核。",
        ],
        "history": [
            "对 runs 目录运行 history index。",
            "打开“历史”，按需要复核、高风险、provider 或 model 过滤。",
            "把分数、gate、风险和模型趋势放在一起看。",
            "从表格中找到需要进一步检查的 run。",
        ],
        "project_defaults": [
            "在仓库根目录创建或编辑 .promptcontrol.yaml。",
            "写入 guard_policy、gate_policy、runs_dir、expected_paths 和 test_commands。",
            "刷新 UI，让侧边栏默认值跟随项目配置。",
            "需要临时覆盖时，再用 CLI 或 UI 显式传入新值。",
        ],
        "export_pr": [
            "打开“工作流”，选择生成 PR summary 或导出 report zip。",
            "确认写入路径，再执行导出。",
            "把 pr_summary.md 放进 PR，或把 report zip 和 run 一起归档。",
            "保留 JSON artifact，方便后续自动化。",
        ],
    },
}

TUTORIAL_SECTIONS = {
    "en": [
        {
            "id": "guard",
            "image": "guard",
            "title": "1. Guard a prompt before an agent runs",
            "operation": "Open Guard Prompt, paste the instruction, choose a profile and policy, then run guard.",
            "result": "`guard_result.json`, an improved prompt, risk level, policy violations, and token estimate.",
            "meaning": "You can see whether the prompt is vague, risky, too broad, or missing files/tests.",
            "next_step": "Send the improved prompt to Claude Code, Cursor, Codex, or keep editing it.",
            "command": "pcl guard --prompt \"Fix this bug\" --profile coding --policy examples/guard.policy.yaml --json",
        },
        {
            "id": "workflows",
            "image": "overview",
            "title": "2. Create demo artifacts from the UI",
            "operation": "Open Workflows and click Create demo artifacts.",
            "result": "A local demo project, `runs/demo`, reports, gate result, and `history_index.json`.",
            "meaning": "The dashboard has real artifacts to render, so every tab becomes easier to inspect.",
            "next_step": "Switch to Run Report or History and inspect the generated data.",
            "command": "pcl init --path demo && cd demo && pcl analyze --config promptcontrol.example.yaml --out runs/quick",
        },
        {
            "id": "report",
            "image": "report",
            "title": "3. Analyze, gate, and read the report",
            "operation": "Run analyze from Workflows or CLI, then run gate with a policy.",
            "result": "`metrics.json`, `stats.json`, `explanation.json`, `gate_result.json`, and report files.",
            "meaning": "You can judge whether the candidate prompt improved reliably and passed policy.",
            "next_step": "Keep the prompt, revise it, or inspect failed slices and examples.",
            "command": "pcl analyze --config promptcontrol.example.yaml --out runs/quick && pcl gate --run runs/quick --policy examples/gate.policy.yaml",
        },
        {
            "id": "drift",
            "image": "report",
            "title": "4. Check model provenance and drift",
            "operation": "Open Model Drift or run model-drift between two run directories.",
            "result": "`model_drift.json` with provider/model comparison and drift risk.",
            "meaning": "If models changed, the comparison is not a clean prompt-only comparison.",
            "next_step": "Pin model ids or rerun baseline/candidate under the same model.",
            "command": "pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json",
        },
        {
            "id": "audit",
            "image": "audit_history",
            "title": "5. Audit what the coding agent changed",
            "operation": "Run audit-diff against two git refs after an agent finishes.",
            "result": "`audit_result.json` and `audit_summary.md` with files, line counts, risks, and tests.",
            "meaning": "You can see whether the agent touched dangerous paths, dependencies, workflows, or tests.",
            "next_step": "Review high-risk files before merging, then build an agent-run manifest.",
            "command": "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
        },
        {
            "id": "history",
            "image": "audit_history",
            "title": "6. Build local run history",
            "operation": "Index a runs directory after several analyses or audits.",
            "result": "`history_index.json` with model, score, gate, prompt, and risk timeline data.",
            "meaning": "You can spot score regressions, model changes, and risky agent runs over time.",
            "next_step": "Use History filters to show only high-risk or review-required runs.",
            "command": "pcl history index --runs runs/ --out runs/history_index.json",
        },
        {
            "id": "project_defaults",
            "image": "overview",
            "title": "7. Use project defaults",
            "operation": "Keep `.promptcontrol.yaml` in the repo root for policies, runs, paths, and tests.",
            "result": "Shorter commands because guard, gate, audit-diff, and UI can read local defaults.",
            "meaning": "Teams can share the same policy and expected paths without copy-pasting flags.",
            "next_step": "Edit `.promptcontrol.yaml` when the project policy changes.",
            "command": "pcl guard --prompt \"Fix this bug\" --profile coding",
        },
        {
            "id": "export_pr",
            "image": "audit_history",
            "title": "8. Export and summarize for review",
            "operation": "Generate a PR summary or export a report zip from Workflows.",
            "result": "`pr_summary.md/json` or a zip containing recognized run artifacts.",
            "meaning": "Reviewers get a compact, shareable summary without reading every JSON file.",
            "next_step": "Attach the summary to a PR or archive the zip with the run.",
            "command": "pcl export-report --run runs/quick --out runs/quick/report.zip",
        },
    ],
    "zh": [
        {
            "id": "guard",
            "image": "guard",
            "title": "1. 在 Agent 执行前守护 Prompt",
            "operation": "打开“Prompt 守护”，粘贴指令，选择场景和策略，然后运行守护。",
            "result": "`guard_result.json`、改写后的 prompt、风险等级、策略违规和 token 估算。",
            "meaning": "你可以判断 prompt 是否模糊、危险、范围太宽，或缺少目标文件和测试计划。",
            "next_step": "把改写后的 prompt 发给 Claude Code、Cursor、Codex，或继续手动调整。",
            "command": "pcl guard --prompt \"修复这个 bug\" --profile coding --policy examples/guard.policy.yaml --json",
        },
        {
            "id": "workflows",
            "image": "overview",
            "title": "2. 一键创建演示数据",
            "operation": "打开“工作流”，点击“创建演示数据”。",
            "result": "本地 demo 项目、`runs/demo`、报告、gate 结果和 `history_index.json`。",
            "meaning": "仪表盘会有真实 artifacts 可读，所有页面都能立刻看到示例。",
            "next_step": "切到“运行报告”或“历史”，查看刚生成的数据。",
            "command": "pcl init --path demo && cd demo && pcl analyze --config promptcontrol.example.yaml --out runs/quick",
        },
        {
            "id": "report",
            "image": "report",
            "title": "3. 运行评测、门禁并阅读报告",
            "operation": "在“工作流”里运行 analyze，或用 CLI 运行 analyze，再用策略运行 gate。",
            "result": "`metrics.json`、`stats.json`、`explanation.json`、`gate_result.json` 和报告文件。",
            "meaning": "你可以判断 candidate prompt 是否真的更好，以及是否通过团队策略。",
            "next_step": "保留 prompt、继续修改，或检查退化的 slice 和失败样本。",
            "command": "pcl analyze --config promptcontrol.example.yaml --out runs/quick && pcl gate --run runs/quick --policy examples/gate.policy.yaml",
        },
        {
            "id": "drift",
            "image": "report",
            "title": "4. 检查模型来源和漂移",
            "operation": "打开“模型漂移”，或对两个 run 目录运行 model-drift。",
            "result": "`model_drift.json`，记录 provider/model 对比和漂移风险。",
            "meaning": "如果模型变了，这次比较就不是干净的 prompt-only 比较。",
            "next_step": "固定模型 id，或在同一模型下重新跑 baseline/candidate。",
            "command": "pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json",
        },
        {
            "id": "audit",
            "image": "audit_history",
            "title": "5. 审计编程 Agent 改了什么",
            "operation": "Agent 运行后，对两个 git ref 执行 audit-diff。",
            "result": "`audit_result.json` 和 `audit_summary.md`，包含文件、行数、风险和测试记录。",
            "meaning": "你能看到 Agent 是否改了危险路径、依赖、workflow 或测试文件。",
            "next_step": "合并前优先复查高风险文件，再生成 agent-run manifest。",
            "command": "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
        },
        {
            "id": "history",
            "image": "audit_history",
            "title": "6. 建立本地运行历史",
            "operation": "当你有多次分析或审计后，对 runs 目录建立索引。",
            "result": "`history_index.json`，记录模型、分数、gate、prompt 和风险时间线。",
            "meaning": "你可以发现分数退化、模型变化和高风险 Agent 运行。",
            "next_step": "用“历史”页面过滤只看高风险或需要复核的 run。",
            "command": "pcl history index --runs runs/ --out runs/history_index.json",
        },
        {
            "id": "project_defaults",
            "image": "overview",
            "title": "7. 使用项目默认配置",
            "operation": "在仓库根目录保留 `.promptcontrol.yaml`，记录策略、runs、路径和测试默认值。",
            "result": "guard、gate、audit-diff 和 UI 可以自动读取默认值，命令更短。",
            "meaning": "团队不用反复复制参数，也能共享同一套策略和预期路径。",
            "next_step": "当项目策略变化时，更新 `.promptcontrol.yaml`。",
            "command": "pcl guard --prompt \"修复这个 bug\" --profile coding",
        },
        {
            "id": "export_pr",
            "image": "audit_history",
            "title": "8. 导出报告并生成 PR 摘要",
            "operation": "在“工作流”里生成 PR summary，或导出 report zip。",
            "result": "`pr_summary.md/json`，或一个包含 run artifacts 的 zip。",
            "meaning": "Reviewer 不用逐个打开 JSON，也能快速看到结论和风险。",
            "next_step": "把 summary 放进 PR，或把 zip 和本次 run 一起归档。",
            "command": "pcl export-report --run runs/quick --out runs/quick/report.zip",
        },
    ],
}

TEXT["zh"].update(
    {
        "title": "prompt_control_lab 本地仪表盘",
        "subtitle": "本地执行前检查、模型溯源和 agent 审计视图。不会上传 prompt、代码或 artifact。",
        "runs": "Runs 目录",
        "policy": "Guard 策略",
        "guard": "Prompt 守护",
        "workflows": "工作流",
        "tutorial": "教程",
        "tutorial_intro": "建议从上到下阅读。每个卡片都会说明：怎么操作、会得到什么文件、结果说明什么问题，以及下一步怎么做。",
        "tutorial_framework_note": "",
        "tutorial_operation": "操作",
        "tutorial_result": "得到什么",
        "tutorial_meaning": "说明什么问题",
        "tutorial_next_step": "下一步",
        "tutorial_command": "CLI 等价命令",
        "execution_mode": "执行模式",
        "overwrite": "覆盖已有 artifact",
        "allow_external_outputs": "允许写入 runs 目录之外",
        "write_boundary": "工作流默认应该写入当前 runs 目录下。外部输出路径会提示风险，并在自动执行模式下被阻止，除非显式允许。",
        "confirm_write": "确认写入",
        "run_action": "运行",
        "create_demo": "创建演示数据",
        "workflow_preview": "预览",
        "workflow_result": "工作流结果",
        "guard_workflow": "守护 Prompt",
        "analyze_workflow": "运行 analyze",
        "gate_workflow": "运行 gate",
        "audit_workflow": "运行 audit-diff",
        "agent_run_workflow": "生成 agent-run",
        "pr_summary_workflow": "生成 PR summary",
        "export_workflow": "导出报告 zip",
        "out_dir": "输出目录",
        "data_path": "任务 JSONL",
        "baseline_predictions": "Baseline 预测文件",
        "candidate_predictions": "Candidate 预测文件",
        "metric": "指标",
        "policy_path": "策略路径",
        "run_dir": "Run 目录",
        "repo": "仓库",
        "before": "Before ref",
        "after": "After ref",
        "tests_run": "已记录测试",
        "audit_dir": "Audit 目录",
        "agent": "Agent",
        "agent_run_path": "agent_run.json 路径",
        "markdown_path": "Markdown 路径",
        "json_path": "JSON 路径",
        "zip_path": "Zip 路径",
        "report": "运行报告",
        "drift": "模型漂移",
        "audit": "Agent 改动审计",
        "history": "历史",
        "prompt": "提示词",
        "run_guard": "运行守护",
        "selected_run": "选择 run",
        "missing_run": "没有找到 run 目录。",
        "empty_run": "这个 run 没有识别到 artifact。",
        "decision": "决策",
        "risk": "风险",
        "review": "需要人工复核",
        "categories": "风险类别",
        "violations": "策略违规",
        "token_cost": "估算 token 成本",
        "diff": "Prompt 差异",
        "recommendation": "部署建议",
        "gate": "门禁状态",
        "candidate_score": "候选分数",
        "comparison_validity": "比较有效性",
        "prompt_only": "Prompt-only",
        "mean_delta": "均值差异",
        "p_value": "p-value",
        "model_provenance": "模型来源",
        "drift_risk": "漂移风险",
        "audit_review": "需要人工复核",
        "dangerous_paths": "危险路径",
        "changed_files": "改动文件",
        "profile": "场景",
        "mode": "模式",
        "token_mode": "Token 模式",
        "max_tokens": "最大 Token",
        "guarded_prompt": "守护后的提示词",
        "save_guard": "保存 guard artifact",
        "save_guard_dir": "Guard 保存目录",
        "saved_guard": "已保存 guard artifact",
        "download_guard_json": "下载 guard_result.json",
        "download_improved_prompt": "下载 improved_prompt.txt",
        "risk_chart": "风险类别",
        "count": "数量",
        "category": "类别",
        "none": "无",
        "score_ci": "分数差异置信区间",
        "slice_scores": "任务切片分数",
        "baseline": "基线",
        "candidate": "候选",
        "model_timeline": "模型时间线",
        "no_model": "没有记录模型来源。",
        "no_audit": "没有找到 audit_result.json。",
        "public_api": "公共 API",
        "tests_passed": "测试通过",
        "file_breakdown": "改动文件类型",
        "file_kind": "类型",
        "source_files": "源码",
        "test_files": "测试",
        "docs_files": "文档",
        "config_files": "配置",
        "path": "路径",
        "no_history": "没有找到 history_index.json。",
        "run_timeline": "Run 时间线",
        "gate_trend": "门禁趋势",
        "score_trend": "分数趋势",
        "risk_trend": "风险趋势",
        "review_trend": "复核趋势",
        "prompt_identity": "Prompt 身份",
        "model_changes": "模型 / provider 变化",
        "audit_details": "审计明细",
        "secret_findings": "疑似密钥",
        "dependency_files": "依赖文件",
        "lockfiles": "锁文件",
        "workflow_files": "Workflow 文件",
        "deleted_test_files": "删除的测试文件",
        "unexpected_files": "意外文件",
        "test_results": "测试结果",
        "changed_lines": "改动行数",
        "file": "文件",
        "added": "新增",
        "deleted": "删除",
        "only_review_required": "只看需要复核的 run",
        "only_high_risk": "只看高风险 run",
        "provider_filter": "Provider 过滤",
        "model_filter": "模型过滤",
        "risk_categories": "风险类别",
    }
)

CHOICE_OPTIONS.update(
    {
        "execution_mode": [
            ("confirm", "confirm", "确认后执行"),
            ("auto", "auto", "自动执行"),
            ("command", "command", "只生成命令"),
        ],
        "profile": [
            ("coding", "coding", "编程"),
            ("general", "general", "通用"),
            ("research", "research", "研究"),
        ],
        "guard_mode": [
            ("suggest", "suggest", "给出建议"),
            ("auto", "auto", "自动改写"),
            ("gate", "gate", "门禁检查"),
        ],
        "token_mode": [
            ("balanced", "balanced", "平衡省 token"),
            ("aggressive", "aggressive", "激进省 token"),
        ],
        "tests_passed": [
            ("unknown", "unknown", "未知"),
            ("true", "true", "通过"),
            ("false", "false", "失败"),
        ],
        "external_tool": [
            ("auto", "auto", "自动识别"),
            ("promptfoo", "promptfoo", "Promptfoo"),
            ("langfuse", "langfuse", "Langfuse"),
            ("langsmith", "langsmith", "LangSmith"),
        ],
    }
)

TUTORIAL_SECTIONS["zh"] = [
    {
        "id": "guard",
        "image": "guard",
        "title": "1. 在 Agent 执行前守护 Prompt",
        "operation": "打开“Prompt 守护”，粘贴指令，选择场景和策略，然后运行守护。",
        "result": "`guard_result.json`、改写后的 prompt、风险等级、策略违规和 token 估算。",
        "meaning": "你可以判断 prompt 是否模糊、危险、范围太宽，或缺少目标文件和测试计划。",
        "next_step": "把改写后的 prompt 发给 Claude Code、Cursor、Codex，或继续手动调整。",
        "command": "pcl guard --prompt \"修复这个 bug\" --profile coding --policy examples/guard.policy.yaml --json",
    },
    {
        "id": "workflows",
        "image": "overview",
        "title": "2. 一键创建演示数据",
        "operation": "打开“工作流”，点击“创建演示数据”。",
        "result": "本地 demo 项目、`runs/demo`、报告、gate 结果和 `history_index.json`。",
        "meaning": "仪表盘会有真实 artifact 可读，每个 tab 都更容易理解。",
        "next_step": "切到“运行报告”或“历史”，检查刚生成的数据。",
        "command": "pcl init --path demo && cd demo && pcl analyze --config promptcontrol.example.yaml --out runs/quick",
    },
    {
        "id": "report",
        "image": "report",
        "title": "3. 评测、门禁和报告",
        "operation": "在工作流或 CLI 里运行 analyze，然后用策略运行 gate。",
        "result": "`metrics.json`、`stats.json`、`explanation.json`、`gate_result.json` 和报告文件。",
        "meaning": "你可以判断候选 prompt 是否可靠提升，并且是否通过团队门禁。",
        "next_step": "保留 prompt、继续改写，或检查失败切片和样本。",
        "command": "pcl analyze --config promptcontrol.example.yaml --out runs/quick && pcl gate --run runs/quick --policy examples/gate.policy.yaml",
    },
    {
        "id": "drift",
        "image": "report",
        "title": "4. 检查模型来源和漂移",
        "operation": "打开“模型漂移”，或在两个 run 目录之间运行 model-drift。",
        "result": "`model_drift.json`，包含 provider/model 对比和漂移风险。",
        "meaning": "如果模型变了，这次比较就不是干净的 prompt-only 比较。",
        "next_step": "固定模型 id，或在同一模型下重新跑 baseline/candidate。",
        "command": "pcl model-drift --run runs/current --history runs/previous --out runs/current/model_drift.json",
    },
    {
        "id": "audit",
        "image": "audit_history",
        "title": "5. 审计编程 Agent 改了什么",
        "operation": "Agent 完成后，对两个 git ref 运行 audit-diff。",
        "result": "`audit_result.json` 和 `audit_summary.md`，包含文件、行数、风险和测试记录。",
        "meaning": "你可以看到 agent 是否改了危险路径、依赖、workflow 或测试。",
        "next_step": "合并前复核高风险文件，然后生成 agent-run manifest。",
        "command": "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
    },
    {
        "id": "history",
        "image": "audit_history",
        "title": "6. 建立本地运行历史",
        "operation": "多次 analyze 或 audit 后，对 runs 目录建立索引。",
        "result": "`history_index.json`，包含模型、分数、gate、prompt 和风险时间线。",
        "meaning": "你可以发现分数回退、模型变化和高风险 agent run。",
        "next_step": "用“历史”过滤器只看高风险或需要复核的 run。",
        "command": "pcl history index --runs runs/ --out runs/history_index.json",
    },
    {
        "id": "project_defaults",
        "image": "overview",
        "title": "7. 使用项目默认配置",
        "operation": "在仓库根目录保留 `.promptcontrol.yaml`，记录策略、runs、路径和测试命令。",
        "result": "guard、gate、audit-diff 和 UI 可以读取本地默认值，命令更短。",
        "meaning": "团队可以共享同一套策略和预期路径，不用反复复制参数。",
        "next_step": "项目策略变化时，更新 `.promptcontrol.yaml`。",
        "command": "pcl guard --prompt \"修复这个 bug\" --profile coding",
    },
    {
        "id": "export_pr",
        "image": "audit_history",
        "title": "8. 导出并生成审查摘要",
        "operation": "从工作流生成 PR summary，或导出报告 zip。",
        "result": "`pr_summary.md/json`，或一个包含 run artifacts 的 zip。",
        "meaning": "Reviewer 不用逐个打开 JSON，也能快速看到结论和风险。",
        "next_step": "把 summary 放进 PR，或把 zip 和本次 run 一起归档。",
        "command": "pcl export-report --run runs/quick --out runs/quick/report.zip",
    },
]


def main() -> None:
    """Run the Streamlit dashboard."""

    st = _streamlit()
    st.set_page_config(page_title="prompt_control_lab", layout="wide")
    _hide_streamlit_chrome(st)
    st.markdown(dashboard_css(), unsafe_allow_html=True)
    query = _query_params(st)
    language = _sidebar_language(st, query)
    text = TEXT[language]
    runs_dir = Path(str(st.sidebar.text_input(text["runs"], os.environ.get("PCL_UI_RUNS", "runs"))))
    default_policy = os.environ.get("PCL_UI_POLICY", "")
    policy_raw = st.sidebar.text_input(text["policy"], default_policy)
    policy_path = Path(policy_raw) if policy_raw else None
    project_config = os.environ.get("PCL_UI_CONFIG", "")
    if project_config:
        st.sidebar.caption(f"Project config: {project_config}")
    execution_label = str(
        st.sidebar.selectbox(
            text["execution_mode"],
            _choice_labels("execution_mode", language),
            index=0,
        )
    )
    execution_mode = _choice_value("execution_mode", execution_label, language)
    overwrite = bool(st.sidebar.checkbox(text["overwrite"], value=False))
    allow_external_outputs = bool(st.sidebar.checkbox(text["allow_external_outputs"], value=False))
    st.markdown(
        (
            '<section class="pcl-hero">'
            f"<h1>{html.escape(text['title'])}</h1>"
            f"<p>{html.escape(text['subtitle'])}</p>"
            "</section>"
        ),
        unsafe_allow_html=True,
    )

    runs = list_runs(runs_dir)
    detail = _select_run(st, runs, text)
    default_view = str(query.get("view") or os.environ.get("PCL_UI_DEFAULT_VIEW", "research"))
    views = _ordered_views(default_view)
    tabs = st.tabs([text[name] for name in views])
    for tab, name in zip(tabs, views, strict=True):
        with tab:
            _render_view(
                st,
                name,
                text,
                language,
                policy_path,
                detail,
                query,
                runs_dir,
                execution_mode,
                overwrite,
                allow_external_outputs,
            )


def _render_view(
    st: Any,
    name: str,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    detail: JsonDict,
    query: JsonDict,
    runs_dir: Path,
    execution_mode: str,
    overwrite: bool,
    allow_external_outputs: bool,
) -> None:
    if name == "research":
        _render_research_overview_tab(st, text, detail)
    elif name == "workflows":
        _render_workflows_tab(
            st,
            text,
            language,
            policy_path,
            detail,
            runs_dir,
            execution_mode,
            overwrite,
            allow_external_outputs,
        )
    elif name == "tutorial":
        _render_tutorial_tab(st, text, language)
    elif name == "guard":
        _render_guard_tab(
            st,
            text,
            language,
            policy_path,
            runs_dir,
            _truthy(query.get("demo")),
            overwrite,
        )
    elif name == "report":
        _render_report_tab(st, text, detail)
    elif name == "drift":
        _render_model_drift_tab(st, text, detail)
    elif name == "audit":
        _render_audit_tab(st, text, detail)
    elif name == "history":
        _render_history_tab(st, text, detail)


def _hide_streamlit_chrome(st: Any) -> None:
    st.markdown(
        """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
</style>
""",
        unsafe_allow_html=True,
    )


def _sidebar_language(st: Any, query: JsonDict) -> str:
    default = str(query.get("lang") or os.environ.get("PCL_UI_LANGUAGE", "en"))
    selected = st.sidebar.selectbox(
        "Language / 语言",
        ["English", "中文"],
        index=0 if default == "en" else 1,
    )
    return "zh" if selected == "中文" else "en"


def _query_params(st: Any) -> JsonDict:
    try:
        raw = st.query_params
    except Exception:
        return {}
    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    if not isinstance(raw, dict):
        return {}
    return {str(key): _first_query_value(value) for key, value in raw.items()}


def _first_query_value(value: object) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value)


def _truthy(value: object) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


def _choice_labels(group: str, language: str) -> list[str]:
    """Return localized labels while keeping workflow values stable."""

    index = 2 if language == "zh" else 1
    return [str(item[index]) for item in CHOICE_OPTIONS[group]]


def _choice_value(group: str, label: str, language: str) -> str:
    """Map a localized UI label back to the stable internal enum value."""

    label_index = 2 if language == "zh" else 1
    for item in CHOICE_OPTIONS[group]:
        if label == item[label_index]:
            return str(item[0])
    return label


def tutorial_sections(language: str) -> list[JsonDict]:
    """Return tutorial cards for the selected language."""

    sections = TUTORIAL_SECTIONS.get(language) or TUTORIAL_SECTIONS["en"]
    steps = TUTORIAL_STEPS.get(language) or TUTORIAL_STEPS["en"]
    enriched: list[JsonDict] = []
    for section in sections:
        item: JsonDict = dict(section)
        section_id = str(item.get("id") or "")
        item["screenshot"] = TUTORIAL_SECTION_SCREENSHOTS.get(section_id, "workflows")
        item["steps"] = list(steps.get(section_id, []))
        enriched.append(item)
    return enriched


def tutorial_gallery_items(language: str) -> list[JsonDict]:
    """Return always-visible tutorial image cards for the selected language."""

    if language == "zh":
        return [
            {"title": "工作流：一键生成和导出", "image": "workflows"},
            {"title": "守护：执行前检查风险", "image": "guard"},
            {"title": "报告：用证据做决策", "image": "report"},
            {"title": "模型漂移：确认比较是否干净", "image": "model_drift"},
            {"title": "审计：看清 Agent 改动", "image": "audit"},
            {"title": "历史：追踪 run 趋势", "image": "history"},
        ]
    return [
        {"title": "Workflows: run and export locally", "image": "workflows"},
        {"title": "Guard: check risk first", "image": "guard"},
        {"title": "Report: decide with evidence", "image": "report"},
        {"title": "Model drift: validate comparisons", "image": "model_drift"},
        {"title": "Audit: inspect agent changes", "image": "audit"},
        {"title": "History: track run trends", "image": "history"},
    ]


def _tutorial_asset_path(image_key: str, language: str) -> Path:
    filenames = TUTORIAL_IMAGES.get(image_key) or TUTORIAL_IMAGES["overview"]
    filename = filenames[1] if language == "zh" else filenames[0]
    return Path(__file__).resolve().parents[3] / "docs" / "assets" / filename


def _tutorial_screenshot_path(image_key: str, language: str) -> Path:
    filenames = TUTORIAL_SCREENSHOTS.get(image_key) or TUTORIAL_SCREENSHOTS["workflows"]
    filename = filenames[1] if language == "zh" else filenames[0]
    return Path(__file__).resolve().parents[3] / "docs" / "assets" / filename


def _ordered_views(first: str) -> list[str]:
    views = ["research", "workflows", "tutorial", "guard", "report", "drift", "audit", "history"]
    if first not in views:
        return views
    return [first, *[view for view in views if view != first]]


def _select_run(st: Any, runs: list[JsonDict], text: dict[str, str]) -> JsonDict:
    if not runs:
        empty_state(
            st,
            text["missing_run"],
            "pcl init --path demo && "
            "pcl analyze --config promptcontrol.example.yaml --out runs/quick",
        )
        return {"has_artifacts": False, "empty_state": text["missing_run"], "name": ""}
    names = [str(item["name"]) for item in runs]
    selected = st.sidebar.selectbox(text["selected_run"], names)
    match = next(item for item in runs if item["name"] == selected)
    return load_run_detail(Path(str(match["path"])))


def _render_research_overview_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    st.markdown(f'<div class="pcl-section-title">{html.escape(text["research_title"])}</div>', unsafe_allow_html=True)
    st.caption(text["research_subtitle"])

    diagnostics = detail.get("diagnostics")
    has_diagnostics = isinstance(diagnostics, dict) and bool(diagnostics)
    if not detail.get("has_artifacts") and not has_diagnostics:
        empty_state(st, text["research_empty"], text["research_demo_command"])
        return

    rows = research_diagnostic_rows(detail)
    counts = research_status_counts(detail)
    available = counts.get("available", 0)
    artifacts = detail.get("artifacts")
    artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
    protocol_ready = "yes" if detail.get("splits") or detail.get("manifest") else "partial"
    stats_ready = "yes" if detail.get("first_comparison") or detail.get("stats") else "missing"
    evidence_card = detail.get("evidence_card")
    evidence_dict = evidence_card if isinstance(evidence_card, dict) else {}
    evidence_recommendation = evidence_dict.get("recommendation", "missing")
    claim_check = claim_check_summary(detail)
    claim_status = claim_check.get("status", "missing")
    claim_ladder = claim_evidence_ladder(detail)
    bridge = external_bridge_summary(detail)
    scorecard_rows = ecosystem_scorecard_rows(detail)
    ecosystem_rows = ecosystem_demo_rows(detail)
    gap_rows = evidence_gap_rows(detail)
    gap_action_rows = evidence_gap_action_rows(detail)
    gap_plan_rows = research_gap_plan_rows(detail)
    gap_script_rows = research_gap_script_rows(detail)
    gap_status_rows = research_gap_status_rows(detail)
    evidence_map = research_evidence_map(detail)

    st.markdown(
        '<div class="pcl-grid">'
        + stat_card_html(text["paper_protocol"], protocol_ready, text["tri_split"])
        + stat_card_html(
            text["diagnostic_coverage"],
            f"{available}/{len(rows)}",
            text["research_diagnostics"],
        )
        + stat_card_html(text["artifact_evidence"], artifact_count, "JSON / HTML / Markdown")
        + stat_card_html(text["paired_stats"], stats_ready, "bootstrap CI / p-value")
        + stat_card_html(
            text["evidence_recommendation"],
            evidence_recommendation,
            text["evidence_card"],
        )
        + stat_card_html(
            text["claim_check_status"],
            str(claim_status),
            str(claim_check.get("requested_claim") or text["claim_check"]),
        )
        + stat_card_html(
            text["ecosystem_bridge"],
            str(bridge.get("tool") or "none"),
            f"{bridge.get('pcl_added_count', 0)} {text['pcl_added_evidence']}",
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    map_html = research_evidence_map_html(evidence_map)
    if map_html:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_evidence_map"])}</div>'
            + map_html,
            unsafe_allow_html=True,
        )
    _render_research_pipeline(st, text)

    if scorecard_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["ecosystem_scorecard"])}</div>',
            unsafe_allow_html=True,
        )
        scorecard = detail.get("ecosystem_scorecard")
        scorecard_dict = scorecard if isinstance(scorecard, dict) else {}
        st.caption(str(scorecard_dict.get("positioning", "")))
        st.dataframe(scorecard_rows, use_container_width=True)

    if ecosystem_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["ecosystem_demo"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(ecosystem_rows, use_container_width=True)

    if gap_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["evidence_gap_diagnosis"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(gap_rows, use_container_width=True)
    if gap_action_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["evidence_gap_actions"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(gap_action_rows, use_container_width=True)
    if gap_plan_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_gap_plan"])}</div>',
            unsafe_allow_html=True,
        )
        plan = detail.get("research_gap_plan")
        plan_dict = plan if isinstance(plan, dict) else {}
        st.caption(str(plan_dict.get("boundary", "")))
        st.dataframe(gap_plan_rows, use_container_width=True)
    if gap_script_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_gap_scripts"])}</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(gap_script_rows, use_container_width=True)
    if gap_status_rows:
        st.markdown(
            f'<div class="pcl-section-title">{html.escape(text["research_gap_status"])}</div>',
            unsafe_allow_html=True,
        )
        status = detail.get("research_gap_status")
        status_dict = status if isinstance(status, dict) else {}
        st.caption(
            f"{status_dict.get('status', '')}: "
            f"{status_dict.get('complete_count', 0)}/{status_dict.get('action_count', 0)}"
        )
        st.dataframe(gap_status_rows, use_container_width=True)

    _render_external_bridge_section(st, text, bridge)

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["evidence_card"])}</div>',
        unsafe_allow_html=True,
    )
    if evidence_dict:
        st.write(f"**{text['evidence_summary']}:** {evidence_dict.get('summary', '')}")
        evidence_rows = evidence_card_rows(detail)
        if evidence_rows:
            st.dataframe(evidence_rows, use_container_width=True)
    else:
        empty_state(st, text["evidence_card_missing"], text["evidence_card_command"])

    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["claim_check"])}</div>',
        unsafe_allow_html=True,
    )
    if claim_check:
        ladder_html = evidence_ladder_html(claim_ladder)
        if ladder_html:
            st.markdown(
                f'<div class="pcl-section-title">{html.escape(text["claim_ladder"])}</div>'
                + ladder_html,
                unsafe_allow_html=True,
            )
        claim_rows = [
            {"field": text["claim_check_requested"], "value": claim_check.get("requested_claim", "")},
            {"field": text["claim_check_status"], "value": claim_check.get("status", "")},
            {"field": text["claim_check_tier"], "value": claim_check.get("evidence_tier", "")},
            {"field": text["claim_check_safe"], "value": claim_check.get("safe_claim", "")},
            {"field": text["claim_check_reason"], "value": claim_check.get("reason", "")},
            {
                "field": text["claim_check_next_missing"],
                "value": ", ".join(str(item) for item in claim_check.get("next_tier_missing", [])),
            },
        ]
        st.dataframe(claim_rows, use_container_width=True)
    else:
        empty_state(st, text["claim_check_missing"], text["claim_check_command"])

    st.markdown(f'<div class="pcl-section-title">{html.escape(text["research_diagnostics"])}</div>', unsafe_allow_html=True)
    st.plotly_chart(
        research_diagnostic_bar(rows, title=text["research_coverage"]),
        use_container_width=True,
    )
    st.dataframe(rows, use_container_width=True)

    st.markdown(
        '<div class="pcl-grid">'
        + paper_card_html(text["soft_hard"], "soft prompt -> hard token projection risk")
        + paper_card_html(text["hidden_state_input"], "HuggingFace/local hidden-state artifact source")
        + paper_card_html(text["trajectory_diag"], "hidden-state drift, decay, and turnpike-like signal")
        + paper_card_html(text["riccati_diag"], "finite-dimensional surrogate stability check")
        + paper_card_html(text["tv_soft_diag"], "static / time-varying / shuffled / random comparison")
        + "</div>",
        unsafe_allow_html=True,
    )
    st.info(text["research_boundary"])


def _render_research_pipeline(st: Any, text: dict[str, str]) -> None:
    steps = [
        (text["tri_split"], "train / validation / withheld"),
        (text["paired_stats"], "paired CI + permutation test"),
        (text["soft_hard"], "projection gap"),
        (text["hidden_state_input"], "HF/local states"),
        (text["trajectory_diag"], "state trajectory"),
        (text["riccati_diag"], "surrogate stability"),
        (text["tv_soft_diag"], "control lane"),
    ]
    html_steps = "".join(
        (
            '<div class="pcl-pipeline-step">'
            f"<strong>{html.escape(title)}</strong>"
            f"<span>{html.escape(caption)}</span>"
            "</div>"
        )
        for title, caption in steps
    )
    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["research_pipeline"])}</div>'
        f'<div class="pcl-pipeline">{html_steps}</div>',
        unsafe_allow_html=True,
    )


def _render_external_bridge_section(
    st: Any,
    text: dict[str, str],
    bridge: JsonDict,
) -> None:
    st.markdown(
        f'<div class="pcl-section-title">{html.escape(text["ecosystem_bridge"])}</div>',
        unsafe_allow_html=True,
    )
    if not bridge:
        empty_state(st, text["ecosystem_bridge_missing"], "pcl evidence-from --help")
        return
    rows = [
        {"field": text["external_tools"], "value": ", ".join(_strings(bridge.get("detected_tools")))},
        {"field": text["recommendation"], "value": bridge.get("recommendation", "")},
        {"field": text["comparison_validity"], "value": bridge.get("validity", "")},
        {"field": text["claim_check_status"], "value": bridge.get("claim_check_status", "")},
        {
            "field": text["claim_check_requested"],
            "value": bridge.get("claim_check_requested_claim", ""),
        },
        {
            "field": text["pcl_added_evidence"],
            "value": ", ".join(_strings(bridge.get("pcl_added_evidence"))),
        },
        {
            "field": text["missing_evidence"],
            "value": ", ".join(_strings(bridge.get("missing_evidence"))),
        },
        {
            "field": text["bridge_next_actions"],
            "value": " | ".join(_strings(bridge.get("next_actions"))),
        },
    ]
    st.dataframe(rows, use_container_width=True)


def _render_tutorial_tab(st: Any, text: dict[str, str], language: str) -> None:
    st.markdown(text["tutorial_intro"])
    overview = _tutorial_asset_path("overview", language)
    if overview.exists():
        _render_image(st, overview)
    _render_tutorial_gallery(st, language)

    for section in tutorial_sections(language):
        title = str(section.get("title", ""))
        expanded = section.get("id") in {"guard", "workflows"}
        with st.expander(title, expanded=expanded):
            screenshot_key = str(section.get("screenshot") or "workflows")
            image_path = _tutorial_screenshot_path(screenshot_key, language)
            if image_path.exists():
                _render_image(st, image_path)
            steps = section.get("steps") or []
            if isinstance(steps, list) and steps:
                st.markdown(f"**{text['tutorial_steps']}**")
                for index, step in enumerate(steps, start=1):
                    st.markdown(f"{index}. {step}")
            st.markdown(f"**{text['tutorial_operation']}**: {section.get('operation', '')}")
            st.markdown(f"**{text['tutorial_result']}**: {section.get('result', '')}")
            st.markdown(f"**{text['tutorial_meaning']}**: {section.get('meaning', '')}")
            st.markdown(f"**{text['tutorial_next_step']}**: {section.get('next_step', '')}")
            st.caption(text["tutorial_command"])
            st.code(str(section.get("command", "")), language="bash")


def _render_tutorial_gallery(st: Any, language: str) -> None:
    columns = st.columns(2)
    for index, item in enumerate(tutorial_gallery_items(language)):
        with columns[index % 2]:
            st.markdown(f"**{item['title']}**")
            path = _tutorial_screenshot_path(str(item["image"]), language)
            if path.exists():
                _render_image(st, path)


def _render_svg(st: Any, path: Path) -> None:
    _render_image(st, path)


def _render_image(st: Any, path: Path) -> None:
    mime_type = "image/png" if path.suffix.lower() == ".png" else "image/svg+xml"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    st.markdown(
        (
            f'<img src="data:{mime_type};base64,{encoded}" '
            'style="width: 100%; max-width: 1100px; border-radius: 8px;" '
            f'alt="{path.stem}">'
        ),
        unsafe_allow_html=True,
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


def _render_guard_tab(
    st: Any,
    text: dict[str, str],
    language: str,
    policy_path: Path | None,
    runs_dir: Path,
    run_demo: bool = False,
    overwrite: bool = False,
) -> None:
    prompt = st.text_area(
        text["prompt"],
        "Fix this bug in auth/session.py and run tests.",
        height=140,
    )
    columns = st.columns(4)
    profile_label = str(
        columns[0].selectbox(text["profile"], _choice_labels("profile", language))
    )
    mode_label = str(
        columns[1].selectbox(text["mode"], _choice_labels("guard_mode", language))
    )
    token_mode_label = str(
        columns[2].selectbox(text["token_mode"], _choice_labels("token_mode", language))
    )
    profile = _choice_value("profile", profile_label, language)
    mode = _choice_value("guard_mode", mode_label, language)
    token_mode = _choice_value("token_mode", token_mode_label, language)
    max_tokens_raw = columns[3].number_input(text["max_tokens"], min_value=0, value=0)
    max_tokens = int(max_tokens_raw) if max_tokens_raw else None
    save_guard = bool(st.checkbox(text["save_guard"], value=False))
    save_dir = Path(
        st.text_input(text["save_guard_dir"], str(runs_dir / "guard-ui"), disabled=not save_guard)
    )
    if st.button(text["run_guard"], type="primary") or run_demo:
        result = guard_prompt(
            prompt,
            context=load_prompt_context(None),
            mode=str(mode),
            profile=str(profile),
            token_mode=str(token_mode),
            max_tokens=max_tokens,
            language=language,
            policy_path=policy_path,
        ).to_json()
        metric_cards(
            st,
            [
                (text["decision"], result.get("action")),
                (text["risk"], result.get("risk_level")),
                (text["review"], result.get("required_review")),
            ],
        )
        st.markdown(badge(text["categories"], ", ".join(_strings(result.get("risk_categories")))))
        st.markdown(badge(text["violations"], len(_list(result.get("policy_violations")))))
        categories = _category_count(_strings(result.get("risk_categories")))
        st.plotly_chart(
            risk_category_bar(
                categories,
                title=text["risk_chart"],
                category_label=text["category"],
                count_label=text["count"],
                none_label=text["none"],
            ),
            use_container_width=True,
        )
        st.subheader(text["token_cost"])
        st.json(result.get("token_report", {}))
        st.subheader(text["diff"])
        st.code(prompt_diff(prompt, str(result.get("improved_prompt", ""))), language="diff")
        st.text_area(text["guarded_prompt"], str(result.get("improved_prompt", "")), height=180)
        downloads = guard_download_payloads(result)
        download_cols = st.columns(2)
        download_cols[0].download_button(
            text["download_guard_json"],
            downloads["guard_result.json"],
            file_name="guard_result.json",
            mime="application/json",
        )
        download_cols[1].download_button(
            text["download_improved_prompt"],
            downloads["improved_prompt.txt"],
            file_name="improved_prompt.txt",
            mime="text/plain",
        )
        if save_guard:
            outputs = [
                save_dir / "guard_result.json",
                save_dir / "improved_prompt.txt",
                save_dir / "guarded_prompt.txt",
            ]
            existing = [path for path in outputs if path.exists()]
            if existing and not overwrite:
                st.warning("Output artifacts already exist; enable overwrite to replace them.")
            else:
                written = save_guard_outputs(result, out_dir=save_dir)
                st.success(f"{text['saved_guard']}: {', '.join(str(path) for path in written)}")


def _render_report_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    if not detail.get("has_artifacts"):
        empty_state(st, text["empty_run"], str(detail.get("empty_state", "")))
        return
    explanation = _dict(detail.get("explanation"))
    gate = _dict(detail.get("gate"))
    validity = _dict(detail.get("comparison_validity"))
    comparison = _dict(detail.get("first_comparison")) or first_comparison(
        _dict(detail.get("stats"))
    )
    metric_cards(
        st,
        [
            (
                text["recommendation"],
                _recommendation_label(explanation.get("deployment_recommendation")),
            ),
            (text["gate"], gate.get("status", "-")),
            (text["candidate_score"], detail.get("candidate_score")),
            (text["comparison_validity"], validity.get("validity", "-")),
            (text["prompt_only"], validity.get("prompt_only_comparison", "-")),
        ],
    )
    metric_cards(
        st,
        [
            (text["mean_delta"], comparison.get("mean_delta")),
            (text["p_value"], comparison.get("permutation_p_value")),
        ],
    )
    if comparison:
        st.plotly_chart(
            score_delta_ci(comparison, title=text["score_ci"], mean_label=text["mean_delta"]),
            use_container_width=True,
        )
    if validity:
        issues = [
            *_list(validity.get("blocking_issues")),
            *_list(validity.get("review_items")),
        ]
        if issues:
            st.warning("\n".join(str(issue) for issue in issues))
    rows = slice_rows(detail)
    if rows:
        st.plotly_chart(
            slice_score_heatmap(
                rows,
                title=text["slice_scores"],
                baseline_label=text["baseline"],
                candidate_label=text["candidate"],
            ),
            use_container_width=True,
        )
        st.dataframe(rows, use_container_width=True)
    st.subheader(text["model_provenance"])
    rows = model_rows(detail)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info(text["no_model"])


def _render_model_drift_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    if not detail.get("has_artifacts"):
        empty_state(st, text["empty_run"], str(detail.get("empty_state", "")))
        return
    drift = _dict(detail.get("model_drift"))
    rows = model_rows(detail)
    metric_cards(st, [(text["drift_risk"], drift.get("risk", "unknown"))])
    if drift:
        st.json(drift)
    else:
        st.code(
            "pcl model-drift --run runs/current --history runs/previous "
            "--out runs/current/model_drift.json",
            language="bash",
        )
    if rows:
        st.dataframe(rows, use_container_width=True)
    history = _dict(detail.get("history_index"))
    runs = history.get("runs")
    if isinstance(runs, list) and runs:
        st.subheader(text["model_timeline"])
        st.dataframe(_history_model_rows(runs), use_container_width=True)


def _render_audit_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    audit = _dict(detail.get("audit"))
    if not audit:
        empty_state(
            st,
            text["no_audit"],
            "pcl audit-diff --before HEAD~1 --after HEAD --out runs/audit",
        )
        return
    metric_cards(
        st,
        [
            (text["changed_files"], audit.get("touched_files")),
            (text["audit_review"], audit.get("human_review_required")),
            (text["public_api"], audit.get("public_api_changed")),
            (text["tests_passed"], audit.get("tests_passed")),
        ],
    )
    st.plotly_chart(
        file_breakdown_bar(
            audit,
            title=text["file_breakdown"],
            kind_label=text["file_kind"],
            count_label=text["count"],
            source_label=text["source_files"],
            tests_label=text["test_files"],
            docs_label=text["docs_files"],
            config_label=text["config_files"],
        ),
        use_container_width=True,
    )
    changed_line_table = changed_line_rows(audit)
    if changed_line_table:
        st.subheader(text["changed_lines"])
        st.dataframe(changed_line_table, use_container_width=True)
    dangerous = _strings(audit.get("dangerous_paths"))
    if dangerous:
        st.error(text["dangerous_paths"])
        st.dataframe([{text["path"]: path} for path in dangerous], use_container_width=True)
    changed = _strings(audit.get("changed_files"))
    if changed:
        st.dataframe([{text["path"]: path} for path in changed], use_container_width=True)
    sections = audit_detail_sections(audit)
    detail_labels = {
        "secret_findings": text["secret_findings"],
        "dependency_files_changed": text["dependency_files"],
        "lockfiles_changed": text["lockfiles"],
        "workflow_files_changed": text["workflow_files"],
        "deleted_test_files": text["deleted_test_files"],
        "unexpected_files": text["unexpected_files"],
        "test_results": text["test_results"],
    }
    if any(sections.values()):
        st.subheader(text["audit_details"])
    for key, label in detail_labels.items():
        rows = sections.get(key, [])
        if rows:
            st.markdown(f"**{label}**")
            st.dataframe(rows, use_container_width=True)


def _render_history_tab(st: Any, text: dict[str, str], detail: JsonDict) -> None:
    history = _dict(detail.get("history_index"))
    runs = history.get("runs")
    if not isinstance(runs, list) or not runs:
        empty_state(
            st,
            text["no_history"],
            "pcl history index --runs runs/ --out runs/history_index.json",
        )
        return
    rows = history_rows(detail)
    filters = st.columns(4)
    only_review_required = bool(filters[0].checkbox(text["only_review_required"], value=False))
    only_high_risk = bool(filters[1].checkbox(text["only_high_risk"], value=False))
    provider_filter = str(filters[2].text_input(text["provider_filter"], ""))
    model_filter = str(filters[3].text_input(text["model_filter"], ""))
    rows = filter_history_rows(
        rows,
        only_review_required=only_review_required,
        only_high_risk=only_high_risk,
        provider=provider_filter,
        model=model_filter,
    )
    st.subheader(text["run_timeline"])
    st.dataframe(rows, use_container_width=True)
    st.plotly_chart(
        history_numeric_trend(
            rows,
            y_key="mean_score",
            title=text["score_trend"],
            value_label=text["candidate_score"],
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        history_category_timeline(
            rows,
            y_key="gate_status",
            title=text["gate_trend"],
            category_label=text["gate"],
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        history_category_timeline(
            rows,
            y_key="risk_level",
            title=text["risk_trend"],
            category_label=text["risk"],
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        history_category_timeline(
            rows,
            y_key="review_required",
            title=text["review_trend"],
            category_label=text["review"],
        ),
        use_container_width=True,
    )
    st.subheader(text["model_changes"])
    st.dataframe(
        [
            {
                "run": row.get("run"),
                "provider": row.get("provider"),
                "model": row.get("model"),
                "prompt_hash": row.get("prompt_hash"),
            }
            for row in rows
        ],
        use_container_width=True,
    )
    gate_counts = _category_count([str(row.get("gate_status", "unknown")) for row in rows])
    st.plotly_chart(
        risk_category_bar(
            gate_counts,
            title=text["gate_trend"],
            category_label=text["gate"],
            count_label=text["count"],
            none_label=text["none"],
        ),
        use_container_width=True,
    )
    risk_counts: dict[str, int] = {}
    for row in rows:
        for category in _strings(row.get("risk_categories")):
            risk_counts[category] = risk_counts.get(category, 0) + 1
    st.plotly_chart(
        risk_category_bar(
            risk_counts,
            title=text["risk_categories"],
            category_label=text["category"],
            count_label=text["count"],
            none_label=text["none"],
        ),
        use_container_width=True,
    )


def _history_row(item: JsonDict) -> JsonDict:
    model = _dict(item.get("model"))
    prompt = _dict(item.get("prompt_identity"))
    return {
        "run": item.get("run_name"),
        "gate_status": item.get("gate_status"),
        "mean_score": item.get("mean_score"),
        "provider": model.get("provider"),
        "model": model.get("model_id"),
        "prompt_hash": prompt.get("prompt_hash"),
        "risk_categories": item.get("risk_categories", []),
    }


def _history_model_rows(runs: list[object]) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        rows.append(_history_row(item))
    return rows


def _streamlit() -> Any:
    return cast(Any, importlib.import_module("streamlit"))


def _dict(value: object) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [str(item) for item in _list(value)]


def _category_count(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _recommendation_label(value: object) -> object:
    if isinstance(value, dict):
        return value.get("label") or value.get("recommendation") or value.get("verdict")
    return value


def _confirm_checkbox(
    st: Any,
    text: dict[str, str],
    execution_mode: str,
    key: str,
) -> bool:
    if execution_mode != "confirm":
        return False
    return bool(st.checkbox(text["confirm_write"], value=False, key=key))


def _render_workflow_result(
    st: Any,
    text: dict[str, str],
    callback: Callable[[], JsonDict],
) -> None:
    try:
        result = callback()
    except Exception as exc:
        st.error(str(exc))
        return
    title = (
        text["workflow_preview"]
        if result.get("status") == "preview"
        else text["workflow_result"]
    )
    st.subheader(title)
    warnings = result.get("path_warnings")
    if isinstance(warnings, list) and warnings:
        for warning in warnings:
            st.warning(str(warning))
    st.json(result)


def _optional_path(value: str) -> Path | None:
    stripped = value.strip()
    return Path(stripped) if stripped else None


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _optional_bool_label(value: object) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


if __name__ == "__main__":
    main()
