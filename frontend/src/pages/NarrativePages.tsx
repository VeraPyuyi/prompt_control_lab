import { ArrowRight, CheckCircle2, CircleDot, ShieldAlert } from "lucide-react";

import { changeKindLabel, copy, decisionLabel, evidenceName } from "../i18n";
import { isEvidenceCovered } from "../lib/utils";
import type { Language, Overview } from "../types";
import { PageHeader } from "../components/PageHeader";
import { Badge, Card } from "../components/ui";

export function BeforePage({ overview, language }: { overview: Overview; language: Language }) {
  const labels = copy[language];
  const coverage = Object.entries(overview.evidence_coverage ?? {});
  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.beforeTitle} lead={labels.beforeLead} />
      <div className="two-column-grid">
        <Card>
          <div className="card-heading"><CircleDot /><h2>{labels.changeType}</h2></div>
          <p className="large-value">{changeKindLabel(overview.change_kind ?? overview.kind, language)}</p>
          <p className="muted">{language === "zh" ? "先确认本次比较只改变了计划中的变量。" : "Confirm that the comparison changes only the intended variable."}</p>
        </Card>
        <Card>
          <div className="card-heading"><ShieldAlert /><h2>{labels.evidenceCoverage}</h2></div>
          <ul className="coverage-list">
            {coverage.map(([key, value]) => {
              const covered = isEvidenceCovered(value);
              return <li key={key}><span>{evidenceName(key, language)}</span><Badge tone={covered ? "good" : "warn"}>{covered ? labels.covered : labels.missing}</Badge></li>;
            })}
          </ul>
        </Card>
      </div>
    </>
  );
}

export function WhyPage({ overview, language }: { overview: Overview; language: Language }) {
  const labels = copy[language];
  const causes = overview.likely_causes ?? overview.causes ?? [];
  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.whyTitle} lead={labels.whyLead} />
      <div className="cause-stack">
        {(causes.length ? causes : [labels.noCause]).map((cause, index) => (
          <Card key={`${cause}-${index}`} className="cause-card">
            <span className="cause-card__rank">{index + 1}</span>
            <div><h2>{language === "zh" ? `候选原因 ${index + 1}` : `Candidate cause ${index + 1}`}</h2><p>{cause}</p></div>
          </Card>
        ))}
      </div>
    </>
  );
}

export function AfterPage({ overview, language }: { overview: Overview; language: Language }) {
  const labels = copy[language];
  const observations = overview.observations ?? [];
  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.afterTitle} lead={labels.afterLead} />
      <Card>
        <div className="card-heading"><CheckCircle2 /><h2>{labels.observed}</h2></div>
        <ul className="observation-list">
          {(observations.length ? observations : [labels.noObservation]).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </Card>
    </>
  );
}

export function DecisionPage({ overview, language }: { overview: Overview; language: Language }) {
  const labels = copy[language];
  const conclusion = overview.conclusion ?? overview.decision ?? overview.status;
  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.decisionTitle} lead={labels.decisionLead} />
      <Card className="decision-panel">
        <div>
          <span>{labels.conclusion}</span>
          <h2>{decisionLabel(conclusion, language)}</h2>
        </div>
        <ArrowRight aria-hidden="true" />
        <div>
          <span>{labels.nextAction}</span>
          <p>{overview.next_action ?? labels.releaseBoundary}</p>
        </div>
      </Card>
      <p className="boundary-banner">{labels.releaseBoundary}</p>
    </>
  );
}
