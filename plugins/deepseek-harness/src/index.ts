/** Native DeepSeek Harness Cordis integration for PromptControlLab. */

import type { Context } from '@deepseek-ai/cordis'
import type { Agent, PreStepDecision, RequestErrorAction } from '@deepseek-ai/dsh-agent'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import type { SessionEvent, UserMessage } from '@deepseek-ai/dsh-session'
import {
  defineTool,
  type PostToolDecision,
  type PreToolDecision,
  type ToolExecution,
  type ToolExecutionResult,
} from '@deepseek-ai/dsh-tools'
import {
  bridgeFailureCategory,
  HarnessBridge,
  JsonRpcBridgeClient,
  settleWithAbort,
} from './bridge.ts'
import { Config, resolveConfig, type ResolvedConfig } from './config.ts'
import { gateFinalPreStep, toolGateAction } from './decisions.ts'
import { BoundedObservationQueue } from './observation-queue.ts'
import {
  boundedText,
  RetryAttemptTracker,
  safeRequestFailure,
  safeSessionEvent,
  safeToolMetadata,
  safeToolResult,
  shouldObserveSessionEvent,
  stableJsonDigest,
  stableEventKey,
} from './privacy.ts'
import type {
  HarnessEventParams,
  HarnessTurnEndResult,
  JsonObject,
} from './protocol.ts'
import { SessionRunLifecycle } from './run-lifecycle.ts'

/** Cordis plugin name used by DeepSeek Harness configuration. */
export const name = 'prompt-control-lab-deepseek-harness'
/** Harness services injected into the plugin lifecycle. */
export const inject = ['tools']
/** Re-export the runtime configuration schema for Cordis discovery. */
export { Config }
/** Re-export the static plugin configuration type for integrators. */
export type { Config as PluginConfig } from './config.ts'

const HARNESS_VERSION = '0.1.1-rc.2'
const HARNESS_COMMIT = 'b150a551b8d465e31e418e1b2eaf5e79bbb7d28e'
const PLUGIN_SOURCE = { kind: 'plugin' as const, plugin: name, form: 'notice' as const }

interface RunState {
  runId: string
  sessionId: string
  observationSequence: number
  recoveryCount: number
  retryAttempts: RetryAttemptTracker
  lastTurnDecision?: HarnessTurnEndResult
}

type ObservationTask = () => Promise<void>

/** Install the native Cordis listeners and one persistent local bridge process. */
export function apply(ctx: Context, input: import('./config.ts').Config): void {
  const config = resolveConfig(input)
  const client = new JsonRpcBridgeClient({
    runsRoot: config.runsRoot,
    timeoutMs: config.bridgeTimeoutMs,
  })
  const bridge = new HarnessBridge(client)
  const observations = new BoundedObservationQueue<ObservationTask>(
    config.observationQueueSize,
    task => task(),
    error => ctx.logger.warn(
      `PromptControlLab observation failed: ${bridgeFailureCategory(error)}`,
    ),
  )
  const lifecycle = new SessionRunLifecycle<Agent, RunState>({
    idOf: agent => String(agent.id),
    start: async (agent, source) => {
      const sessionId = String(agent.id)
      const result = await bridge.harnessSessionStart({
        session_id: sessionId,
        source,
        mode: config.mode,
        authorization: 'agent-scoped',
        policy_path: config.policyPath ?? null,
        capture: 'redacted',
        auto_recover: config.autoRecover,
        max_auto_recoveries: config.maxAutoRecoveries,
        provider: agent.options.provider ?? null,
        model: agent.options.model ?? null,
        runs_root: config.runsRoot,
        harness_version: HARNESS_VERSION,
        harness_commit: HARNESS_COMMIT,
        session_origin: 'live_cordis',
        bridge_transport: 'persistent_stdio',
      })
      return {
        runId: result.run_id,
        sessionId,
        observationSequence: 0,
        recoveryCount: 0,
        retryAttempts: new RetryAttemptTracker(),
      }
    },
    finalize: state => observations.enqueueCritical(() => bridge.harnessFinalize({
      run_id: state.runId,
      session_id: state.sessionId,
    }).then(() => undefined)),
    onError: error => warnBridge(ctx, config, error),
  })

  function ensureRun(agent: Agent, source = 'runtime'): Promise<RunState> {
    return lifecycle.ensure(agent, source)
  }

  function enqueueEvent(
    state: RunState,
    eventType: string,
    payload: JsonObject,
    identity: unknown,
    timestamp = new Date().toISOString(),
  ): void {
    const sequence = state.observationSequence + 1
    const params: HarnessEventParams = {
      run_id: state.runId,
      session_id: state.sessionId,
      idempotency_key: stableEventKey(state.sessionId, eventType, identity),
      event_type: eventType,
      sequence,
      timestamp,
      payload,
    }
    const accepted = observations.enqueue(() => bridge.harnessEvent(params).then(() => undefined))
    if (accepted) {
      state.observationSequence = sequence
    } else {
      ctx.logger.warn(
        `PromptControlLab observation queue full; dropped ${observations.dropped} event(s)`,
      )
    }
  }

  /** Create the local run as soon as the Harness session starts. */
  ctx.on('agent/session-start', ({ agent, source }) => {
    void ensureRun(agent, source).catch(error => warnBridge(ctx, config, error))
  })

  /** Gate the final downstream message batch before any model request. */
  ctx.on('agent/pre-step', async (
    { agent, messages, turn, step, signal },
    next,
  ): Promise<PreStepDecision> => gateFinalPreStep({
    mode: config.mode,
    step,
    proposedMessages: messages,
    signal,
    feedbackMaxChars: config.feedbackMaxChars,
    next,
    inspect: async (prompt, gateSignal) => {
      if (gateSignal.aborted) throw gateSignal.reason
      const state = await settleWithAbort(ensureRun(agent), gateSignal)
      if (gateSignal.aborted) throw gateSignal.reason
      return bridge.harnessPreStep({
        run_id: state.runId,
        session_id: state.sessionId,
        turn,
        step,
        prompt,
        prompt_hash: stableJsonDigest(prompt),
        policy_path: config.policyPath ?? null,
        feedback_max_chars: config.feedbackMaxChars,
      }, gateSignal)
    },
    withFeedback: (messages, feedback) => [...messages, feedbackMessage(feedback)],
    onBridgeError: error => warnBridge(ctx, config, error),
  }))

  /** Record public provider and model request metadata after downstream resolution. */
  ctx.on('agent/request', async ({ agent, turn, step }, next) => {
    const request = await next()
    void ensureRun(agent).then(state => {
      const attempt = state.retryAttempts.next('agent/request', turn, step)
      const requestId = stableEventKey(state.sessionId, 'agent/request', [turn, step, attempt])
      enqueueEvent(state, 'agent/request', {
        turn,
        step,
        attempt,
        request_id: requestId,
        request_id_source: 'prompt_control_lab',
        provider: request.provider,
        model: request.model,
        max_tokens: request.maxTokens ?? null,
        temperature: request.temperature ?? null,
      }, [turn, step, attempt, request.provider, request.model])
    }).catch(error => warnBridge(ctx, config, error))
    return request
  })

  /** Record redacted provider failures and retry context. */
  ctx.on('agent/request-error', async (
    { agent, turn, step, provider, failure, retryPolicy },
    next,
  ): Promise<RequestErrorAction> => {
    const failureMetadata = safeRequestFailure(failure)
    void ensureRun(agent).then(state => {
      const attempt = state.retryAttempts.next('agent/request-error', turn, step)
      enqueueEvent(state, 'agent/request-error', {
        turn,
        step,
        attempt,
        provider,
        failure: failureMetadata,
        retry_policy_present: retryPolicy !== undefined,
      }, [turn, step, attempt, provider, failureMetadata])
    }).catch(error => warnBridge(ctx, config, error))
    return next()
  })

  /** Enforce allow, ask, or deny policy before a tool executes. */
  ctx.on('tools/pre-execute', async (exec, next): Promise<PreToolDecision> => {
    if (!exec.agent) return next()
    try {
      const state = await settleWithAbort(ensureRun(exec.agent), exec.signal)
      const tool = safeToolMetadata(exec)
      const result = await bridge.harnessToolPreExecute({
        run_id: state.runId,
        session_id: state.sessionId,
        event_id: stableEventKey(state.sessionId, 'tools/pre-execute', tool),
        tool,
        policy_path: config.policyPath ?? null,
      }, exec.signal)
      const action = toolGateAction(config.mode, result.decision, true)
      if (action === 'deny') {
        return { kind: 'deny', reason: boundedReason(result.reason, config) }
      }
      if (action === 'ask') {
        return { kind: 'ask', reason: boundedReason(result.reason, config) }
      }
      return next()
    } catch (error) {
      if (exec.signal.aborted) return { kind: 'deny', reason: 'Tool call cancelled.' }
      warnBridge(ctx, config, error)
      if (toolGateAction(config.mode, 'allow', false) === 'deny') {
        return { kind: 'deny', reason: 'PromptControlLab bridge unavailable in gate mode.' }
      }
      return next()
    }
  })

  /** Observe a completed tool call after downstream post-execute listeners. */
  ctx.on('tools/post-execute', async (
    exec,
    result,
    next,
  ): Promise<PostToolDecision> => {
    const downstream = await next()
    observeTool(ctx, config, ensureRun, enqueueEvent, exec, result, 'tools/post-execute')
    return downstream
  })

  /** Persist final tool-result metadata as an immutable observation. */
  ctx.on('tools/result', (exec, result) => {
    observeTool(ctx, config, ensureRun, enqueueEvent, exec, result, 'tools/result')
  })

  /** Convert durable session events into ordered control observations. */
  ctx.on('session/event', (session, event: SessionEvent) => {
    if (!shouldObserveSessionEvent(event.type)) return
    const payload = safeSessionEvent(event)
    const observe = (state: RunState): void => {
      enqueueEvent(
        state,
        `session/${event.type}`,
        payload,
        event.seq,
        new Date(event.time).toISOString(),
      )
      if (event.type === 'turn/end') {
        void observations.enqueueCritical(() => bridge.harnessTurnEnd({
            run_id: state.runId,
            session_id: state.sessionId,
            turn: event.data.turn,
            reason: event.data.reason as unknown as JsonObject,
            feedback_max_chars: config.feedbackMaxChars,
          }).then(result => { state.lastTurnDecision = result }))
          .catch(() => undefined)
      }
    }
    const sessionId = String(session.id)
    const state = lifecycle.current(sessionId)
    if (state) observe(state)
    else void lifecycle.whenAvailable(sessionId)?.then(observe)
      .catch(error => warnBridge(ctx, config, error))
  })

  if (config.autoRecover && config.maxAutoRecoveries > 0) {
    /** Apply bounded recovery guidance only when automatic recovery is enabled. */
    ctx.on('agent/turn-stopping', async ({ agent, turn }) => {
      try {
        const state = await ensureRun(agent)
        if (state.recoveryCount >= config.maxAutoRecoveries) return
        const decision = await bridge.harnessTurnEnd({
          run_id: state.runId,
          session_id: state.sessionId,
          turn,
          reason: { kind: 'turn-stopping' },
          feedback_max_chars: config.feedbackMaxChars,
        })
        state.lastTurnDecision = decision
        if (!decision.recover) return
        const recommendation = boundedText(decision.recommendation, config.feedbackMaxChars)
        if (!recommendation) return
        state.recoveryCount += 1
        agent.steer(feedbackMessage(recommendation))
      } catch (error) {
        warnBridge(ctx, config, error)
      }
    })
  }

  /** Finalize the ControlRun when its Harness agent is disposed. */
  ctx.on('agent/disposed', ({ agent }) => {
    void lifecycle.dispose(agent)
  })

  if (config.exposeStatusTool) registerStatusTool(ctx, bridge, ensureRun)

  ctx.effect(() => async () => {
    await lifecycle.disposeAll()
    await observations.flush()
    await bridge.close()
  }, 'prompt-control-lab bridge teardown')
}

function observeTool(
  ctx: Context,
  config: ResolvedConfig,
  ensureRun: (agent: Agent, source?: string) => Promise<RunState>,
  enqueueEvent: (
    state: RunState,
    eventType: string,
    payload: JsonObject,
    identity: unknown,
    timestamp?: string,
  ) => void,
  exec: Readonly<ToolExecution>,
  result: Readonly<ToolExecutionResult>,
  eventType: string,
): void {
  if (!exec.agent) return
  const tool = safeToolMetadata(exec)
  const resultMetadata = safeToolResult(result)
  void ensureRun(exec.agent).then(state => enqueueEvent(
    state,
    eventType,
    { tool, result: resultMetadata },
    [tool.call_id ?? null, eventType, resultMetadata],
  )).catch(error => warnBridge(ctx, config, error))
}

function registerStatusTool(
  ctx: Context,
  bridge: HarnessBridge,
  ensureRun: (agent: Agent, source?: string) => Promise<RunState>,
): void {
  ctx.tools.register(defineTool({
    name: 'pcl_status',
    description: 'Read the current local PromptControlLab control status. This tool changes no state.',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(_args, exec) {
      if (!exec.agent) return JSON.stringify({ status: 'unavailable', reason: 'no agent context' })
      const state = await ensureRun(exec.agent)
      const status = await bridge.harnessStatus({
        run_id: state.runId,
        session_id: state.sessionId,
      })
      return JSON.stringify(status)
    },
  }))
}

function feedbackMessage(text: string): UserMessage {
  return createUserMessage({
    content: [{ type: 'text', text }],
    source: { ...PLUGIN_SOURCE, summary: 'PromptControlLab suggestion' },
  })
}

function boundedReason(reason: string, config: ResolvedConfig): string {
  return boundedText(reason || 'Denied by PromptControlLab policy.', config.feedbackMaxChars)
}

function warnBridge(ctx: Context, config: ResolvedConfig, error: unknown): void {
  const disposition = config.mode === 'gate' ? 'blocking gated work' : 'continuing in suggest mode'
  ctx.logger.warn(
    `PromptControlLab bridge unavailable; ${disposition}: ${bridgeFailureCategory(error)}`,
  )
}
