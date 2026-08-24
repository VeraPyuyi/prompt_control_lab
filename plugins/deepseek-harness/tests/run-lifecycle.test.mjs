import assert from 'node:assert/strict'
import test from 'node:test'

test('dispose finalizes before removal and a resume starts a fresh run', async () => {
  const lifecycleModule = await import('../src/run-lifecycle.ts').catch(() => ({}))
  assert.equal(typeof lifecycleModule.SessionRunLifecycle, 'function')

  let starts = 0
  let finalizes = 0
  let releaseFinalize
  const finalizeBlocker = new Promise(resolve => { releaseFinalize = resolve })
  const errors = []
  const lifecycle = new lifecycleModule.SessionRunLifecycle({
    idOf: agent => agent.id,
    start: async (_agent, source) => ({ id: `run-${++starts}`, source }),
    finalize: async () => {
      finalizes += 1
      await finalizeBlocker
    },
    onError: error => errors.push(error),
  })
  const agent = { id: 'session-1' }
  const first = await lifecycle.ensure(agent, 'startup')

  const disposing = lifecycle.dispose(agent)
  await Promise.resolve()
  assert.equal(lifecycle.current(agent.id), first)
  const resumed = lifecycle.ensure(agent, 'resume')
  await Promise.resolve()
  assert.equal(starts, 1)
  assert.equal(finalizes, 1)

  releaseFinalize()
  await disposing
  const second = await resumed
  assert.equal(second.id, 'run-2')
  assert.equal(second.source, 'resume')
  assert.notEqual(second, first)
  assert.equal(lifecycle.current(agent.id), second)
  assert.deepEqual(errors, [])
})

test('a failed finalization is reported, retained, and retried before a fresh run', async () => {
  const lifecycleModule = await import('../src/run-lifecycle.ts').catch(() => ({}))
  assert.equal(typeof lifecycleModule.SessionRunLifecycle, 'function')

  let starts = 0
  let finalizes = 0
  const errors = []
  const lifecycle = new lifecycleModule.SessionRunLifecycle({
    idOf: agent => agent.id,
    start: async () => ({ id: `run-${++starts}` }),
    finalize: async () => {
      finalizes += 1
      if (finalizes === 1) throw new Error('finalize failed')
    },
    onError: error => errors.push(String(error)),
  })
  const agent = { id: 'session-1' }
  const first = await lifecycle.ensure(agent, 'startup')

  await assert.rejects(lifecycle.dispose(agent), /finalize failed/)
  assert.equal(lifecycle.current(agent.id), first)
  assert.equal(await lifecycle.ensure(agent, 'resume'), first)

  await lifecycle.dispose(agent)
  assert.equal(lifecycle.current(agent.id), undefined)
  const second = await lifecycle.ensure(agent, 'fresh')
  assert.notEqual(second, first)
  assert.equal(second.id, 'run-2')
  assert.equal(errors.length, 1)
  assert.equal(finalizes, 2)
})

test('disposeAll finalizes active runs before plugin shutdown', async () => {
  const lifecycleModule = await import('../src/run-lifecycle.ts').catch(() => ({}))
  assert.equal(typeof lifecycleModule.SessionRunLifecycle, 'function')

  const finalized = []
  const lifecycle = new lifecycleModule.SessionRunLifecycle({
    idOf: agent => agent.id,
    start: async agent => ({ id: agent.id }),
    finalize: async state => { finalized.push(state.id) },
    onError: error => { throw error },
  })
  const first = { id: 'session-1' }
  const second = { id: 'session-2' }
  await Promise.all([
    lifecycle.ensure(first, 'startup'),
    lifecycle.ensure(second, 'startup'),
  ])

  await lifecycle.disposeAll()

  assert.deepEqual(finalized.sort(), ['session-1', 'session-2'])
  assert.equal(lifecycle.current(first.id), undefined)
  assert.equal(lifecycle.current(second.id), undefined)
})
