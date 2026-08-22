/** User-facing native plugin configuration. */

import z from '@deepseek-ai/schemastery'

export interface Config {
  mode?: 'suggest' | 'gate'
  policyPath?: string
  capture?: 'redacted'
  feedback?: 'summary'
  autoRecover?: boolean
  bridgeFailure?: 'warn' | 'block'
  runsRoot?: string
  feedbackMaxChars?: number
  observationQueueSize?: number
  bridgeTimeoutMs?: number
  exposeStatusTool?: boolean
  maxAutoRecoveries?: number
}

export interface ResolvedConfig {
  mode: 'suggest' | 'gate'
  policyPath?: string
  capture: 'redacted'
  feedback: 'summary'
  autoRecover: boolean
  bridgeFailure: 'warn' | 'block'
  runsRoot: string
  feedbackMaxChars: number
  observationQueueSize: number
  bridgeTimeoutMs: number
  exposeStatusTool: boolean
  maxAutoRecoveries: number
}

export const DEFAULT_CONFIG: ResolvedConfig = {
  mode: 'suggest',
  capture: 'redacted',
  feedback: 'summary',
  autoRecover: false,
  bridgeFailure: 'warn',
  runsRoot: '.promptcontrol/runs',
  feedbackMaxChars: 600,
  observationQueueSize: 256,
  bridgeTimeoutMs: 5_000,
  exposeStatusTool: false,
  maxAutoRecoveries: 1,
}

export const Config: z<Config> = z.object({
  mode: z.union(['suggest', 'gate'] as const).default('suggest'),
  policyPath: z.string(),
  capture: z.union(['redacted'] as const).default('redacted'),
  feedback: z.union(['summary'] as const).default('summary'),
  autoRecover: z.boolean().default(false),
  bridgeFailure: z.union(['warn', 'block'] as const).default('warn'),
  runsRoot: z.string().default('.promptcontrol/runs'),
  feedbackMaxChars: z.number().default(600),
  observationQueueSize: z.number().default(256),
  bridgeTimeoutMs: z.number().default(5_000),
  exposeStatusTool: z.boolean().default(false),
  maxAutoRecoveries: z.number().default(1),
})

export function resolveConfig(config: Config): ResolvedConfig {
  const resolved: ResolvedConfig = { ...DEFAULT_CONFIG, ...config }
  for (const [name, value] of [
    ['feedbackMaxChars', resolved.feedbackMaxChars],
    ['observationQueueSize', resolved.observationQueueSize],
    ['bridgeTimeoutMs', resolved.bridgeTimeoutMs],
  ] as const) {
    if (!Number.isInteger(value) || value < 1) throw new Error(`${name} must be a positive integer`)
  }
  if (!Number.isInteger(resolved.maxAutoRecoveries) || resolved.maxAutoRecoveries < 0) {
    throw new Error('maxAutoRecoveries must be a non-negative integer')
  }
  if (resolved.mode === 'gate' && resolved.bridgeFailure !== 'block') {
    resolved.bridgeFailure = 'block'
  }
  if (resolved.mode === 'suggest') resolved.bridgeFailure = 'warn'
  return resolved
}
