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

test('a failed finalization is reported before a later run starts fresh', async () => {
  const lifecycleModule = await import('../src/run-lifecycle.ts').catch(() => ({}))
  assert.equal(typeof lifecycleModule.SessionRunLifecycle, 'function')

  let starts = 0
  const errors = []
  const lifecycle = new lifecycleModule.SessionRunLifecycle({
    idOf: agent => agent.id,
    start: async () => ({ id: `run-${++starts}` }),
    finalize: async () => { throw new Error('finalize failed') },
    onError: error => errors.push(String(error)),
  })
  const agent = { id: 'session-1' }
  const first = await lifecycle.ensure(agent, 'startup')

  await lifecycle.dispose(agent)
  assert.equal(lifecycle.current(agent.id), undefined)
  const second = await lifecycle.ensure(agent, 'resume')
  assert.notEqual(second, first)
  assert.equal(second.id, 'run-2')
  assert.equal(errors.length, 1)
})
