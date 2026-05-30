import { describe, it, expect } from 'vitest'
import { initialState, reduce, setConnection } from './ws'
import type { ServerEvent } from './protocol'

function status(over: Partial<Extract<ServerEvent, { type: 'status' }>> = {}) {
  return {
    type: 'status',
    state: 'running',
    progress: 0,
    step: 0,
    total_steps: 10000,
    speed_per_sec: 100,
    eta_seconds: 90,
    message: '',
    ts: 0,
    ...over,
  } as ServerEvent
}

describe('reduce', () => {
  it('folds the running -> running -> done -> metrics sequence', () => {
    const events: ServerEvent[] = [
      status({ state: 'running', progress: 10, step: 1000, speed_per_sec: 100, message: 'go' }),
      status({ state: 'running', progress: 20, step: 2000, speed_per_sec: 110, eta_seconds: 72 }),
      status({ state: 'done', progress: 100, step: 10000, speed_per_sec: 120, eta_seconds: 0, message: 'finished' }),
      { type: 'metrics', report: { auc: 0.91, nested: { rmse: 1.2 } } },
    ]

    const final = events.reduce(reduce, initialState)

    expect(final.state).toBe('done')
    expect(final.progress).toBe(100)
    expect(final.step).toBe(10000)
    expect(final.speed_per_sec).toBe(120)
    expect(final.message).toBe('finished')
    // three status events => three speed samples
    expect(final.speedHistory).toEqual([100, 110, 120])
    // metrics set and state preserved
    expect(final.metrics).toEqual({ auc: 0.91, nested: { rmse: 1.2 } })
    expect(final.state).toBe('done')
    expect(final.error).toBeNull()
  })

  it('appends log entries without touching run state', () => {
    let s = reduce(initialState, status({ state: 'running' }))
    s = reduce(s, { type: 'log', level: 'warn', message: 'careful', ts: 1 })
    s = reduce(s, { type: 'log', level: 'error', message: 'boom', ts: 2 })
    expect(s.logs).toHaveLength(2)
    expect(s.logs[1]).toEqual({ level: 'error', message: 'boom', ts: 2 })
    expect(s.state).toBe('running')
  })

  it('records errors via the error event then status error', () => {
    let s = reduce(initialState, { type: 'error', message: 'kaboom' })
    expect(s.error).toBe('kaboom')
    s = reduce(s, status({ state: 'error', message: 'failed' }))
    expect(s.state).toBe('error')
    // an error status must not wipe the captured error message
    expect(s.error).toBe('kaboom')
  })

  it('keeps reduce pure (does not mutate input state)', () => {
    const before = { ...initialState, speedHistory: [...initialState.speedHistory] }
    reduce(initialState, status({ speed_per_sec: 50 }))
    expect(initialState.speedHistory).toEqual(before.speedHistory)
    expect(initialState.state).toBe('idle')
  })

  it('setConnection updates only the connection field', () => {
    const s = setConnection(initialState, 'open')
    expect(s.connection).toBe('open')
    expect(s.state).toBe('idle')
  })
})
