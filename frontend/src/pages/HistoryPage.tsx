import { useMemo, useState } from "react";
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

import { copy, decisionLabel, riskLabel } from "../i18n";
import { formatNumber } from "../lib/utils";
import type { Language, RunSummary } from "../types";
import { EmptyPanel } from "../components/StatePanel";
import { PageHeader } from "../components/PageHeader";
import { Badge, Card } from "../components/ui";

const ALL = "__all__";

function uniqueValues(runs: RunSummary[], key: "provider" | "model" | "prompt_hash"): string[] {
  return [...new Set(runs.map((run) => run[key]).filter((value): value is string => Boolean(value)))].sort();
}

export function HistoryPage({ runs, language }: { runs: RunSummary[]; language: Language }) {
  const labels = copy[language];
  const [reviewOnly, setReviewOnly] = useState(false);
  const [highRiskOnly, setHighRiskOnly] = useState(false);
  const [provider, setProvider] = useState(ALL);
  const [model, setModel] = useState(ALL);
  const [promptHash, setPromptHash] = useState(ALL);
  const providers = useMemo(() => uniqueValues(runs, "provider"), [runs]);
  const models = useMemo(() => uniqueValues(runs, "model"), [runs]);
  const promptHashes = useMemo(() => uniqueValues(runs, "prompt_hash"), [runs]);
  const filtered = useMemo(() => runs.filter((run) => {
    const review = run.review_required ?? run.human_review_required ?? false;
    return (!reviewOnly || review)
      && (!highRiskOnly || run.risk_level === "high")
      && (provider === ALL || run.provider === provider)
      && (model === ALL || run.model === model)
      && (promptHash === ALL || run.prompt_hash === promptHash);
  }), [highRiskOnly, model, promptHash, provider, reviewOnly, runs]);
  const chartData = filtered.map((run, index) => ({
    name: run.id ?? run.name ?? `Run ${index + 1}`,
    score: run.score ?? run.mean_score ?? null,
  }));

  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.historyTitle} lead={labels.historyLead} />
      {!runs.length ? <EmptyPanel language={language} /> : (
        <>
          <Card className="history-filters" aria-label={language === "zh" ? "历史筛选" : "History filters"}>
            <label className="check-filter"><input type="checkbox" checked={reviewOnly} onChange={(event) => setReviewOnly(event.target.checked)} />{language === "zh" ? "只看需要复核" : "Review required only"}</label>
            <label className="check-filter"><input type="checkbox" checked={highRiskOnly} onChange={(event) => setHighRiskOnly(event.target.checked)} />{language === "zh" ? "只看高风险" : "High risk only"}</label>
            <FilterSelect label={labels.provider} value={provider} values={providers} language={language} onChange={setProvider} />
            <FilterSelect label={labels.model} value={model} values={models} language={language} onChange={setModel} />
            <FilterSelect label="Prompt hash" value={promptHash} values={promptHashes} language={language} onChange={setPromptHash} />
          </Card>
          {!filtered.length ? <EmptyPanel language={language} /> : (
            <>
              <div className="history-chart-grid">
                <Card className="chart-card">
                  <h2>{language === "zh" ? "分数趋势" : "Score trend"}</h2>
                  <HistoryChart data={chartData} lines={[{ key: "score", label: labels.score, color: "#2563eb" }]} />
                </Card>
                <Card className="chart-card">
                  <h2>{language === "zh" ? "决策、风险与复核趋势" : "Decision, risk, and review trend"}</h2>
                  <StatusTimeline runs={filtered} language={language} />
                </Card>
              </div>
              <Card className="table-card history-table">
                <div className="table-scroll"><table>
                  <thead><tr><th>{labels.run}</th><th>{labels.score}</th><th>{labels.gate}</th><th>{labels.risk}</th><th>{labels.review}</th><th>{labels.provider}</th><th>{labels.model}</th><th>Prompt hash</th></tr></thead>
                  <tbody>{filtered.map((run, index) => {
                    const id = run.id ?? run.name ?? run.path ?? String(index);
                    const review = run.review_required ?? run.human_review_required ?? false;
                    return <tr key={id}><td>{id}</td><td>{formatNumber(run.score ?? run.mean_score)}</td><td>{decisionLabel(run.change_decision ?? run.gate_status ?? run.decision, language)}</td><td><Badge tone={run.risk_level === "high" ? "danger" : run.risk_level === "medium" ? "warn" : "neutral"}>{riskLabel(run.risk_level, language)}</Badge></td><td>{review ? labels.needsReview : "—"}</td><td>{run.provider ?? "—"}</td><td>{run.model ?? "—"}</td><td className="hash-cell" title={run.prompt_hash}>{run.prompt_hash ? `${run.prompt_hash.slice(0, 12)}…` : "—"}</td></tr>;
                  })}</tbody>
                </table></div>
              </Card>
            </>
          )}
        </>
      )}
    </>
  );
}

function FilterSelect({ label, value, values, language, onChange }: { label: string; value: string; values: string[]; language: Language; onChange: (value: string) => void }) {
  return <label className="select-filter"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}><option value={ALL}>{language === "zh" ? "全部" : "All"}</option>{values.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>;
}

function HistoryChart({ data, lines }: { data: Array<Record<string, string | number | null>>; lines: Array<{ key: string; label: string; color: string }> }) {
  return <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 12, right: 12, left: -16, bottom: 8 }}><CartesianGrid stroke="#e5e7eb" vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} /><YAxis tickLine={false} axisLine={false} /><Tooltip /><Legend />{lines.map((line) => <Line key={line.key} type="monotone" dataKey={line.key} name={line.label} stroke={line.color} strokeWidth={2} connectNulls dot={{ r: 3 }} />)}</LineChart></ResponsiveContainer></div>;
}

function StatusTimeline({ runs, language }: { runs: RunSummary[]; language: Language }) {
  const labels = copy[language];
  return <div className="status-timeline">{runs.map((run, index) => {
    const previous = runs[index - 1];
    const modelChanged = Boolean(previous && (previous.model !== run.model || previous.provider !== run.provider));
    const promptChanged = Boolean(previous && previous.prompt_hash !== run.prompt_hash);
    const review = run.review_required ?? run.human_review_required ?? false;
    return <div className="status-timeline__row" key={run.id ?? run.name ?? index}>
      <span className="status-timeline__dot" aria-hidden="true" />
      <div className="status-timeline__body">
        <strong>{run.id ?? run.name ?? `Run ${index + 1}`}</strong>
        <span>{[run.provider, run.model].filter(Boolean).join(" / ") || labels.unknown}</span>
      </div>
      <div className="status-timeline__signals">
        <Badge tone="info">{decisionLabel(run.change_decision ?? run.gate_status ?? run.decision, language)}</Badge>
        <Badge tone={run.risk_level === "high" ? "danger" : run.risk_level === "medium" ? "warn" : "neutral"}>{riskLabel(run.risk_level, language)}</Badge>
        {review && <Badge tone="warn">{labels.needsReview}</Badge>}
        {modelChanged && <Badge>{language === "zh" ? "模型已变化" : "Model changed"}</Badge>}
        {promptChanged && <Badge>{language === "zh" ? "Prompt 已变化" : "Prompt changed"}</Badge>}
      </div>
    </div>;
  })}</div>;
}
