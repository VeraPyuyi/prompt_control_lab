/** A single-writer bounded queue for non-gating observations. */

interface QueueItem<T> {
  value: T
  resolve?: () => void
  reject?: (error: unknown) => void
}

/** Serialize bounded observations while preserving critical lifecycle writes. */
export class BoundedObservationQueue<T> {
  readonly capacity: number
  dropped = 0
  private readonly items: Array<QueueItem<T>> = []
  private readonly worker: (item: T) => Promise<void>
  private readonly onError: (error: unknown) => void
  private pendingObservations = 0
  private active = false
  private waiters: Array<() => void> = []

  constructor(
    capacity: number,
    worker: (item: T) => Promise<void>,
    onError: (error: unknown) => void = () => undefined,
  ) {
    if (!Number.isInteger(capacity) || capacity < 1) {
      throw new Error('observation queue capacity must be a positive integer')
    }
    this.capacity = capacity
    this.worker = worker
    this.onError = onError
  }

  /** Enqueue a best-effort observation unless the bounded capacity is full. */
  enqueue(item: T): boolean {
    if (this.pendingObservations >= this.capacity) {
      this.dropped += 1
      return false
    }
    this.pendingObservations += 1
    this.items.push({ value: item })
    if (!this.active) void this.drain()
    return true
  }

  /** Admit lifecycle work without allowing bounded observations to drop it. */
  enqueueCritical(item: T): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      this.items.push({ value: item, resolve, reject })
      if (!this.active) void this.drain()
    })
  }

  /** Wait until all currently queued work has completed. */
  async flush(): Promise<void> {
    if (!this.active && this.items.length === 0) return
    await new Promise<void>(resolve => this.waiters.push(resolve))
  }

  private async drain(): Promise<void> {
    this.active = true
    while (this.items.length > 0) {
      const item = this.items.shift()
      if (item === undefined) continue
      if (!item.resolve) this.pendingObservations -= 1
      try {
        await this.worker(item.value)
        item.resolve?.()
      } catch (error) {
        this.onError(error)
        item.reject?.(error)
      }
    }
    this.active = false
    const waiters = this.waiters
    this.waiters = []
    for (const resolve of waiters) resolve()
  }
}
