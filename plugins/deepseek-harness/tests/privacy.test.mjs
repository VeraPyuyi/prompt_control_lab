import assert from 'node:assert/strict'
import test from 'node:test'
import * as privacy from '../src/privacy.ts'

const {
  extractPromptText,
  safeSessionEvent,
  safeToolMetadata,
  safeToolResult,
  sha256,
  stableJsonDigest,
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
  assert.equal(
    stableJsonDigest(prompt),
    'sha256:687b796614f94d79aab47cc50a5d2ed96653f87f9839d91a7ee55d5239373177',
  )
  const protocolFixtures = [
    ['\u4fee\u590d\u8ba4\u8bc1', 'sha256:189dbbc52d7e7a94c095837bca08dc8463c591f4f874aedacd4b59f6c8d89e16'],
    ['Say "hello"', 'sha256:d060b35451d1c6a34cd16c0de63268262830fa2c4894544b58f03059c2e4e8f5'],
    [String.raw`C:\repo\file.py`, 'sha256:6822c37ea61f4fb07263e5f91c759c15204b05f2f9c44c076ac4543261f0b060'],
    ['line one\nline two', 'sha256:fe7ce060245a7cf48259f349043911673196ca36b3202195ee79d85bac454fc0'],
  ]
  for (const [value, expected] of protocolFixtures) {
    assert.equal(stableJsonDigest(value), expected)
  }
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
    value: {
      kind: 'foreground',
      exitCode: 0,
      stdout: { text: 'secret stdout' },
      stderr: { text: 'secret stderr' },
    },
    content: [{ type: 'text', text: 'secret output' }],
  })
  const serialized = JSON.stringify({ tool, result })
  assert.equal(tool.argument_keys.join(','), 'api_key,path')
  assert.equal(tool.operation_category, 'file_write')
  assert.match(tool.argument_hash, /^sha256:/)
  assert.equal(result.content_block_count, 1)
  assert.equal(result.exit_code, 0)
  assert.doesNotMatch(serialized, /sk-super-secret|secret output|secret stdout|secret stderr/)
})

test('tool result projection preserves a bounded nonzero exit status', () => {
  const result = safeToolResult({
    isError: false,
    value: { kind: 'foreground', exitCode: 2, stdout: { text: 'private output' } },
    content: [{ type: 'text', text: 'private rendered output' }],
  })
  assert.equal(result.exit_code, 2)
  assert.doesNotMatch(JSON.stringify(result), /private output|private rendered output/)
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
      message: {
        id: 'assistant-message-1',
        source: { kind: 'model', provider: 'deepseek', model: 'deepseek-chat' },
        content: [{ type: 'reasoning', text: 'hidden chain' }],
      },
      usage: { inputTokens: 10, outputTokens: 4 },
    },
  })
  const serialized = JSON.stringify({ user, assistant })
  assert.deepEqual(user.harness_guard_signals, ['repeat_tool_reminder'])
  assert.equal(assistant.usage.input_tokens, 10)
  assert.equal(assistant.response_id, 'assistant-message-1')
  assert.equal(assistant.provider, 'deepseek')
  assert.equal(assistant.model, 'deepseek-chat')
  assert.doesNotMatch(serialized, /private prompt|hidden chain/)
})

test('tool projections classify test execution without persisting commands', () => {
  const tool = safeToolMetadata({
    callId: 'call-2',
    name: 'bash',
    arguments: { command: 'pytest tests/test_auth.py -q' },
  })

  assert.equal(tool.operation_category, 'test_execution')
  assert.doesNotMatch(JSON.stringify(tool), /pytest|test_auth/)
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
