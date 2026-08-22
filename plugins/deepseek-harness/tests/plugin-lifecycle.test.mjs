import assert from 'node:assert/strict'
import test from 'node:test'
import { JsonRpcBridgeClient } from '../src/bridge.ts'
import { apply } from '../src/index.ts'

test('autoRecover intent is transmitted and automatic steering stays bounded', async () => {
  const originalCall = JsonRpcBridgeClient.prototype.call
  const calls = []
  let notifyStarted
  const started = new Promise(resolve => { notifyStarted = resolve })
  let cleanup = async () => {}
  const handlers = new Map()
  const warnings = []
  const ctx = {
    logger: { warn: message => warnings.push(message) },
    tools: { register: () => {} },
    on: (event, handler) => { handlers.set(event, handler) },
    effect: setup => { cleanup = setup() },
  }

  JsonRpcBridgeClient.prototype.call = async function (method, params) {
    calls.push({ method, params })
    if (method === 'harness_session_start') {
      notifyStarted()
      return { run_id: 'run-1', status: 'initialized' }
    }
    if (method === 'harness_turn_end') {
      return { stability: 'stalled', recommendation: 'Use the bounded recovery.', recover: true }
    }
    if (method === 'harness_finalize') {
      return { run_id: 'run-1', status: 'finalized', report_path: null }
    }
    throw new Error(`unexpected bridge method: ${method}`)
  }

  try {
    apply(ctx, {
      autoRecover: true,
      maxAutoRecoveries: 1,
      runsRoot: 'runs',
    })
    const steers = []
    const agent = {
      id: 'session-1',
      options: {},
      steer: message => { steers.push(message) },
    }
    handlers.get('agent/session-start')({ agent, source: 'resume' })
    await started

    const start = calls.find(call => call.method === 'harness_session_start')
    assert.equal(start.params.auto_recover, true)
    assert.equal(start.params.max_auto_recoveries, 1)

    await handlers.get('agent/turn-stopping')({ agent, turn: 1 })
    await handlers.get('agent/turn-stopping')({ agent, turn: 2 })
    assert.equal(calls.filter(call => call.method === 'harness_turn_end').length, 1)
    assert.equal(steers.length, 1)
    assert.deepEqual(warnings, [])
  } finally {
    await cleanup()
    JsonRpcBridgeClient.prototype.call = originalCall
  }
})
