/** Pure gate semantics shared by the native listeners and contract tests. */

import { boundedText, extractPromptText } from './privacy.ts'

export type ControlMode = 'suggest' | 'gate'
export type PreStepAction = 'delegate' | 'reject'
export type ToolGateAction = 'delegate' | 'ask' | 'deny'

export type FinalPreStepDecision<T> =
  | { kind: 'reject' }
  | { kind: 'enter'; messages: T[] }

export interface PreStepInspection {
  decision: 'allow' | 'suggest' | 'deny'
  risk_level: 'low' | 'medium' | 'high' | 'unknown'
  summary: string
  feedback: string | null
}

export interface FinalPreStepGate<T extends { content?: unknown }> {
  mode: ControlMode
  step: number
  proposedMessages: readonly T[]
  signal: AbortSignal
  feedbackMaxChars: number
  next: () => Promise<FinalPreStepDecision<T>>
  inspect: (prompt: string, signal: AbortSignal) => Promise<PreStepInspection>
  withFeedback: (messages: T[], feedback: string) => T[]
  onBridgeError: (error: unknown) => void
}

export function preStepAction(
  mode: ControlMode,
  decision: 'allow' | 'suggest' | 'deny',
  bridgeAvailable: boolean,
): PreStepAction {
  if (mode === 'suggest') return 'delegate'
  if (!bridgeAvailable || decision === 'deny') return 'reject'
  return 'delegate'
}

export function toolGateAction(
  mode: ControlMode,
  decision: 'allow' | 'ask' | 'deny',
  bridgeAvailable: boolean,
): ToolGateAction {
  if (mode === 'suggest') return 'delegate'
  if (!bridgeAvailable || decision === 'deny') return 'deny'
  if (decision === 'ask') return 'ask'
  return 'delegate'
}

/** Gate the exact message batch returned by downstream pre-step listeners. */
export async function gateFinalPreStep<T extends { content?: unknown }>(
  gate: FinalPreStepGate<T>,
): Promise<FinalPreStepDecision<T>> {
  const downstream = await gate.next()
  if (downstream.kind === 'reject' || gate.signal.aborted) return downstream

  const prompt = extractPromptText(downstream.messages)
  if (!prompt) {
    const explicitContinuation = gate.step > 1
      && gate.proposedMessages.length === 0
      && downstream.messages.length === 0
    return gate.mode === 'gate' && !explicitContinuation ? { kind: 'reject' } : downstream
  }

  try {
    const result = await gate.inspect(prompt, gate.signal)
    if (gate.signal.aborted) return downstream
    if (preStepAction(gate.mode, result.decision, true) === 'reject') {
      return { kind: 'reject' }
    }
    const feedback = boundedText(result.feedback, gate.feedbackMaxChars)
    if (!feedback) return downstream
    return {
      kind: 'enter',
      messages: gate.withFeedback(downstream.messages, feedback),
    }
  } catch (error) {
    if (gate.signal.aborted) return downstream
    gate.onBridgeError(error)
    if (preStepAction(gate.mode, 'allow', false) === 'reject') return { kind: 'reject' }
    return downstream
  }
}
