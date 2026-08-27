/** Versioned wire contract between the Cordis plugin and the local Python bridge. */

export const BRIDGE_PROTOCOL = 'prompt_control_lab.bridge.v1'

/** JSON scalar values accepted by the bridge protocol. */
export type JsonPrimitive = string | number | boolean | null
/** Recursively serializable values accepted by the bridge protocol. */
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue }
/** String-keyed JSON object used by protocol request and response records. */
export type JsonObject = { [key: string]: JsonValue }

/** Versioned method names implemented by the persistent local bridge. */
export type HarnessBridgeMethod =
  | 'harness_session_start'
  | 'harness_pre_step'
  | 'harness_tool_pre_execute'
  | 'harness_event'
  | 'harness_turn_end'
  | 'harness_status'
  | 'harness_finalize'

/** Sanitized metadata sent when a Harness session starts. */
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

/** Bridge result returned after a control run has been created. */
export interface HarnessSessionStartResult extends JsonObject {
  run_id: string
  status: string
}

/** Prompt hash and bounded metadata inspected before a model step. */
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

/** Allow, suggest, or deny decision returned for a model step. */
export interface HarnessPreStepResult extends JsonObject {
  decision: 'allow' | 'suggest' | 'deny'
  risk_level: 'low' | 'medium' | 'high' | 'unknown'
  summary: string
  feedback: string | null
}

/** Sanitized tool metadata inspected before tool execution. */
export interface HarnessToolPreExecuteParams extends JsonObject {
  run_id: string
  session_id: string
  event_id: string
  tool: JsonObject
  policy_path: string | null
}

/** Allow, ask, or deny decision returned before tool execution. */
export interface HarnessToolPreExecuteResult extends JsonObject {
  decision: 'allow' | 'ask' | 'deny'
  reason: string
}

/** Sequenced, redacted observation sent for one Harness lifecycle event. */
export interface HarnessEventParams extends JsonObject {
  run_id: string
  session_id: string
  idempotency_key: string
  event_type: string
  sequence: number | null
  timestamp: string
  payload: JsonObject
}

/** Acknowledgement returned after an observation is recorded. */
export interface HarnessEventResult extends JsonObject {
  accepted: boolean
  duplicate: boolean
}

/** Bounded turn summary used to refresh stability diagnostics. */
export interface HarnessTurnEndParams extends JsonObject {
  run_id: string
  session_id: string
  turn: number
  reason: JsonObject
  feedback_max_chars: number
}

/** Stability and recovery guidance returned at turn completion. */
export interface HarnessTurnEndResult extends JsonObject {
  stability: 'converging' | 'stalled' | 'oscillating' | 'diverging' | 'insufficient_evidence'
  recommendation: string
  recover: boolean
}

/** Session identifier used to request a read-only control status. */
export interface HarnessStatusParams extends JsonObject {
  run_id: string
  session_id: string
}

/** Read-only control status exposed to the Harness integration. */
export interface HarnessStatusResult extends JsonObject {
  run_id: string
  status: string
  risk_level: string
  stability: string
  report_path: string | null
}

/** Session metadata sent when finalizing a Harness control run. */
export interface HarnessFinalizeParams extends JsonObject {
  run_id: string
  session_id: string
}

/** Final report location and decision returned after finalization. */
export interface HarnessFinalizeResult extends JsonObject {
  run_id: string
  status: string
  report_path: string | null
}

/** JSON-RPC request envelope sent over the persistent stdio bridge. */
export interface JsonRpcRequest {
  jsonrpc: '2.0'
  id: number
  method: HarnessBridgeMethod | 'health'
  params: JsonObject
}

/** Bounded JSON-RPC error envelope safe for plugin display. */
export interface JsonRpcError {
  code: number
  message: string
  data?: JsonValue
}

/** JSON-RPC response envelope returned by the local bridge. */
export interface JsonRpcResponse {
  jsonrpc: '2.0'
  id: number
  result?: JsonObject
  error?: JsonRpcError
}
