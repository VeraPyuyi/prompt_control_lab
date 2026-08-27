import type { DiagnosticEntry, Language, ViewId } from "./types";

export const navItems: Array<{ id: ViewId; en: string; zh: string }> = [
  { id: "change-review", en: "Change Review", zh: "变更审查" },
  { id: "before", en: "Before", zh: "执行前" },
  { id: "run", en: "Run", zh: "运行" },
  { id: "why", en: "Why", zh: "原因" },
  { id: "after", en: "After", zh: "执行后" },
  { id: "decision", en: "Decision", zh: "决策" },
  { id: "history", en: "History", zh: "历史" },
  { id: "stability", en: "Stability & Confidence", zh: "稳定性与可信度" },
];

export const copy = {
  en: {
    appName: "PromptControlLab",
    local: "Local cockpit",
    navigation: "Workflow",
    pageEyebrow: "CHANGE CONTROL",
    changeReview: "Change review",
    changeReviewLead: "A decision-ready view of what changed, why it matters, and what to do next.",
    conclusion: "Conclusion",
    changeType: "Change type",
    risk: "Risk",
    likelyCauses: "Likely causes",
    evidenceCoverage: "Evidence coverage",
    nextAction: "Next action",
    observed: "Observed",
    beforeTitle: "Before the run",
    beforeLead: "Check the intended change and evidence plan before execution.",
    runTitle: "Run inventory",
    runLead: "Compare recorded runs without opening raw artifacts.",
    whyTitle: "Why the result changed",
    whyLead: "Ranked explanations grounded in the available evidence.",
    afterTitle: "What happened after the change",
    afterLead: "Outcome and operational signals observed in the candidate run.",
    decisionTitle: "Release decision",
    decisionLead: "The current recommendation does not override missing evidence or policy failures.",
    historyTitle: "Run history",
    historyLead: "Score, risk, and review status across recorded runs.",
    stabilityTitle: "Stability & confidence",
    stabilityLead: "Plain-language diagnostics for long-horizon influence, local stability, and local solution confidence.",
    technicalName: "Technical name",
    whatItDoes: "What this checks",
    currentEvidence: "Current evidence",
    whatItMeans: "What the result means",
    cannotProve: "What it cannot prove",
    noData: "No data recorded yet",
    noDataHelp: "Generate or import a run to populate this view.",
    loadError: "Could not load this view",
    loadErrorHelp: "The local API did not return the expected data.",
    retry: "Try again",
    loading: "Loading local evidence",
    covered: "Covered",
    missing: "Missing",
    needsReview: "Needs review",
    pass: "Pass",
    hold: "Hold",
    insufficientEvidence: "Insufficient evidence",
    unknown: "Unknown",
    run: "Run",
    score: "Score",
    gate: "Gate",
    model: "Model",
    provider: "Provider",
    review: "Review",
    noCause: "No cause was recorded. Compare the run provenance before acting.",
    noObservation: "No outcome observation was recorded.",
    releaseBoundary: "Treat this as a local evidence review, not a proof of causal safety.",
    featuredCases: "Featured reviews",
    featuredCasesLead: "Open a real case to see the same evidence workflow applied to an Agent, model, or checkpoint change.",
    caseChanged: "Change",
    caseEvidence: "Evidence",
    caseBoundary: "Cannot prove",
    selectedCase: "Selected",
  },
  zh: {
    appName: "PromptControlLab",
    local: "本地工作台",
    navigation: "工作流程",
    pageEyebrow: "变更控制",
    changeReview: "变更审查",
    changeReviewLead: "用一页看清改了什么、为什么重要，以及下一步应该做什么。",
    conclusion: "当前结论",
    changeType: "变更类型",
    risk: "风险等级",
    likelyCauses: "最可能的原因",
    evidenceCoverage: "证据覆盖",
    nextAction: "建议下一步",
    observed: "观察结果",
    beforeTitle: "运行前检查",
    beforeLead: "在执行前确认变更目标、范围与证据计划。",
    runTitle: "运行记录",
    runLead: "无需打开原始文件，即可比较已经记录的运行。",
    whyTitle: "为什么结果发生变化",
    whyLead: "根据现有证据整理最可能的解释。",
    afterTitle: "变更后发生了什么",
    afterLead: "查看候选运行中的结果与工程信号。",
    decisionTitle: "发布决策",
    decisionLead: "当前建议不会掩盖证据缺失或策略检查失败。",
    historyTitle: "运行历史",
    historyLead: "查看多次运行中的分数、风险和人工复核状态。",
    stabilityTitle: "稳定性与可信度",
    stabilityLead: "用通俗语言解释长任务影响、局部稳定性和局部解可信范围。",
    technicalName: "技术名称",
    whatItDoes: "这个功能做什么",
    currentEvidence: "当前证据",
    whatItMeans: "结果意味着什么",
    cannotProve: "不能证明什么",
    noData: "暂时没有数据",
    noDataHelp: "生成或导入一次运行后，这里会显示结果。",
    loadError: "无法加载当前页面",
    loadErrorHelp: "本地接口没有返回预期数据。",
    retry: "重试",
    loading: "正在读取本地证据",
    covered: "已覆盖",
    missing: "缺失",
    needsReview: "需要复核",
    pass: "可以继续",
    hold: "暂缓",
    insufficientEvidence: "证据不足",
    unknown: "未知",
    run: "运行",
    score: "分数",
    gate: "门禁",
    model: "模型",
    provider: "服务商",
    review: "人工复核",
    noCause: "尚未记录明确原因，行动前请先比较运行来源信息。",
    noObservation: "尚未记录结果观察。",
    releaseBoundary: "这是本地证据审查，不是对因果关系或安全性的证明。",
    featuredCases: "旗舰案例",
    featuredCasesLead: "选择真实案例，查看同一套证据流程如何审查 Agent、模型或 Checkpoint 变更。",
    caseChanged: "变更内容",
    caseEvidence: "证据可靠性",
    caseBoundary: "不能证明",
    selectedCase: "当前案例",
  },
} as const;

const diagnosticCopy: Record<string, Record<Language, DiagnosticEntry>> = {
  terminal_sensitivity: {
    en: {
      label: "Long-horizon goal influence",
      technical_name: "Terminal sensitivity",
      purpose: "Checks whether changing the final reward or objective has less influence on earlier decisions as the task grows longer.",
    },
    zh: {
      label: "最终目标影响",
      technical_name: "终端敏感性（Terminal sensitivity）",
      purpose: "检查最终奖励或目标改变后，对前面决策的影响是否会随着任务变长而减弱。",
    },
  },
  green_certificate: {
    en: {
      label: "Local stability boundary",
      technical_name: "Green certificate",
      purpose: "Checks whether stable directions are clearly separated and boundary constraints remain robust in the current low-dimensional approximation.",
    },
    zh: {
      label: "局部稳定边界",
      technical_name: "Green 证书（Green certificate）",
      purpose: "检查当前低维近似中的稳定方向是否清楚分离，边界约束是否足够稳健。",
    },
  },
  posterior_certificate: {
    en: {
      label: "Local solution confidence range",
      technical_name: "Posterior certificate",
      purpose: "Uses residual and local variation bounds to check whether a verifiable solution exists nearby and estimates the trustworthy local range.",
    },
    zh: {
      label: "局部解可信范围",
      technical_name: "后验证书（Posterior certificate）",
      purpose: "根据残差和局部变化上界，检查当前结果附近是否存在可验证的解，并估计可信范围。",
    },
  },
};

export function localizeDiagnostic(
  id: string,
  entry: DiagnosticEntry,
  language: Language,
): DiagnosticEntry {
  const local = diagnosticCopy[id]?.[language];
  return { ...entry, ...local, id };
}

export function decisionLabel(value: string | undefined, language: Language): string {
  const normalized = value?.toLowerCase();
  const labels = copy[language];
  if (normalized === "pass" || normalized === "passed") return labels.pass;
  if (normalized === "hold" || normalized === "fail" || normalized === "failed") return labels.hold;
  if (normalized === "needs_review" || normalized === "review") return labels.needsReview;
  if (normalized === "insufficient_evidence") return labels.insufficientEvidence;
  return labels.unknown;
}

export function riskLabel(value: string | undefined, language: Language): string {
  const normalized = value?.toLowerCase();
  if (language === "zh") {
    if (normalized === "high") return "高风险";
    if (normalized === "medium") return "中风险";
    if (normalized === "low") return "低风险";
  }
  return normalized ? humanizeForDisplay(normalized) : copy[language].unknown;
}

export function changeKindLabel(value: string | undefined, language: Language): string {
  if (language === "zh") {
    const labels: Record<string, string> = {
      agent_change: "Agent 变更",
      prompt_change: "Prompt 变更",
      model_change: "模型变更",
      checkpoint_change: "Checkpoint 变更",
    };
    if (value && labels[value]) return labels[value];
  }
  return value ? humanizeForDisplay(value) : copy[language].unknown;
}

export function evidenceName(value: string, language: Language): string {
  if (language === "zh") {
    const labels: Record<string, string> = {
      prompt: "Prompt",
      model: "模型",
      audit: "改动审计",
      tests: "测试",
      provenance: "来源记录",
      stability: "稳定性",
      metrics: "评测指标",
      baseline_events: "Baseline 运行事件",
      baseline_gate: "Baseline 门禁",
      baseline_manifest: "Baseline 来源记录",
      baseline_metrics: "Baseline 评测指标",
      candidate_events: "Candidate 运行事件",
      candidate_gate: "Candidate 门禁",
      candidate_manifest: "Candidate 来源记录",
      candidate_metrics: "Candidate 评测指标",
    };
    if (labels[value]) return labels[value];
  }
  return humanizeForDisplay(value);
}

export function evidenceLevelLabel(value: string | undefined, language: Language): string {
  const labels: Record<Language, Record<string, string>> = {
    en: {
      real_repeated_runs: "Real repeated runs",
      historical_aggregate: "Real historical aggregates",
      real_three_seed_pilot: "Real three-seed pilot",
    },
    zh: {
      real_repeated_runs: "真实重复运行",
      historical_aggregate: "真实历史聚合",
      real_three_seed_pilot: "真实三 Seed 试点",
    },
  };
  return value ? labels[language][value] ?? humanizeForDisplay(value) : copy[language].unknown;
}

const diagnosticStatuses: Record<Language, Record<string, string>> = {
  en: {
    certificate_verified: "Conditions verified",
    surrogate_consistent: "Low-dimensional result consistent",
    empirical_only: "Experimental trend only",
    not_applicable: "Not applicable",
    insufficient_evidence: "Insufficient evidence",
    conditions_not_met: "Conditions not met; this does not prove non-existence",
  },
  zh: {
    certificate_verified: "限定条件已核验",
    surrogate_consistent: "低维近似结果一致",
    empirical_only: "仅观察到实验趋势",
    not_applicable: "当前场景不适用",
    insufficient_evidence: "现有证据不足",
    conditions_not_met: "条件未满足，不代表解不存在",
  },
};

const diagnosticMetrics: Record<Language, Record<string, string>> = {
  en: {
    decay_rate: "Influence decay rate",
    r_squared: "Trend fit",
    hyperbolicity_margin: "Stable-direction separation margin",
    boundary_sigma_min: "Boundary robustness margin",
    h: "Local condition indicator",
    existence_radius: "Confidence neighborhood radius",
  },
  zh: {
    decay_rate: "影响衰减速度",
    r_squared: "趋势拟合度",
    hyperbolicity_margin: "稳定方向分离余量",
    boundary_sigma_min: "边界稳健余量",
    h: "局部条件指标",
    existence_radius: "可信邻域半径",
  },
};

export function diagnosticStatusLabel(value: string | undefined, language: Language): string {
  if (!value) return copy[language].unknown;
  return diagnosticStatuses[language][value] ?? humanizeForDisplay(value);
}

export function diagnosticMetricLabel(value: string, language: Language): string {
  return diagnosticMetrics[language][value] ?? humanizeForDisplay(value);
}

function humanizeForDisplay(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
