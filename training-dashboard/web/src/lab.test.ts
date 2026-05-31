import { describe, it, expect } from 'vitest'
import { gefsPercent, type GefsStatus } from './lab'

describe('gefsPercent', () => {
  it('computes inits/target as a clamped percent', () => {
    const st: GefsStatus = { inits: 62, target: 124, rows: 0, by_year: {},
      fc_spfh_pct: 100, running: true, log_tail: '' }
    expect(gefsPercent(st)).toBe(50)
  })
  it('is 0 when target is 0', () => {
    expect(gefsPercent({ inits: 5, target: 0, rows: 0, by_year: {},
      fc_spfh_pct: 0, running: false, log_tail: '' })).toBe(0)
  })
})
