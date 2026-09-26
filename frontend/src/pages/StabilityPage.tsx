import { Activity, CircleGauge, Target } from "lucide-react";

import {
  copy,
  diagnosticMetricLabel,
  diagnosticStatusLabel,
  localizeDiagnostic,
} from "../i18n";
import { formatNumber } from "../lib/utils";
import type { DiagnosticCatalog, Language } from "../types";
import { EmptyPanel } from "../components/StatePanel";
import { PageHeader } from "../components/PageHeader";
import { Badge, Card } from "../components/ui";

const diagnosticOrder = ["terminal_sensitivity", "green_certificate", "posterior_certificate"];
const icons = [Target, Activity, CircleGauge];

export function StabilityPage({ catalog, language }: { catalog: DiagnosticCatalog; language: Language }) {
  const labels = copy[language];
  const entries = diagnosticOrder
    .filter((id) => catalog[id])
    .map((id) => localizeDiagnostic(id, catalog[id], language));

  return (
    <>
      <PageHeader eyebrow={labels.pageEyebrow} title={labels.stabilityTitle} lead={labels.stabilityLead} />
      {!entries.length ? <EmptyPanel language={language} /> : (
        <div className="diagnostic-grid">
          {entries.map((entry, index) => {
            const Icon = icons[index];
            return (
              <Card key={entry.id} className="diagnostic-card">
                <div className="diagnostic-card__top">
                  <span className="diagnostic-icon"><Icon aria-hidden="true" /></span>
                  <Badge tone={entry.status === "certificate_verified" ? "good" : "info"}>
                    {diagnosticStatusLabel(entry.status ?? entry.certificate_level, language)}
                  </Badge>
                </div>
                <h2>{entry.label}</h2>
                <p className="technical-name">{labels.technicalName}：{entry.technical_name}</p>
                <div className="diagnostic-purpose">
                  <strong>{labels.whatItDoes}</strong>
                  <p>{entry.purpose ?? entry.question ?? labels.noDataHelp}</p>
                </div>
                <DiagnosticSection
                  label={labels.currentEvidence}
                  value={diagnosticStatusLabel(entry.status ?? entry.certificate_level, language)}
                />
                {entry.metrics && Object.keys(entry.metrics).length > 0 && (
                  <dl className="metric-list">
                    {Object.entries(entry.metrics).slice(0, 3).map(([name, value]) => (
                      <div key={name}><dt>{diagnosticMetricLabel(name, language)}</dt><dd>{formatNumber(value)}</dd></div>
                    ))}
                  </dl>
                )}
                <DiagnosticSection
                  label={labels.whatItMeans}
                  value={entry.meaning ?? labels.noDataHelp}
                />
                <DiagnosticSection
                  label={labels.cannotProve}
                  value={entry.claim_boundary ?? labels.releaseBoundary}
                />
                <DiagnosticSection
                  label={labels.nextAction}
                  value={entry.next_action ?? labels.noDataHelp}
                />
              </Card>
            );
          })}
        </div>
      )}
      <p className="boundary-banner">{labels.releaseBoundary}</p>
    </>
  );
}

function DiagnosticSection({ label, value }: { label: string; value: string }) {
  return (
    <div className="diagnostic-section">
      <strong>{label}</strong>
      <p>{value}</p>
    </div>
  );
}
