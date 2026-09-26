export type Language = "en" | "zh";

export interface LocalizedText {
  en?: string;
  zh?: string;
}

export type ViewId =
  | "experiment"
  | "research"
  | "change-review"
  | "before"
  | "run"
  | "why"
  | "after"
  | "decision"
  | "history"
  | "stability";

export interface Overview {
  ui_language?: Language;
  checkpoint_import_enabled?: boolean;
  conclusion?: string;
  decision?: string;
  status?: string;
  change_kind?: string;
  kind?: string;
  likely_causes?: string[];
  causes?: string[];
  risk?: string;
  risk_level?: string;
  evidence_coverage?: Record<string, boolean | string | number | null>;
  next_action?: string;
  observations?: string[];
  changed?: string[];
  baseline?: Record<string, unknown>;
  candidate?: Record<string, unknown>;
}

export interface RunSummary {
  id?: string;
  name?: string;
  path?: string;
  created_at?: string;
  score?: number | null;
  mean_score?: number | null;
  gate_status?: string;
  decision?: string;
  risk_level?: string;
  model?: string;
  provider?: string;
  review_required?: boolean;
  human_review_required?: boolean;
  change_decision?: string;
  prompt_hash?: string;
  model_changed?: boolean;
  score_regressed?: boolean;
  title?: LocalizedText;
  summary?: LocalizedText;
  boundary?: LocalizedText;
  category?: string;
  evidence_level?: string;
  featured?: boolean;
  order?: number;
  technical_change_kind?: string;
}

export interface CheckpointPoint {
  seed: string;
  stage: string;
  checkpoint_id: string;
  mean_score: number;
  step?: number;
  generation_mismatch?: number;
  selective_aurc?: number;
  trajectory_drift?: number;
  format_following_score?: number;
  mean_tokens?: number;
  mean_latency_ms?: number;
  readout_alignment_gap?: number;
  reachability_shift?: number;
}

export interface CheckpointAggregate {
  stage: string;
  seed_count?: number;
  mean_score: number;
  generation_mismatch?: number;
  selective_aurc?: number;
  trajectory_drift?: number;
  format_following_score?: number;
  mean_tokens?: number;
  mean_latency_ms?: number;
  readout_alignment_gap?: number;
  reachability_shift?: number;
}

export interface CheckpointDiagnostic {
  available: boolean;
  direction: "lower_is_better" | "context_dependent" | string;
  aggregates: Array<{ stage: string; value?: number | null }>;
}

export interface CheckpointNarrative {
  changed?: string;
  observed?: string;
  meaning?: string;
  boundary?: string;
  next_action?: string;
}

export interface CheckpointGateCheck {
  check?: string;
  observed?: string | number | null;
  observed_mean?: string | number | null;
  threshold?: string | number | null;
  impact?: string;
  status?: string;
}

export interface CheckpointVisualization {
  schema: string;
  decision: string;
  evidence_level?: string;
  stage_order: string[];
  seeds: string[];
  points: CheckpointPoint[];
  aggregates: CheckpointAggregate[];
  diagnostics?: Record<string, CheckpointDiagnostic>;
  triggered_checks?: CheckpointGateCheck[];
  narrative?: Partial<Record<Language, CheckpointNarrative>>;
  claim_boundary?: string;
}

export interface CheckpointImportResult {
  run: RunSummary;
  decision: string;
  warnings?: string[];
}

export interface DiagnosticEntry {
  id?: string;
  label?: string;
  technical_name?: string;
  purpose?: string;
  question?: string;
  meaning?: string;
  claim_boundary?: string;
  next_action?: string;
  status?: string;
  certificate_level?: string;
  metrics?: Record<string, string | number | null>;
}

export type DiagnosticCatalog = Record<string, DiagnosticEntry>;
