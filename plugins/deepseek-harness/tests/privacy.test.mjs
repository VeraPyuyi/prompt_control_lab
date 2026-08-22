import assert from 'node:assert/strict'
import test from 'node:test'
import * as privacy from '../src/privacy.ts'

const {
  extractPromptText,
  safeSessionEvent,
  safeToolMetadata,
  safeToolResult,
  sha256,
} = privacy

test('prompt extraction is ephemeral and hashing is deterministic', () => {
  const prompt = extractPromptText([{
    content: [
      { type: 'text', text: 'Fix auth' },
      { type: 'reasoning', text: 'private thought' },
    ],
  }])
  assert.equal(prompt, 'Fix auth')
  assert.match(sha256(prompt), /^sha256:[0-9a-f]{64}$/)
})

test('tool projections contain hashes and status, never raw values', () => {
  const tool = safeToolMetadata({
    callId: 'call-1',
    rootCallId: 'call-1',
    name: 'write',
    arguments: { api_key: 'sk-super-secret', path: 'auth/session.py' },
  })
  const result = safeToolResult({
    isError: false,
    content: [{ type: 'text', text: 'secret output' }],
  })
  const serialized = JSON.stringify({ tool, result })
  assert.equal(tool.argument_keys.join(','), 'api_key,path')
  assert.match(tool.argument_hash, /^sha256:/)
  assert.equal(result.content_block_count, 1)
  assert.doesNotMatch(serialized, /sk-super-secret|secret output/)
})

test('session projection drops prompt, assistant text, and hidden reasoning', () => {
  const user = safeSessionEvent({
    type: 'user/message',
    seq: 4,
    time: 1_700_000_000_000,
    data: {
      content: [{ type: 'text', text: 'private prompt' }],
      source: { kind: 'plugin', plugin: 'repeat-tool-reminder' },
    },
  })
  const assistant = safeSessionEvent({
    type: 'assistant/message',
    seq: 5,
    time: 1_700_000_000_001,
    data: {
      message: { content: [{ type: 'reasoning', text: 'hidden chain' }] },
      usage: { inputTokens: 10, outputTokens: 4 },
    },
  })
  const serialized = JSON.stringify({ user, assistant })
  assert.deepEqual(user.harness_guard_signals, ['repeat_tool_reminder'])
  assert.equal(assistant.usage.input_tokens, 10)
  assert.doesNotMatch(serialized, /private prompt|hidden chain/)
})

test('token-level session events are filtered before observation', () => {
  assert.equal(typeof privacy.shouldObserveSessionEvent, 'function')
  assert.equal(privacy.shouldObserveSessionEvent('assistant/chunk'), false)
  assert.equal(privacy.shouldObserveSessionEvent('assistant/message'), true)
  assert.equal(privacy.shouldObserveSessionEvent('turn/end'), true)
})

test('retry attempts are distinct within a run and deterministic on replay', () => {
  assert.equal(typeof privacy.RetryAttemptTracker, 'function')
  const collect = () => {
    const tracker = new privacy.RetryAttemptTracker()
    return [
      ['agent/request', tracker.next('agent/request', 4, 2)],
      ['agent/request-error', tracker.next('agent/request-error', 4, 2)],
      ['agent/request', tracker.next('agent/request', 4, 2)],
      ['agent/request-error', tracker.next('agent/request-error', 4, 2)],
    ].map(([eventType, attempt]) => ({
      eventType,
      attempt,
      key: privacy.stableEventKey('session-1', eventType, [4, 2, attempt]),
    }))
  }

  const first = collect()
  const replay = collect()
  assert.deepEqual(first.map(item => item.attempt), [1, 1, 2, 2])
  assert.notEqual(first[0].key, first[2].key)
  assert.notEqual(first[1].key, first[3].key)
  assert.deepEqual(replay, first)
})
