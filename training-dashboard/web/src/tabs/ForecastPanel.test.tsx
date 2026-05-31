import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { riskColor } from '../forecast'
import ForecastPanel from './ForecastPanel'

// ---------------------------------------------------------------------------
// riskColor — pure function, no network
// ---------------------------------------------------------------------------

describe('riskColor', () => {
  it('returns neutral gray for undefined', () => {
    expect(riskColor(undefined)).toBe('#9e9e9e')
  })

  it('returns neutral gray for null', () => {
    expect(riskColor(null)).toBe('#9e9e9e')
  })

  it('returns neutral gray for empty string', () => {
    expect(riskColor('')).toBe('#9e9e9e')
  })

  it('returns neutral gray for unknown risk level', () => {
    expect(riskColor('UNKNOWN_LEVEL')).toBe('#9e9e9e')
  })

  it('returns green for low', () => {
    expect(riskColor('low')).toBe('#4caf50')
  })

  it('returns gold for moderate', () => {
    expect(riskColor('moderate')).toBe('#ffc24b')
  })

  it('returns ember for high', () => {
    expect(riskColor('high')).toBe('#ff6a3d')
  })

  it('returns deep red for extreme', () => {
    expect(riskColor('extreme')).toBe('#b71c1c')
  })

  it('is case-insensitive', () => {
    expect(riskColor('HIGH')).toBe('#ff6a3d')
    expect(riskColor('Moderate')).toBe('#ffc24b')
    expect(riskColor('LOW')).toBe('#4caf50')
    expect(riskColor('EXTREME')).toBe('#b71c1c')
  })
})

// ---------------------------------------------------------------------------
// ForecastPanel — empty/no-data state with mocked fetch
// ---------------------------------------------------------------------------

const MOCK_PROVINCES = [
  { id: 1, code: 'BKK', name_en: 'Bangkok', name_th: 'กรุงเทพ', region: 'Central', lat: 13.75, lon: 100.50 },
  { id: 2, code: 'CNX', name_en: 'Chiang Mai', name_th: 'เชียงใหม่', region: 'North', lat: 18.79, lon: 98.98 },
]

const UNAVAILABLE_MAP = {
  available: false,
  reason: 'DB unreachable',
  cells: {},
}

function mockFetch(url: string): Promise<Response> {
  const asJson = (data: unknown) =>
    Promise.resolve(new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))

  if (url.includes('/api/forecast/provinces')) return asJson(MOCK_PROVINCES)
  if (url.includes('/api/forecast/map')) return asJson(UNAVAILABLE_MAP)
  if (url.includes('/api/forecast/province/')) {
    return asJson({ available: false, reason: 'DB unreachable', series: [] })
  }
  return Promise.reject(new Error(`Unexpected URL: ${url}`))
}

describe('ForecastPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the lead day selector', async () => {
    vi.stubGlobal('fetch', mockFetch)
    render(<ForecastPanel />)
    expect(screen.getByLabelText('Lead day:')).toBeDefined()
  })

  it('shows the no-data banner when DB is unavailable', async () => {
    vi.stubGlobal('fetch', mockFetch)
    render(<ForecastPanel />)
    await waitFor(() => {
      expect(screen.getByText(/No forecast data available/i)).toBeDefined()
    })
  })

  it('renders province cells after provinces load', async () => {
    vi.stubGlobal('fetch', mockFetch)
    render(<ForecastPanel />)
    await waitFor(() => {
      expect(screen.getByText('BKK')).toBeDefined()
      expect(screen.getByText('CNX')).toBeDefined()
    })
  })

  it('province cells have neutral color when no data', async () => {
    vi.stubGlobal('fetch', mockFetch)
    render(<ForecastPanel />)
    await waitFor(() => {
      const cells = document.querySelectorAll('.forecast-cell')
      expect(cells.length).toBeGreaterThan(0)
      cells.forEach((cell) => {
        const el = cell as HTMLElement
        // All cells should have the neutral gray background when cells:{} returned
        expect(el.style.backgroundColor).toBe('rgb(158, 158, 158)')
      })
    })
  })

  it('shows region group headers', async () => {
    vi.stubGlobal('fetch', mockFetch)
    render(<ForecastPanel />)
    await waitFor(() => {
      expect(screen.getByText('Central')).toBeDefined()
      expect(screen.getByText('North')).toBeDefined()
    })
  })

  it('shows the detail panel placeholder text before any cell is selected', async () => {
    vi.stubGlobal('fetch', mockFetch)
    render(<ForecastPanel />)
    await waitFor(() => {
      expect(screen.getByText(/Click a province cell to see its forecast series/i)).toBeDefined()
    })
  })
})
