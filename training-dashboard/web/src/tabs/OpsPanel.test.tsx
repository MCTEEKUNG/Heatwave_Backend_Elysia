import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { canPromote } from '../ops'
import OpsPanel from './OpsPanel'

// ---------------------------------------------------------------------------
// Pure unit: canPromote
// ---------------------------------------------------------------------------

describe('canPromote', () => {
  it('allows exact model name', () => {
    expect(canPromote('balanced_rf', 'balanced_rf')).toBe(true)
  })

  it('allows the word "promote" (case-insensitive)', () => {
    expect(canPromote('promote', 'xgboost')).toBe(true)
    expect(canPromote('PROMOTE', 'xgboost')).toBe(true)
    expect(canPromote('Promote', 'lgbm')).toBe(true)
  })

  it('rejects empty string', () => {
    expect(canPromote('', 'balanced_rf')).toBe(false)
  })

  it('rejects whitespace-only string', () => {
    expect(canPromote('   ', 'balanced_rf')).toBe(false)
  })

  it('rejects wrong model name', () => {
    expect(canPromote('wrong_model', 'balanced_rf')).toBe(false)
  })

  it('rejects partial match', () => {
    expect(canPromote('balanced', 'balanced_rf')).toBe(false)
  })

  it('accepts name with surrounding whitespace (trimmed by the helper)', () => {
    // canPromote trims input so that copy-paste accidents with a trailing space still work.
    expect(canPromote(' balanced_rf', 'balanced_rf')).toBe(true)
    expect(canPromote('balanced_rf ', 'balanced_rf')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Render tests — mocked fetch, no real network, no promote endpoint call
// ---------------------------------------------------------------------------

const EMPTY_MODELS_RESPONSE = { models: [], production: null }
const EMPTY_RUNS_RESPONSE = { runs: [] }

function makeFetch(
  modelsBody: unknown = EMPTY_MODELS_RESPONSE,
  runsBody: unknown = EMPTY_RUNS_RESPONSE,
) {
  return vi.fn((url: string) => {
    const body =
      typeof url === 'string' && url.includes('/api/ops/models')
        ? modelsBody
        : typeof url === 'string' && url.includes('/api/ops/runs')
          ? runsBody
          : { error: 'unexpected url' }

    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(body),
    })
  }) as unknown as typeof fetch
}

describe('OpsPanel rendering', () => {
  let originalFetch: typeof fetch

  beforeEach(() => {
    originalFetch = globalThis.fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('shows loading state initially (connected=false)', () => {
    // Fetch that never resolves so loading persists
    globalThis.fetch = vi.fn(() => new Promise(() => { /* never */ })) as unknown as typeof fetch
    render(<OpsPanel connected={false} />)
    // Multiple "Loading…" nodes are expected (one per section)
    const loadingEls = screen.getAllByText('Loading…')
    expect(loadingEls.length).toBeGreaterThan(0)
  })

  it('shows disconnected warning when connected=false', () => {
    globalThis.fetch = makeFetch()
    render(<OpsPanel connected={false} />)
    expect(screen.getByText(/Server disconnected/i)).toBeTruthy()
  })

  it('renders empty model state when no models returned', async () => {
    globalThis.fetch = makeFetch()
    render(<OpsPanel connected={true} />)
    await waitFor(() => {
      expect(screen.getByText(/No trained dashboard models found/i)).toBeTruthy()
    })
  })

  it('renders empty runs state when no runs returned', async () => {
    globalThis.fetch = makeFetch()
    render(<OpsPanel connected={true} />)
    await waitFor(() => {
      expect(screen.getByText(/No runs recorded yet/i)).toBeTruthy()
    })
  })

  it('renders model cards when models are returned', async () => {
    const mockModels = {
      models: [
        {
          name: 'lgbm',
          metrics: {
            trainer: 'lgbm',
            saved_at: '2026-05-30T17:57:09+00:00',
            metrics: { f2: 0.56, pr_auc: 0.33, roc_auc: 0.76 },
          },
          file_exists: true,
          size_mb: 0.7,
        },
        {
          name: 'xgboost',
          metrics: { metrics: { f2: 0.54, pr_auc: 0.31, roc_auc: 0.74 } },
          file_exists: false,
          size_mb: null,
        },
      ],
      production: null,
    }
    globalThis.fetch = makeFetch(mockModels)
    render(<OpsPanel connected={true} />)

    await waitFor(() => {
      expect(screen.getByText('lgbm')).toBeTruthy()
      expect(screen.getByText('xgboost')).toBeTruthy()
    })
  })

  it('renders production banner when production card is present', async () => {
    const mockData = {
      models: [],
      production: {
        promoted_from: 'lgbm',
        promoted_at: '2026-05-31T10:00:00+00:00',
        source_metrics: { metrics: { f2: 0.56, pr_auc: 0.33, roc_auc: 0.76 } },
      },
    }
    globalThis.fetch = makeFetch(mockData)
    render(<OpsPanel connected={true} />)

    await waitFor(() => {
      expect(screen.getByText('lgbm')).toBeTruthy()
    })
  })

  it('renders runs table when runs are present', async () => {
    const mockRuns = {
      runs: [
        {
          ts: '2026-05-30T18:00:00+00:00',
          trainer: 'lgbm',
          // flat keys matching append_run callers in lgbm.py / sklearn_models.py
          f2: 0.55,
          pr_auc: 0.32,
          brier_skill_score: 0.09,
        },
      ],
    }
    globalThis.fetch = makeFetch(EMPTY_MODELS_RESPONSE, mockRuns)
    render(<OpsPanel connected={true} />)

    await waitFor(() => {
      expect(screen.getByText('lgbm')).toBeTruthy()
    })
  })

  it('Promote button is disabled when connected=false even if model exists', async () => {
    const mockModels = {
      models: [
        {
          name: 'lgbm',
          metrics: { metrics: { f2: 0.56 } },
          file_exists: true,
          size_mb: 0.7,
        },
      ],
      production: null,
    }
    globalThis.fetch = makeFetch(mockModels)
    render(<OpsPanel connected={false} />)

    await waitFor(() => {
      const promoteBtn = screen.getByRole('button', { name: /Promote lgbm/i })
      expect((promoteBtn as HTMLButtonElement).disabled).toBe(true)
    })
  })
})
