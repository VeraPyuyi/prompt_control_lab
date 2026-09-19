import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { decisionLabel } from "../i18n";
import type {
  CheckpointAggregate,
  CheckpointVisualization,
  Language,
} from "../types";
import { Badge, Card } from "../components/ui";

const SEED_COLORS = ["#2563eb", "#0f766e", "#c26a18", "#7c3aed", "#be123c"];

const TEXT = {
  en: {
    score: "Checkpoint score by seed",
    scoreHelp: "Each seed remains visible; the heavier line is the stage mean.",
    generation_mismatch: "Generation mismatch",
    selective_aurc: "Selective risk AURC",
    trajectory_drift: "Representation trajectory drift",
    lowerBetter: "Lower is better",
    contextDependent: "Interpret with the recorded threshold",
    notRecorded: "Not recorded",
    gate: "Gate decision and triggers",
    check: "Check",
    observed: "Observed",
    threshold: "Threshold",
    impact: "Impact",
    noTriggers: "No triggered gate checks were recorded.",
    changed: "What changed",
    observedLabel: "What was observed",
    meaning: "What it means",
    boundary: "What it cannot prove",
    next: "Next action",
    stageMean: "Stage mean",
  },
  zh: {
    score: "各 Seed 的 Checkpoint 任务分数",
    scoreHelp: "保留每个 Seed 的原始轨迹，粗线表示各阶段平均值。",
    generation_mismatch: "生成阶段错配",
    selective_aurc: "选择性风险 AURC",
    trajectory_drift: "表示轨迹漂移",
    lowerBetter: "越低越好",
    contextDependent: "需要结合已记录阈值解释",
    notRecorded: "未记录",
    gate: "门禁决策与触发原因",
    check: "检查项",
    observed: "观测值",
    threshold: "阈值",
    impact: "影响",
    noTriggers: "没有记录触发的门禁检查。",
    changed: "改了什么",
    observedLabel: "观察到了什么",
    meaning: "可以解释什么",
    boundary: "不能证明什么",
    next: "下一步行动",
    stageMean: "阶段均值",
  },
} as const;

function numberLabel(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(4) : "—";
}

function stageLabel(stage: string, language: Language): string {
  if (language === "zh") {
    return { initial: "初始", mid: "中间", final: "最终" }[stage] ?? stage;
  }
  return stage.charAt(0).toUpperCase() + stage.slice(1);
}

function diagnosticValues(
  aggregates: CheckpointAggregate[],
  field: "generation_mismatch" | "selective_aurc" | "trajectory_drift",
  language: Language,
) {
  return aggregates.flatMap((row) => {
    const value = row[field];
    return typeof value === "number" && Number.isFinite(value)
      ? [{ stage: stageLabel(row.stage, language), value }]
      : [];
  });
}

function DiagnosticChart({
  field,
  visualization,
  language,
}: {
  field: "generation_mismatch" | "selective_aurc" | "trajectory_drift";
  visualization: CheckpointVisualization;
  language: Language;
}) {
  const labels = TEXT[language];
  const values = diagnosticValues(visualization.aggregates, field, language);
  const direction = visualization.diagnostics?.[field]?.direction;
  return (
    <Card className="checkpoint-diagnostic-card">
      <h2>{labels[field]}</h2>
      <p className="checkpoint-chart-note">
        {direction === "lower_is_better" ? labels.lowerBetter : labels.contextDependent}
      </p>
      {values.length ? (
        <div className="checkpoint-mini-chart" aria-label={labels[field]}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={values} margin={{ top: 12, right: 14, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#edf0f3" vertical={false} />
              <XAxis dataKey="stage" tick={{ fontSize: 11 }} />
              <YAxis width={48} domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => numberLabel(value)} />
              <Line
                dataKey="value"
                type="monotone"
                stroke="#0f766e"
                strokeWidth={3}
                dot={{ r: 4 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : <p className="muted">{labels.notRecorded}</p>}
    </Card>
  );
}

export function CheckpointReview({
  visualization,
  language,
}: {
  visualization: CheckpointVisualization;
  language: Language;
}) {
  const labels = TEXT[language];
  const scoreRows = visualization.stage_order.map((stage) => {
    const row: Record<string, string | number> = { stage: stageLabel(stage, language) };
    for (const point of visualization.points.filter((item) => item.stage === stage)) {
      row[`seed_${point.seed}`] = point.mean_score;
    }
    const aggregate = visualization.aggregates.find((item) => item.stage === stage);
    if (aggregate) row.stage_mean = aggregate.mean_score;
    return row;
  });
  const narrative = visualization.narrative?.[language] ?? visualization.narrative?.en ?? {};
  const checks = visualization.triggered_checks ?? [];

  return (
    <section className="checkpoint-evidence" aria-label={labels.score}>
      <Card className="checkpoint-score-card">
        <div className="checkpoint-section-heading">
          <div>
            <h2>{labels.score}</h2>
            <p>{labels.scoreHelp}</p>
          </div>
          <Badge tone={visualization.decision === "hold" ? "danger" : "warn"}>
            {decisionLabel(visualization.decision, language)}
          </Badge>
        </div>
        <div className="checkpoint-score-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={scoreRows} margin={{ top: 12, right: 20, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#edf0f3" vertical={false} />
              <XAxis dataKey="stage" tick={{ fontSize: 12 }} />
              <YAxis width={54} domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => numberLabel(value)} />
              <Legend />
              {visualization.seeds.map((seed, index) => (
                <Line
                  key={seed}
                  dataKey={`seed_${seed}`}
                  name={`Seed ${seed}`}
                  type="linear"
                  connectNulls={false}
                  stroke={SEED_COLORS[index % SEED_COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  isAnimationActive={false}
                />
              ))}
              <Line
                dataKey="stage_mean"
                name={labels.stageMean}
                type="linear"
                stroke="#172033"
                strokeWidth={4}
                dot={{ r: 5 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="checkpoint-diagnostic-grid">
        <DiagnosticChart field="generation_mismatch" visualization={visualization} language={language} />
        <DiagnosticChart field="selective_aurc" visualization={visualization} language={language} />
        <DiagnosticChart field="trajectory_drift" visualization={visualization} language={language} />
      </div>

      <Card className="checkpoint-gate-card">
        <div className="checkpoint-section-heading">
          <h2>{labels.gate}</h2>
          <Badge tone={visualization.decision === "hold" ? "danger" : "warn"}>
            {decisionLabel(visualization.decision, language)}
          </Badge>
        </div>
        {checks.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>{labels.check}</th><th>{labels.observed}</th><th>{labels.threshold}</th><th>{labels.impact}</th></tr>
              </thead>
              <tbody>
                {checks.map((check, index) => (
                  <tr key={`${check.check ?? "check"}-${index}`}>
                    <td>{(check.check ?? "unknown").replaceAll("_", " ")}</td>
                    <td>{numberLabel(check.observed ?? check.observed_mean)}</td>
                    <td>{numberLabel(check.threshold)}</td>
                    <td>{decisionLabel(check.impact ?? check.status, language)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="muted">{labels.noTriggers}</p>}
      </Card>

      <div className="checkpoint-narrative">
        {[
          [labels.changed, narrative.changed],
          [labels.observedLabel, narrative.observed],
          [labels.meaning, narrative.meaning],
          [labels.boundary, narrative.boundary ?? visualization.claim_boundary],
          [labels.next, narrative.next_action],
        ].map(([title, body]) => (
          <div key={title}>
            <strong>{title}</strong>
            <p>{body || labels.notRecorded}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
