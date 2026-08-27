export type Language = "en" | "zh";

export interface LocalizedText {
  en?: string;
  zh?: string;
}

export type ViewId =
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
