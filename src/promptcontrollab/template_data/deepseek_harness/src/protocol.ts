/** Versioned wire contract between the Cordis plugin and the local Python bridge. */

export const BRIDGE_PROTOCOL = 'prompt_control_lab.bridge.v1'

export type JsonPrimitive = string | number | boolean | null
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue }
export type JsonObject = { [key: string]: JsonValue }

export type HarnessBridgeMethod =
  | 'harness_session_start'
  | 'harness_pre_step'
  | 'harness_tool_pre_execute'
  | 'harness_event'
  | 'harness_turn_end'
  | 'harness_status'
  | 'harness_finalize'

export interface HarnessSessionStartParams extends JsonObject {
  session_id: string
  source: string
  mode: 'suggest' | 'gate'
  authorization: 'agent-scoped'
  policy_path: string | null
  capture: 'redacted'
  auto_recover: boolean
  max_auto_recoveries: number
  provider: string | null
  model: string | null
  runs_root: string
  harness_version: string
  harness_commit: string
  session_origin: 'live_cordis'
  bridge_transport: 'persistent_stdio'
}

export interface HarnessSessionStartResult extends JsonObject {
  run_id: string
  status: string
}

export interface HarnessPreStepParams extends JsonObject {
  run_id: string
  session_id: string
  turn: number
  step: number
  prompt: string
  prompt_hash: string
  policy_path: string | null
  feedback_max_chars: number
}

export interface HarnessPreStepResult extends JsonObject {
  decision: 'allow' | 'suggest' | 'deny'
  risk_level: 'low' | 'medium' | 'high' | 'unknown'
  summary: string
  feedback: string | null
}

export interface HarnessToolPreExecuteParams extends JsonObject {
  run_id: string
  session_id: string
  event_id: string
  tool: JsonObject
  policy_path: string | null
}

export interface HarnessToolPreExecuteResult extends JsonObject {
  decision: 'allow' | 'ask' | 'deny'
  reason: string
}

export interface HarnessEventParams extends JsonObject {
  run_id: string
  session_id: string
  idempotency_key: string
  event_type: string
  sequence: number | null
  timestamp: string
  payload: JsonObject
}

export interface HarnessEventResult extends JsonObject {
  accepted: boolean
  duplicate: boolean
}

export interface HarnessTurnEndParams extends JsonObject {
  run_id: string
  session_id: string
  turn: number
  reason: JsonObject
  feedback_max_chars: number
}

export interface HarnessTurnEndResult extends JsonObject {
  stability: 'converging' | 'stalled' | 'oscillating' | 'diverging' | 'insufficient_evidence'
  recommendation: string
  recover: boolean
}

export interface HarnessStatusParams extends JsonObject {
  run_id: string
  session_id: string
}

export interface HarnessStatusResult extends JsonObject {
  run_id: string
  status: string
  risk_level: string
  stability: string
  report_path: string | null
}

export interface HarnessFinalizeParams extends JsonObject {
  run_id: string
  session_id: string
}

export interface HarnessFinalizeResult extends JsonObject {
  run_id: string
  status: string
  report_path: string | null
}

export interface JsonRpcRequest {
  jsonrpc: '2.0'
  id: number
  method: HarnessBridgeMethod | 'health'
  params: JsonObject
}

export interface JsonRpcError {
  code: number
  message: string
  data?: JsonValue
}

export interface JsonRpcResponse {
  jsonrpc: '2.0'
  id: number
  result?: JsonObject
  error?: JsonRpcError
}
