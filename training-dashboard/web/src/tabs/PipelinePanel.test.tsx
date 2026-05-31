import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { stageTone } from '../pipeline'
import PipelinePanel from './PipelinePanel'

// ────────────────────────────────────────────────────────────────────────────
// Pure-function unit tests for stageTone (no network, no React)
// ────────────────────────────────────────────────────────────────────────────

describe('stageTone', () => {
  it('returns tone-ready for "ready"', () => {
    expect(stageTone('ready')).toBe('tone-ready')
  })

  it('returns tone-missing for "missing"', () => {
    expect(stageTone('missing')).toBe('tone-missing')
  })

  it('returns tone-unknown for undefined', () => {
    expect(stageTone(undefined)).toBe('tone-unknown')
  })

  it('returns tone-unknown for an unknown status string', () => {
    expect(stageTone('pending')).toBe('tone-unknown')
  })

  it('returns tone-unknown for empty string', () => {
    expect(stageTone('')).toBe('tone-unknown')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// Render test: loading state when fetch never resolves
// ────────────────────────────────────────────────────────────────────────────

describe('PipelinePanel', () => {
  beforeEach(() => {
    // Mock global fetch to return a promise that never resolves, simulating
    // a pending request so the component stays in its initial loading state.
    vi.stubGlobal('fetch', () => new Promise(() => {}))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows loading text while fetch is pending', () => {
    render(<PipelinePanel connected={false} />)
    expect(screen.getByText(/loading pipeline status/i)).toBeTruthy()
  })

  it('renders without crashing when connected=true', () => {
    const { container } = render(<PipelinePanel connected={true} />)
    expect(container.querySelector('.pipeline')).toBeTruthy()
  })
})
