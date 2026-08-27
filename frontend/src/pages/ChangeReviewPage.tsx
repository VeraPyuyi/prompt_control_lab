import { AlertTriangle, ArrowRight, Check, CircleHelp, Layers3 } from "lucide-react";

import {
  changeKindLabel,
  copy,
  decisionLabel,
  evidenceLevelLabel,
  evidenceName,
  riskLabel,
} from "../i18n";
import { isEvidenceCovered } from "../lib/utils";
import type { Language, LocalizedText, Overview, RunSummary } from "../types";
import { PageHeader } from "../components/PageHeader";
import { Badge, Card } from "../components/ui";

function toneForDecision(value: string): "good" | "warn" | "danger" | "neutral" {
  if (value === "pass" || value === "passed") return "good";
  if (value === "hold" || value === "fail" || value === "failed") return "danger";
  if (value === "needs_review" || value === "review") return "warn";
  return "neutral";
}

interface ChangeReviewPageProps {
  overview: Overview;
  language: Language;
  cases: RunSummary[];
  selectedRun: string;
  onSelectRun: (name: string) => void;
}

function localized(value: LocalizedText | undefined, language: Language): string {
  return value?.[language] ?? value?.en ?? value?.zh ?? "";
}

export function ChangeReviewPage({
  overview,
  language,
  cases,
  selectedRun,
  onSelectRun,
}: ChangeReviewPageProps) {
  const labels = copy[language];
  const conclusion = overview.conclusion ?? overview.decision ?? overview.status;
  const risk = overview.risk ?? overview.risk_level ?? "unknown";
  const causes = overview.likely_causes ?? overview.causes ?? [];
  const observations = overview.observations ?? [];
  const coverage = Object.entries(overview.evidence_coverage ?? {});

  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.changeReview} lead={labels.changeReviewLead} />
      {cases.length ? (
        <section className="case-section" aria-labelledby="featured-case-heading">
          <div className="section-heading">
            <div>
              <h2 id="featured-case-heading">{labels.featuredCases}</h2>
              <p>{labels.featuredCasesLead}</p>
            </div>
          </div>
          <div className="case-gallery">
            {[...cases]
              .sort((left, right) => (left.order ?? 10_000) - (right.order ?? 10_000))
              .map((item) => {
                const name = item.name ?? "";
                const active = name === selectedRun;
                const title = localized(item.title, language) || name;
                return (
                  <button
                    key={name}
                    type="button"
                    className={`case-card${active ? " case-card--active" : ""}`}
                    aria-pressed={active}
                    onClick={() => onSelectRun(name)}
                  >
                    <div className="case-card__top">
                      <span className="case-card__category">
                        {changeKindLabel(item.technical_change_kind, language)}
                      </span>
                      {active ? <span className="case-card__selected">{labels.selectedCase}</span> : null}
                    </div>
                    <h3>{title}</h3>
                    <p className="case-card__summary">{localized(item.summary, language)}</p>
                    <dl className="case-card__facts">
                      <div>
                        <dt>{labels.conclusion}</dt>
                        <dd>{decisionLabel(item.decision, language)}</dd>
                      </div>
                      <div>
                        <dt>{labels.caseEvidence}</dt>
                        <dd>{evidenceLevelLabel(item.evidence_level, language)}</dd>
                      </div>
                    </dl>
                    <div className="case-card__boundary">
                      <strong>{labels.caseBoundary}</strong>
                      <span>{localized(item.boundary, language)}</span>
                    </div>
                  </button>
                );
              })}
          </div>
        </section>
      ) : null}
      <div className="summary-strip">
        <div>
          <span>{labels.conclusion}</span>
          <Badge tone={toneForDecision(conclusion ?? "")}>{decisionLabel(conclusion, language)}</Badge>
        </div>
        <div>
          <span>{labels.changeType}</span>
          <strong>{changeKindLabel(overview.change_kind ?? overview.kind, language)}</strong>
        </div>
        <div>
          <span>{labels.risk}</span>
          <Badge tone={risk === "high" ? "danger" : risk === "medium" ? "warn" : "good"}>
            {riskLabel(risk, language)}
          </Badge>
        </div>
      </div>
      <div className="review-grid">
        <Card className="review-grid__primary">
          <div className="card-heading">
            <Layers3 aria-hidden="true" />
            <h2>{labels.likelyCauses}</h2>
          </div>
          {causes.length ? (
            <ol className="cause-list">
              {causes.map((cause, index) => (
                <li key={`${cause}-${index}`}>
                  <span>{index + 1}</span>
                  <p>{cause}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">{labels.noCause}</p>
          )}
        </Card>
        <Card>
          <div className="card-heading">
            <Check aria-hidden="true" />
            <h2>{labels.evidenceCoverage}</h2>
          </div>
          {coverage.length ? (
            <ul className="coverage-list">
              {coverage.map(([name, value]) => {
                const covered = isEvidenceCovered(value);
                return (
                  <li key={name}>
                    <span>{evidenceName(name, language)}</span>
                    <Badge tone={covered ? "good" : "neutral"}>
                      {covered ? labels.covered : labels.missing}
                    </Badge>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="muted">{labels.noData}</p>
          )}
        </Card>
        <Card>
          <div className="card-heading">
            <CircleHelp aria-hidden="true" />
            <h2>{labels.observed}</h2>
          </div>
          <ul className="plain-list">
            {(observations.length ? observations : [labels.noObservation]).map((observation) => (
              <li key={observation}>{observation}</li>
            ))}
          </ul>
        </Card>
        <Card className="next-action-card">
          <div className="card-heading">
            <AlertTriangle aria-hidden="true" />
            <h2>{labels.nextAction}</h2>
          </div>
          <p>{overview.next_action ?? labels.releaseBoundary}</p>
          <div className="boundary-note">
            <ArrowRight aria-hidden="true" />
            <span>{labels.releaseBoundary}</span>
          </div>
        </Card>
      </div>
    </>
  );
}
