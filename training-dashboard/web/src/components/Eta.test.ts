import { describe, it, expect } from 'vitest'
import { formatEta } from './Eta'

describe('formatEta', () => {
  it('formats minutes and seconds: 108 -> "1 m 48 s"', () => {
    expect(formatEta(108)).toBe('1 m 48 s')
  })

  it('formats hours and minutes, omitting seconds: 8100 -> "2 h 15 m"', () => {
    expect(formatEta(8100)).toBe('2 h 15 m')
  })

  it('returns em-dash for 0', () => {
    expect(formatEta(0)).toBe('—')
  })

  it('returns em-dash for null', () => {
    expect(formatEta(null)).toBe('—')
  })

  it('returns em-dash for undefined / negative / non-finite', () => {
    expect(formatEta(undefined)).toBe('—')
    expect(formatEta(-5)).toBe('—')
    expect(formatEta(NaN)).toBe('—')
    expect(formatEta(Infinity)).toBe('—')
  })

  it('formats seconds-only values', () => {
    expect(formatEta(45)).toBe('45 s')
  })
})
