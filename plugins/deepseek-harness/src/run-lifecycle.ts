/** Per-session run lifecycle with serialized finalization and resume. */

export interface SessionRunLifecycleOptions<Agent, State extends object> {
  idOf: (agent: Agent) => string
  start: (agent: Agent, source: string) => Promise<State>
  finalize: (state: State) => Promise<void>
  onError: (error: unknown) => void
}

/** Coordinate exactly one active ControlRun lifecycle per Harness session. */
export class SessionRunLifecycle<Agent, State extends object> {
  private readonly options: SessionRunLifecycleOptions<Agent, State>
  private readonly active = new Map<string, State>()
  private readonly starts = new Map<string, Promise<State>>()
  private readonly finalizations = new Map<string, Promise<void>>()

  constructor(options: SessionRunLifecycleOptions<Agent, State>) {
    this.options = options
  }

  /** Return the active run or serialize creation behind any finalization. */
  ensure(agent: Agent, source: string): Promise<State> {
    const sessionId = this.options.idOf(agent)
    const finalization = this.finalizations.get(sessionId)
    if (finalization) return finalization.then(() => this.ensure(agent, source))

    const current = this.active.get(sessionId)
    if (current) return Promise.resolve(current)
    const pending = this.starts.get(sessionId)
    if (pending) return pending

    let start: Promise<State>
    start = Promise.resolve()
      .then(() => this.options.start(agent, source))
      .then(
        state => {
          if (this.starts.get(sessionId) === start) this.starts.delete(sessionId)
          this.active.set(sessionId, state)
          return state
        },
        error => {
          if (this.starts.get(sessionId) === start) this.starts.delete(sessionId)
          throw error
        },
      )
    this.starts.set(sessionId, start)
    return start
  }

  /** Return an active run without starting a new one. */
  current(sessionId: string): State | undefined {
    return this.active.get(sessionId)
  }

  /** Return an active or starting run unless finalization has begun. */
  whenAvailable(sessionId: string): Promise<State> | undefined {
    if (this.finalizations.has(sessionId)) return undefined
    const current = this.active.get(sessionId)
    return current ? Promise.resolve(current) : this.starts.get(sessionId)
  }

  /** Finalize the run associated with one disposed Harness agent. */
  dispose(agent: Agent): Promise<void> {
    const sessionId = this.options.idOf(agent)
    return this.disposeSession(sessionId)
  }

  /** Finalize every active or starting run before the plugin bridge closes. */
  async disposeAll(): Promise<void> {
    const sessionIds = new Set([
      ...this.active.keys(),
      ...this.starts.keys(),
      ...this.finalizations.keys(),
    ])
    await Promise.all([...sessionIds].map(sessionId => this.disposeSession(sessionId)))
  }

  private disposeSession(sessionId: string): Promise<void> {
    const existing = this.finalizations.get(sessionId)
    if (existing) return existing

    const current = this.active.get(sessionId)
    const pending = current ? Promise.resolve(current) : this.starts.get(sessionId)
    if (!pending) return Promise.resolve()

    let completion: Promise<void>
    completion = pending
      .then(async state => {
        await this.options.finalize(state)
        if (this.active.get(sessionId) === state) {
          this.active.delete(sessionId)
        }
      })
      .catch(error => {
        this.report(error)
        throw error
      })
      .finally(() => {
        if (this.finalizations.get(sessionId) === completion) {
          this.finalizations.delete(sessionId)
        }
      })
    this.finalizations.set(sessionId, completion)
    return completion
  }

  private report(error: unknown): void {
    try {
      this.options.onError(error)
    } catch {
      // Lifecycle cleanup must complete even if the diagnostic sink fails.
    }
  }
}
