import assert from 'node:assert/strict'
import test from 'node:test'
import * as decisions from '../src/decisions.ts'

const { preStepAction, toolGateAction } = decisions

test('pre-step is fail-open in suggest and fail-closed in gate', () => {
  assert.equal(preStepAction('suggest', 'deny', true), 'delegate')
  assert.equal(preStepAction('suggest', 'allow', false), 'delegate')
  assert.equal(preStepAction('gate', 'deny', true), 'reject')
  assert.equal(preStepAction('gate', 'allow', false), 'reject')
  assert.equal(preStepAction('gate', 'allow', true), 'delegate')
})

test('tool gate prevents execution only in gate mode', () => {
  assert.equal(toolGateAction('suggest', 'deny', true), 'delegate')
  assert.equal(toolGateAction('suggest', 'allow', false), 'delegate')
  assert.equal(toolGateAction('gate', 'deny', true), 'deny')
  assert.equal(toolGateAction('gate', 'ask', true), 'ask')
  assert.equal(toolGateAction('gate', 'allow', false), 'deny')
  assert.equal(toolGateAction('gate', 'allow', true), 'delegate')
})

test('pre-step gates the final downstream messages and delegates exactly once', async () => {
  assert.equal(typeof decisions.gateFinalPreStep, 'function')
  let nextCalls = 0
  let inspected = ''
  const initial = message('initial prompt')
  const final = message('downstream replacement')

  const result = await decisions.gateFinalPreStep({
    mode: 'gate',
    step: 1,
    proposedMessages: [initial],
    signal: new AbortController().signal,
    feedbackMaxChars: 100,
    next: async () => {
      nextCalls += 1
      return { kind: 'enter', messages: [final] }
    },
    inspect: async prompt => {
      inspected = prompt
      return {
        decision: 'suggest',
        risk_level: 'low',
        summary: 'ok',
        feedback: 'bounded feedback',
      }
    },
    withFeedback: (messages, feedback) => [...messages, message(feedback)],
    onBridgeError: assert.fail,
  })

  assert.equal(nextCalls, 1)
  assert.equal(inspected, 'downstream replacement')
  assert.deepEqual(result, {
    kind: 'enter',
    messages: [final, message('bounded feedback')],
  })
  assert.notEqual(inspected, initial.content[0].text)
})

test('gate rejects uninspectable input except an explicit empty continuation', async () => {
  assert.equal(typeof decisions.gateFinalPreStep, 'function')
  let inspections = 0
  const run = (step, messages, proposedMessages = messages) => decisions.gateFinalPreStep({
    mode: 'gate',
    step,
    proposedMessages,
    signal: new AbortController().signal,
    feedbackMaxChars: 100,
    next: async () => ({ kind: 'enter', messages }),
    inspect: async () => {
      inspections += 1
      throw new Error('uninspectable input must not reach the bridge')
    },
    withFeedback: current => current,
    onBridgeError: assert.fail,
  })

  assert.deepEqual(await run(1, []), { kind: 'reject' })
  assert.deepEqual(await run(1, [message('  \n  ')]), { kind: 'reject' })
  assert.deepEqual(await run(2, [{ content: [{ type: 'image', url: 'opaque' }] }]), {
    kind: 'reject',
  })
  assert.deepEqual(await run(2, [], [message('downstream erased this')]), { kind: 'reject' })
  assert.deepEqual(await run(2, []), { kind: 'enter', messages: [] })
  assert.equal(inspections, 0)
})

test('pre-step bridge failure never calls downstream twice', async () => {
  assert.equal(typeof decisions.gateFinalPreStep, 'function')
  let nextCalls = 0
  let failures = 0
  const result = await decisions.gateFinalPreStep({
    mode: 'suggest',
    step: 1,
    proposedMessages: [message('inspect me')],
    signal: new AbortController().signal,
    feedbackMaxChars: 100,
    next: async () => {
      nextCalls += 1
      return { kind: 'enter', messages: [message('inspect me')] }
    },
    inspect: async () => { throw new Error('bridge unavailable') },
    withFeedback: current => current,
    onBridgeError: () => { failures += 1 },
  })

  assert.equal(nextCalls, 1)
  assert.equal(failures, 1)
  assert.equal(result.kind, 'enter')
})

function message(text) {
  return { content: [{ type: 'text', text }] }
}
