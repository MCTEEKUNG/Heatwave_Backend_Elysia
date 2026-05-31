import { describe, it, expect } from 'vitest'
import { p0Gate } from './LabPanel'

describe('p0Gate', () => {
  it('green when A recovered and B beats A', () => {
    expect(p0Gate(0.62, 0.66).tone).toBe('good')
  })
  it('amber honest-null when A recovered but B ~= A', () => {
    expect(p0Gate(0.61, 0.612).tone).toBe('null')
  })
  it('red structurally-broken when A stays random', () => {
    expect(p0Gate(0.50, 0.51).tone).toBe('broken')
  })
})
