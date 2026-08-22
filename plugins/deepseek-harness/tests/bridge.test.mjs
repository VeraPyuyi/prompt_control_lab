import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import * as bridgeModule from '../src/bridge.ts'

const { HarnessBridge, JsonRpcBridgeClient } = bridgeModule

const fakeBridge = fileURLToPath(new URL('./fake-bridge.mjs', import.meta.url))

test('one bridge process serves repeated JSON-RPC calls', async () => {
  const client = new JsonRpcBridgeClient({
    runsRoot: 'runs',
    timeoutMs: 2_000,
    command: [process.execPath, fakeBridge],
  })
  const bridge = new HarnessBridge(client)
  try {
    const first = await bridge.health()
    const second = await bridge.health()
    assert.equal(first.status, 'ok')
    assert.equal(first.pid, second.pid)
    assert.equal(first.pid, client.pid)
  } finally {
    await bridge.close()
  }
})

test('Harness bridge wrappers use the versioned method names', async () => {
  const client = new JsonRpcBridgeClient({
    runsRoot: 'runs',
    timeoutMs: 2_000,
    command: [process.execPath, fakeBridge],
  })
  const bridge = new HarnessBridge(client)
  try {
    const status = await bridge.harnessStatus({ run_id: 'run-1', session_id: 'session-1' })
    assert.equal(status.method, 'harness_status')
    const event = await bridge.harnessEvent({
      run_id: 'run-1',
      session_id: 'session-1',
      idempotency_key: 'event-1',
      event_type: 'session/turn/end',
      sequence: 1,
      timestamp: '2026-01-01T00:00:00.000Z',
      payload: {},
    })
    assert.equal(event.method, 'harness_event')
  } finally {
    await bridge.close()
  }
})

test('typed bridge wrappers reject malformed responses', async () => {
  const calls = [
    ['harness_session_start', bridge => bridge.harnessSessionStart({
      session_id: 'session-1',
      source: 'test',
      mode: 'gate',
      authorization: 'agent-scoped',
      policy_path: null,
      capture: 'redacted',
      auto_recover: false,
      max_auto_recoveries: 1,
      provider: null,
      model: null,
      runs_root: 'runs',
      harness_version: '0.1.1-rc.2',
      harness_commit: 'test',
    })],
    ['harness_pre_step', bridge => bridge.harnessPreStep({
      run_id: 'run-1',
      session_id: 'session-1',
      turn: 1,
      step: 1,
      prompt: 'ephemeral prompt',
      prompt_hash: 'sha256:test',
      policy_path: null,
      feedback_max_chars: 100,
    })],
    ['harness_tool_pre_execute', bridge => bridge.harnessToolPreExecute({
      run_id: 'run-1',
      session_id: 'session-1',
      event_id: 'event-1',
      tool: {},
      policy_path: null,
    })],
    ['harness_event', bridge => bridge.harnessEvent({
      run_id: 'run-1',
      session_id: 'session-1',
      idempotency_key: 'event-1',
      event_type: 'session/turn/end',
      sequence: 1,
      timestamp: '2026-01-01T00:00:00.000Z',
      payload: {},
    })],
    ['harness_turn_end', bridge => bridge.harnessTurnEnd({
      run_id: 'run-1',
      session_id: 'session-1',
      turn: 1,
      reason: {},
      feedback_max_chars: 100,
    })],
    ['harness_status', bridge => bridge.harnessStatus({
      run_id: 'run-1',
      session_id: 'session-1',
    })],
    ['harness_finalize', bridge => bridge.harnessFinalize({
      run_id: 'run-1',
      session_id: 'session-1',
    })],
  ]

  for (const [method, invoke] of calls) {
    const client = new JsonRpcBridgeClient({
      runsRoot: 'runs',
      timeoutMs: 2_000,
      command: [process.execPath, fakeBridge],
      env: { INVALID_METHOD: method },
    })
    const bridge = new HarnessBridge(client)
    try {
      await assert.rejects(invoke(bridge), new RegExp(`malformed ${method} response`))
    } finally {
      await bridge.close()
    }
  }
})

test('JSON-RPC error text is replaced by a bounded category', async () => {
  const secret = `rpc-secret-${'x'.repeat(4_000)}`
  const client = new JsonRpcBridgeClient({
    runsRoot: 'runs',
    timeoutMs: 2_000,
    command: [process.execPath, fakeBridge],
    env: { RPC_ERROR_MESSAGE: secret },
  })
  try {
    await assert.rejects(client.call('health', {}), error => {
      assert.equal(error.category, 'remote-error')
      assert.equal(bridgeModule.bridgeFailureCategory(error), 'remote-error')
      assert.ok(error.message.length < 100)
      assert.doesNotMatch(error.message, /rpc-secret|xxxx/)
      return true
    })
  } finally {
    await client.close()
  }
})

test('child stderr is never copied into a bridge failure', async () => {
  const secret = `stderr-secret-${'y'.repeat(4_000)}`
  const client = new JsonRpcBridgeClient({
    runsRoot: 'runs',
    timeoutMs: 2_000,
    command: [process.execPath, fakeBridge],
    env: { EXIT_STDERR: secret },
  })
  try {
    await assert.rejects(client.call('health', {}), error => {
      assert.equal(error.category, 'process-exit')
      assert.equal(bridgeModule.bridgeFailureCategory(error), 'process-exit')
      assert.ok(error.message.length < 100)
      assert.doesNotMatch(error.message, /stderr-secret|yyyy/)
      return true
    })
  } finally {
    await client.close()
  }
})

test('unknown failures collapse to a fixed diagnostic category', () => {
  assert.equal(typeof bridgeModule.bridgeFailureCategory, 'function')
  assert.equal(bridgeModule.bridgeFailureCategory(new Error('api-key=secret')), 'unexpected')
  assert.equal(bridgeModule.bridgeFailureCategory('raw failure'), 'unexpected')
})

test('an AbortSignal promptly cancels an in-flight bridge call', async () => {
  const client = new JsonRpcBridgeClient({
    runsRoot: 'runs',
    timeoutMs: 500,
    command: [process.execPath, fakeBridge],
    env: { HOLD_REQUEST: '1' },
  })
  const controller = new AbortController()
  const reason = new Error('harness cancelled')
  const started = Date.now()
  try {
    const pending = client.call('health', {}, controller.signal)
    setTimeout(() => controller.abort(reason), 20)
    await assert.rejects(pending, error => error === reason)
    assert.ok(Date.now() - started < 250)
  } finally {
    await client.close()
  }
})

test('waiting for a shared session start honors cancellation', async () => {
  assert.equal(typeof bridgeModule.settleWithAbort, 'function')
  const controller = new AbortController()
  const reason = new Error('turn cancelled')
  const work = new Promise(() => {})
  const waiting = bridgeModule.settleWithAbort(work, controller.signal)
  controller.abort(reason)
  await assert.rejects(waiting, error => error === reason)
})
