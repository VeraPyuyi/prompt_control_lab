/** Persistent line-delimited JSON-RPC stdio client. */

import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { createInterface, type Interface as ReadlineInterface } from 'node:readline'
import type {
  HarnessEventParams,
  HarnessEventResult,
  HarnessFinalizeParams,
  HarnessFinalizeResult,
  HarnessPreStepParams,
  HarnessPreStepResult,
  HarnessSessionStartParams,
  HarnessSessionStartResult,
  HarnessStatusParams,
  HarnessStatusResult,
  HarnessToolPreExecuteParams,
  HarnessToolPreExecuteResult,
  HarnessTurnEndParams,
  HarnessTurnEndResult,
  JsonObject,
  JsonRpcRequest,
  JsonRpcResponse,
} from './protocol.ts'

interface PendingCall {
  resolve: (value: JsonObject) => void
  reject: (error: unknown) => void
  timer: ReturnType<typeof setTimeout>
  removeAbort?: () => void
}

/** Stable failure categories safe to expose outside the bridge process. */
export type BridgeFailureCategory =
  | 'aborted'
  | 'closed'
  | 'invalid-response'
  | 'process-exit'
  | 'remote-error'
  | 'timeout'
  | 'transport-error'

/** Describe a bridge failure without exposing raw subprocess or provider details. */
export class BridgeFailure extends Error {
  readonly category: BridgeFailureCategory

  constructor(category: BridgeFailureCategory, message?: string) {
    super(message ?? `PromptControlLab bridge ${category}`)
    this.name = 'BridgeFailure'
    this.category = category
  }
}

/** Classify an unknown error into the stable bridge failure taxonomy. */
export function bridgeFailureCategory(error: unknown): BridgeFailureCategory | 'unexpected' {
  return error instanceof BridgeFailure ? error.category : 'unexpected'
}

/** Stop waiting for shared lifecycle work when the current Harness operation aborts. */
export function settleWithAbort<T>(work: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) return Promise.reject(abortReason(signal))
  return new Promise<T>((resolve, reject) => {
    const onAbort = (): void => {
      signal.removeEventListener('abort', onAbort)
      reject(abortReason(signal))
    }
    signal.addEventListener('abort', onAbort, { once: true })
    if (signal.aborted) {
      onAbort()
      return
    }
    void work.then(
      value => {
        signal.removeEventListener('abort', onAbort)
        resolve(value)
      },
      error => {
        signal.removeEventListener('abort', onAbort)
        reject(error)
      },
    )
  })
}

/** Process and queue settings for a persistent JSON-RPC bridge client. */
export interface BridgeClientOptions {
  runsRoot: string
  timeoutMs: number
  command?: readonly string[]
  env?: NodeJS.ProcessEnv
}

/** Manage one persistent JSON-RPC subprocess and its in-flight requests. */
export class JsonRpcBridgeClient {
  private readonly options: BridgeClientOptions
  private process: ChildProcessWithoutNullStreams | undefined
  private lines?: ReadlineInterface
  private nextId = 1
  private readonly pending = new Map<number, PendingCall>()
  private closed = false

  constructor(options: BridgeClientOptions) {
    this.options = options
  }

  get pid(): number | undefined {
    return this.process?.pid
  }

  /** Send a versioned bridge request and validate transport-level completion. */
  async call(
    method: JsonRpcRequest['method'],
    params: JsonObject,
    signal?: AbortSignal,
  ): Promise<JsonObject> {
    if (signal?.aborted) throw abortReason(signal)
    const child = this.ensureStarted()
    const id = this.nextId++
    const request: JsonRpcRequest = { jsonrpc: '2.0', id, method, params }
    return new Promise<JsonObject>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.takePending(id)?.reject(new BridgeFailure('timeout'))
      }, this.options.timeoutMs)
      const pending: PendingCall = { resolve, reject, timer }
      if (signal) {
        const onAbort = (): void => {
          this.takePending(id)?.reject(abortReason(signal))
        }
        pending.removeAbort = () => signal.removeEventListener('abort', onAbort)
        signal.addEventListener('abort', onAbort, { once: true })
      }
      this.pending.set(id, pending)
      if (signal?.aborted) {
        this.takePending(id)?.reject(abortReason(signal))
        return
      }
      child.stdin.write(`${JSON.stringify(request)}\n`, error => {
        if (!error) return
        this.takePending(id)?.reject(new BridgeFailure('transport-error'))
      })
    })
  }

  /** Close the bridge process and reject no additional calls. */
  async close(): Promise<void> {
    if (this.closed) return
    this.closed = true
    const child = this.process
    this.lines?.close()
    if (!child) return
    child.stdin.end()
    await new Promise<void>(resolve => {
      if (child.exitCode !== null) return resolve()
      const timeout = setTimeout(() => {
        child.kill()
        resolve()
      }, 1_000)
      child.once('exit', () => {
        clearTimeout(timeout)
        resolve()
      })
    })
  }

  private ensureStarted(): ChildProcessWithoutNullStreams {
    if (this.closed) throw new BridgeFailure('closed')
    if (this.process) return this.process
    const command = this.options.command ?? [
      'pcl', 'bridge', 'serve', '--transport', 'stdio', '--runs-root', this.options.runsRoot,
    ]
    const executable = command[0]
    if (!executable) throw new BridgeFailure('transport-error')
    const child = spawn(executable, command.slice(1), {
      env: { ...process.env, ...this.options.env },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    })
    this.process = child
    this.lines = createInterface({ input: child.stdout })
    this.lines.on('line', line => this.handleLine(line))
    child.stderr.resume()
    child.once('error', () => this.failAll(new BridgeFailure('transport-error')))
    child.once('exit', () => {
      this.failAll(new BridgeFailure('process-exit'))
      this.process = undefined
    })
    return child
  }

  private handleLine(line: string): void {
    let response: JsonRpcResponse
    try {
      response = JSON.parse(line) as JsonRpcResponse
    } catch {
      this.failAll(new BridgeFailure('invalid-response'))
      return
    }
    const pending = this.takePending(response.id)
    if (!pending) return
    if (response.error) {
      pending.reject(new BridgeFailure('remote-error'))
    } else {
      pending.resolve(response.result ?? {})
    }
  }

  private takePending(id: number): PendingCall | undefined {
    const pending = this.pending.get(id)
    if (!pending) return undefined
    this.pending.delete(id)
    clearTimeout(pending.timer)
    pending.removeAbort?.()
    return pending
  }

  private failAll(error: Error): void {
    for (const id of [...this.pending.keys()]) {
      this.takePending(id)?.reject(error)
    }
  }
}

/** Expose typed Harness operations over the generic JSON-RPC client. */
export class HarnessBridge {
  private readonly client: JsonRpcBridgeClient

  constructor(client: JsonRpcBridgeClient) {
    this.client = client
  }

  /** Check whether the local bridge is responsive. */
  async health(): Promise<JsonObject> {
    return this.client.call('health', {})
  }

  /** Create a local ControlRun for a newly started Harness session. */
  async harnessSessionStart(params: HarnessSessionStartParams): Promise<HarnessSessionStartResult> {
    const result = await this.client.call('harness_session_start', params)
    requireNonEmptyString('harness_session_start', result, 'run_id')
    requireNonEmptyString('harness_session_start', result, 'status')
    return result as HarnessSessionStartResult
  }

  /** Inspect a pending agent step before a model request is allowed downstream. */
  async harnessPreStep(
    params: HarnessPreStepParams,
    signal?: AbortSignal,
  ): Promise<HarnessPreStepResult> {
    const result = await this.client.call('harness_pre_step', params, signal)
    requireEnum('harness_pre_step', result, 'decision', ['allow', 'suggest', 'deny'])
    requireEnum('harness_pre_step', result, 'risk_level', [
      'low', 'medium', 'high', 'unknown',
    ])
    requireString('harness_pre_step', result, 'summary')
    requireNullableString('harness_pre_step', result, 'feedback')
    return result as HarnessPreStepResult
  }

  /** Ask the local policy engine whether a tool call may proceed. */
  async harnessToolPreExecute(
    params: HarnessToolPreExecuteParams,
    signal?: AbortSignal,
  ): Promise<HarnessToolPreExecuteResult> {
    const result = await this.client.call('harness_tool_pre_execute', params, signal)
    requireEnum('harness_tool_pre_execute', result, 'decision', ['allow', 'ask', 'deny'])
    requireString('harness_tool_pre_execute', result, 'reason')
    return result as HarnessToolPreExecuteResult
  }

  /** Record one redacted, idempotent Harness observation. */
  async harnessEvent(params: HarnessEventParams): Promise<HarnessEventResult> {
    const result = await this.client.call('harness_event', params)
    requireBoolean('harness_event', result, 'accepted')
    requireBoolean('harness_event', result, 'duplicate')
    return result as HarnessEventResult
  }

  /** Update stability diagnostics and optional bounded recovery advice at turn end. */
  async harnessTurnEnd(params: HarnessTurnEndParams): Promise<HarnessTurnEndResult> {
    const result = await this.client.call('harness_turn_end', params)
    requireEnum('harness_turn_end', result, 'stability', [
      'converging', 'stalled', 'oscillating', 'diverging', 'insufficient_evidence',
    ])
    requireString('harness_turn_end', result, 'recommendation')
    requireBoolean('harness_turn_end', result, 'recover')
    return result as HarnessTurnEndResult
  }

  /** Read the current local control status without changing run state. */
  async harnessStatus(params: HarnessStatusParams): Promise<HarnessStatusResult> {
    const result = await this.client.call('harness_status', params)
    requireNonEmptyString('harness_status', result, 'run_id')
    requireNonEmptyString('harness_status', result, 'status')
    requireNonEmptyString('harness_status', result, 'risk_level')
    requireNonEmptyString('harness_status', result, 'stability')
    requireNullableString('harness_status', result, 'report_path')
    return result as HarnessStatusResult
  }

  /** Finalize a Harness-backed ControlRun and its report artifacts. */
  async harnessFinalize(params: HarnessFinalizeParams): Promise<HarnessFinalizeResult> {
    const result = await this.client.call('harness_finalize', params)
    requireNonEmptyString('harness_finalize', result, 'run_id')
    requireNonEmptyString('harness_finalize', result, 'status')
    requireNullableString('harness_finalize', result, 'report_path')
    return result as HarnessFinalizeResult
  }

  /** Close the underlying persistent bridge process. */
  async close(): Promise<void> {
    await this.client.close()
  }
}

function requireString(method: string, result: JsonObject, field: string): void {
  if (typeof result[field] !== 'string') throw malformedResponse(method, field)
}

function requireNonEmptyString(method: string, result: JsonObject, field: string): void {
  const value = result[field]
  if (typeof value !== 'string' || value.length === 0) throw malformedResponse(method, field)
}

function requireNullableString(method: string, result: JsonObject, field: string): void {
  const value = result[field]
  if (value !== null && typeof value !== 'string') throw malformedResponse(method, field)
}

function requireBoolean(method: string, result: JsonObject, field: string): void {
  if (typeof result[field] !== 'boolean') throw malformedResponse(method, field)
}

function requireEnum(
  method: string,
  result: JsonObject,
  field: string,
  allowed: readonly string[],
): void {
  const value = result[field]
  if (typeof value !== 'string' || !allowed.includes(value)) throw malformedResponse(method, field)
}

function malformedResponse(method: string, field: string): Error {
  return new BridgeFailure(
    'invalid-response',
    `malformed ${method} response: invalid ${field}`,
  )
}

function abortReason(signal: AbortSignal): unknown {
  return signal.reason ?? new BridgeFailure('aborted')
}
