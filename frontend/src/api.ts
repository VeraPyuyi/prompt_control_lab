import type {
  CheckpointImportResult,
  CheckpointVisualization,
  DiagnosticCatalog,
  Overview,
  RunSummary,
} from "./types";
import { getSessionToken } from "./experimentApi";

type JsonRecord = Record<string, unknown>;

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes((init?.method ?? "GET").toUpperCase())) {
    headers.set("X-PCL-Session", await getSessionToken());
  }
  const response = await fetch(path, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json() as { detail?: unknown };
      detail = typeof payload.detail === "string" ? `: ${payload.detail}` : "";
    } catch {
      // Keep the status-only fallback when the server does not return JSON.
    }
    throw new Error(`Request failed with status ${response.status}${detail}`);
  }
  return (await response.json()) as T;
}

export function fetchOverview(run?: string, language?: "en" | "zh"): Promise<Overview> {
  const params = new URLSearchParams();
  if (run) params.set("run", run);
  if (language) params.set("language", language);
  const query = params.toString();
  return requestJson<Overview>(`/api/overview${query ? `?${query}` : ""}`);
}

export async function fetchRuns(): Promise<RunSummary[]> {
  const payload = await requestJson<JsonRecord[] | { runs?: JsonRecord[] }>("/api/runs");
  return (Array.isArray(payload) ? payload : (payload.runs ?? [])).map(normalizeRun);
}

export async function fetchHistory(): Promise<RunSummary[]> {
  const payload = await requestJson<JsonRecord[] | { runs?: JsonRecord[] }>("/api/history");
  return (Array.isArray(payload) ? payload : (payload.runs ?? [])).map(normalizeRun);
}

export async function fetchDiagnosticCatalog(
  language: "en" | "zh",
  run?: string,
): Promise<DiagnosticCatalog> {
  const params = new URLSearchParams({ language });
  if (run) params.set("run", run);
  const payload = await requestJson<DiagnosticCatalog | { diagnostics?: DiagnosticCatalog }>(
    `/api/diagnostics/catalog?${params.toString()}`,
  );
  const nested = (payload as { diagnostics?: DiagnosticCatalog }).diagnostics;
  return nested ?? (payload as DiagnosticCatalog);
}

export function fetchCheckpointSeries(run: string): Promise<CheckpointVisualization> {
  const params = new URLSearchParams({ run });
  return requestJson<CheckpointVisualization>(`/api/checkpoint-series?${params.toString()}`);
}

export function importCheckpointRun(
  name: string,
  csvText: string,
): Promise<CheckpointImportResult> {
  return requestJson<CheckpointImportResult>("/api/checkpoint-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, csv_text: csvText }),
  });
}

function normalizeRun(row: JsonRecord): RunSummary {
  const model = asRecord(row.model);
  const prompt = asRecord(row.prompt_identity);
  const agentRun = asRecord(row.agent_run);
  return {
    id: asString(row.id) ?? asString(row.run_name) ?? asString(row.name),
    name: asString(row.name) ?? asString(row.run_name),
    path: asString(row.path),
    created_at: asString(row.created_at),
    score: asNumber(row.score),
    mean_score: asNumber(row.mean_score),
    gate_status: asString(row.gate_status),
    decision: asString(row.decision),
    change_decision: asString(row.change_decision),
    risk_level: asString(row.risk_level),
    model: asString(row.model) ?? asString(model.model_id) ?? asString(agentRun.model),
    provider: asString(row.provider) ?? asString(model.provider) ?? asString(agentRun.provider),
    prompt_hash: asString(row.prompt_hash) ?? asString(prompt.prompt_hash) ?? asString(agentRun.prompt_hash),
    review_required: asBoolean(row.review_required),
    human_review_required: asBoolean(row.human_review_required),
    model_changed: asBoolean(row.model_changed),
    score_regressed: asBoolean(row.score_regressed),
    title: asLocalizedText(row.title),
    summary: asLocalizedText(row.summary),
    boundary: asLocalizedText(row.boundary),
    category: asString(row.category),
    evidence_level: asString(row.evidence_level),
    featured: asBoolean(row.featured),
    order: asNumber(row.order) ?? undefined,
    technical_change_kind: asString(row.technical_change_kind),
  };
}

function asLocalizedText(value: unknown): { en?: string; zh?: string } | undefined {
  const row = asRecord(value);
  const en = asString(row.en);
  const zh = asString(row.zh);
  return en || zh ? { en, zh } : undefined;
}

function asRecord(value: unknown): JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function asNumber(value: unknown): number | null | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}
