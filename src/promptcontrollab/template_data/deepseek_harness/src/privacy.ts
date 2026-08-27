/** Privacy-preserving projections for Harness events. */

import { createHash } from 'node:crypto'
import type { JsonObject, JsonValue } from './protocol.ts'

export type RetryObservationType = 'agent/request' | 'agent/request-error'

/** Deterministic occurrence counters for retryable request lifecycle events. */
export class RetryAttemptTracker {
  private readonly counts = new Map<string, number>()

  next(eventType: RetryObservationType, turn: number, step: number): number {
    const key = JSON.stringify([eventType, turn, step])
    const attempt = (this.counts.get(key) ?? 0) + 1
    this.counts.set(key, attempt)
    return attempt
  }
}

/** Compute a tagged SHA-256 digest for redacted event identities. */
export function sha256(value: string): string {
  return `sha256:${createHash('sha256').update(value, 'utf8').digest('hex')}`
}

/** Match Python stable_digest for the string-valued Harness prompt path. */
export function stableJsonDigest(value: string): string {
  return sha256(JSON.stringify(toStableJson(value)))
}

/** Bound feedback text before it can re-enter the agent context. */
export function boundedText(value: unknown, maxChars: number): string {
  const text = typeof value === 'string' ? value : ''
  if (text.length <= maxChars) return text
  return `${text.slice(0, Math.max(0, maxChars - 1))}…`
}

/** Extract visible text blocks from a proposed Harness message batch. */
export function extractPromptText(messages: readonly unknown[]): string {
  const parts: string[] = []
  for (const candidate of messages) {
    if (!isRecord(candidate) || !Array.isArray(candidate.content)) continue
    for (const block of candidate.content) {
      if (isRecord(block) && block.type === 'text' && typeof block.text === 'string') {
        parts.push(block.text)
      }
    }
  }
  const prompt = parts.join('\n')
  return prompt.trim() ? prompt : ''
}

/** Token chunks are durable replay facts, not useful control observations. */
export function shouldObserveSessionEvent(eventType: string): boolean {
  return eventType !== 'assistant/chunk'
}

/** Project a tool call into redacted metadata suitable for local persistence. */
export function safeToolMetadata(exec: unknown): JsonObject {
  if (!isRecord(exec)) return {}
  const argumentsValue = toStableJson(exec.arguments)
  const keys = isRecord(exec.arguments) ? Object.keys(exec.arguments).sort() : []
  return compact({
    call_id: stringValue(exec.callId),
    root_call_id: stringValue(exec.rootCallId),
    name: stringValue(exec.name),
    operation_category: classifyToolOperation(exec.name, exec.arguments),
    argument_hash: sha256(JSON.stringify(argumentsValue)),
    argument_keys: keys,
  })
}

/** Project a tool result into bounded status metadata without result content. */
export function safeToolResult(result: unknown): JsonObject {
  if (!isRecord(result)) return {}
  const error = isRecord(result.error)
    ? compact({ name: stringValue(result.error.name), code: stringValue(result.error.code) })
    : null
  const value = isRecord(result.value) ? result.value : {}
  return compact({
    is_error: result.isError === true,
    exit_code: integerValue(value.exitCode),
    error,
    concludes_turn: result.concludesTurn === true,
    content_block_count: Array.isArray(result.content) ? result.content.length : 0,
  })
}

/** Reduce a provider request failure to non-secret retry metadata. */
export function safeRequestFailure(failure: unknown): JsonObject {
  if (!isRecord(failure)) return { kind: 'unknown' }
  return compact({
    kind: stringValue(failure.kind) ?? stringValue(failure.name) ?? 'unknown',
    code: stringValue(failure.code),
    status: numberValue(failure.status),
    retryable: booleanValue(failure.retryable),
  })
}

/** Convert a Harness session event into a redacted control observation. */
export function safeSessionEvent(event: unknown): JsonObject {
  if (!isRecord(event)) return { event_type: 'unknown' }
  const eventType = stringValue(event.type) ?? 'unknown'
  const data = isRecord(event.data) ? event.data : {}
  const payload: JsonObject = compact({
    event_type: eventType,
    harness_sequence: numberValue(event.seq),
    harness_time_ms: numberValue(event.time),
    turn: numberValue(data.turn),
    step: numberValue(data.step),
  })

  if (eventType === 'tool/call') {
    payload.tool_name = stringValue(data.name) ?? 'unknown'
    payload.call_id = stringValue(data.callId) ?? 'unknown'
    payload.argument_hash = sha256(stringValue(data.arguments) ?? '')
  } else if (eventType === 'tool/result') {
    payload.is_error = isToolResultError(data.message)
    if (isRecord(data.error)) {
      payload.error = compact({
        name: stringValue(data.error.name),
        code: stringValue(data.error.code),
      })
    }
  } else if (eventType === 'assistant/message') {
    const message = isRecord(data.message) ? data.message : {}
    const source = isRecord(message.source) ? message.source : {}
    Object.assign(payload, compact({
      response_id: stringValue(message.id),
      provider: stringValue(source.provider),
      model: stringValue(source.model),
    }))
    payload.usage = safeUsage(data.usage)
    payload.interrupted = data.interrupted === true
  } else if (eventType === 'user/message' && isRecord(data.source)) {
    payload.source = compact({
      kind: stringValue(data.source.kind),
      plugin: stringValue(data.source.plugin),
      form: stringValue(data.source.form),
    })
  }

  const signals = guardSignals(eventType, data)
  if (signals.length > 0) payload.harness_guard_signals = signals
  return payload
}

function classifyToolOperation(nameValue: unknown, argumentsValue: unknown): string {
  const name = (stringValue(nameValue) ?? '').toLowerCase()
  const argumentText = collectStringValues(argumentsValue).join(' ').toLowerCase()
  const combined = `${name} ${argumentText}`
  if (/\b(pytest|unittest|jest|vitest|cargo test|go test|npm test|pnpm test|yarn test)\b/.test(combined)) {
    return 'test_execution'
  }
  if (/(apply[_-]?patch|edit|replace|write|create[_-]?file)/.test(name)) return 'file_write'
  if (/(read|view|open[_-]?file|cat)/.test(name)) return 'file_read'
  return 'other'
}

function collectStringValues(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(collectStringValues)
  if (isRecord(value)) return Object.values(value).flatMap(collectStringValues)
  return []
}

/** Build a deterministic idempotency key for replay-safe event ingestion. */
export function stableEventKey(sessionId: string, eventType: string, identity: unknown): string {
  return sha256(JSON.stringify([sessionId, eventType, toStableJson(identity)]))
}

function guardSignals(eventType: string, data: Record<string, unknown>): JsonValue[] {
  const signals: string[] = []
  const source = isRecord(data.source) ? data.source : {}
  const plugin = stringValue(source.plugin)?.toLowerCase() ?? ''
  if (plugin.includes('repeat-tool-reminder')) signals.push('repeat_tool_reminder')
  const error = isRecord(data.error) ? data.error : {}
  const code = stringValue(error.code)?.toLowerCase() ?? ''
  if (code.includes('timeout') || eventType.toLowerCase().includes('timeout')) {
    signals.push('tool_timeout')
  }
  return signals
}

function safeUsage(value: unknown): JsonObject {
  if (!isRecord(value)) return {}
  return compact({
    input_tokens: numberValue(value.inputTokens),
    output_tokens: numberValue(value.outputTokens),
    cache_read_tokens: numberValue(value.cacheReadTokens),
    cache_write_tokens: numberValue(value.cacheWriteTokens),
  })
}

function isToolResultError(message: unknown): boolean {
  if (!isRecord(message) || !Array.isArray(message.content)) return false
  return message.content.some(block => isRecord(block) && block.isError === true)
}

function toStableJson(value: unknown): JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value
  if (typeof value === 'number') return Number.isFinite(value) ? value : String(value)
  if (Array.isArray(value)) return value.map(toStableJson)
  if (isRecord(value)) {
    const output: JsonObject = {}
    for (const key of Object.keys(value).sort()) output[key] = toStableJson(value[key])
    return output
  }
  return String(value)
}

function compact(value: Record<string, JsonValue | undefined>): JsonObject {
  const result: JsonObject = {}
  for (const [key, item] of Object.entries(value)) {
    if (item !== undefined) result[key] = item
  }
  return result
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : undefined
}

function numberValue(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function integerValue(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) ? value : undefined
}

function booleanValue(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined
}
