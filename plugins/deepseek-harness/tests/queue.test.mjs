import assert from 'node:assert/strict'
import test from 'node:test'
import { BoundedObservationQueue } from '../src/observation-queue.ts'

test('observation queue is bounded and preserves accepted order', async () => {
  const seen = []
  let release
  const blocker = new Promise(resolve => { release = resolve })
  const queue = new BoundedObservationQueue(2, async value => {
    if (value === 1) await blocker
    seen.push(value)
  })

  assert.equal(queue.enqueue(1), true)
  assert.equal(queue.enqueue(2), true)
  assert.equal(queue.enqueue(3), true)
  assert.equal(queue.enqueue(4), false)
  assert.equal(queue.dropped, 1)
  release()
  await queue.flush()
  assert.deepEqual(seen, [1, 2, 3])
})

test('worker failures are contained and later observations still run', async () => {
  const seen = []
  const errors = []
  const queue = new BoundedObservationQueue(
    4,
    async value => {
      if (value === 'bad') throw new Error('failed')
      seen.push(value)
    },
    error => errors.push(String(error)),
  )
  queue.enqueue('bad')
  queue.enqueue('good')
  await queue.flush()
  assert.equal(errors.length, 1)
  assert.deepEqual(seen, ['good'])
})

test('critical work is admitted when the observation capacity is full', async () => {
  const seen = []
  let release
  const blocker = new Promise(resolve => { release = resolve })
  const queue = new BoundedObservationQueue(1, async value => {
    if (value === 'active') await blocker
    seen.push(value)
  })

  assert.equal(queue.enqueue('active'), true)
  assert.equal(queue.enqueue('observation'), true)
  assert.equal(queue.enqueue('dropped'), false)
  assert.equal(typeof queue.enqueueCritical, 'function')
  const critical = queue.enqueueCritical('turn-end')
  release()

  await critical
  await queue.flush()
  assert.deepEqual(seen, ['active', 'observation', 'turn-end'])
})

test('critical worker failures reject their caller and do not stop the queue', async () => {
  assert.equal(typeof BoundedObservationQueue.prototype.enqueueCritical, 'function')
  const seen = []
  const errors = []
  const queue = new BoundedObservationQueue(
    1,
    async value => {
      if (value === 'critical') throw new Error('failed')
      seen.push(value)
    },
    error => errors.push(String(error)),
  )

  const critical = queue.enqueueCritical('critical')
  queue.enqueue('later')
  await assert.rejects(critical, /failed/)
  await queue.flush()
  assert.equal(errors.length, 1)
  assert.deepEqual(seen, ['later'])
})
