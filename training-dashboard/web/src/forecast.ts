/**
 * forecast.ts — types, API helpers, and pure utilities for the Forecast tab.
 */

const API_BASE = 'http://127.0.0.1:8000'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Province {
  id: number
  code: string
  name_en: string
  name_th: string
  region: string
  lat: number
  lon: number
}

export interface ForecastCell {
  probability: number | null
  risk_level: string | null
}

export interface ForecastMap {
  available: boolean
  generated_at?: string
  reason?: string
  cells: Record<string, ForecastCell>
}

export interface HorizonPoint {
  horizon_days: number
  target_date: string
  probability: number | null
  risk_level: string | null
  swbgt_pred: number | null
}

export interface ProvinceSeries {
  available: boolean
  reason?: string
  series: HorizonPoint[]
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

export async function fetchProvinces(): Promise<Province[]> {
  const r = await fetch(`${API_BASE}/api/forecast/provinces`)
  return (await r.json()) as Province[]
}

export async function fetchForecastMap(lead: number): Promise<ForecastMap> {
  const r = await fetch(`${API_BASE}/api/forecast/map?lead=${lead}`)
  return (await r.json()) as ForecastMap
}

export async function fetchProvinceSeries(pid: number): Promise<ProvinceSeries> {
  const r = await fetch(`${API_BASE}/api/forecast/province/${pid}`)
  return (await r.json()) as ProvinceSeries
}

// ---------------------------------------------------------------------------
// Pure utility — risk level → display color
// ---------------------------------------------------------------------------

/** Map a DB risk_level string to a CSS color string.
 *  undefined / null / unknown → neutral gray (no data).
 *
 *  Risk levels expected from the model: "low", "moderate", "high", "extreme".
 *  The neutral color is also used when available===false or the province has
 *  no row in the current snapshot.
 */
export function riskColor(risk_level: string | undefined | null): string {
  if (!risk_level) return '#9e9e9e'          // neutral — no data
  switch (risk_level.toLowerCase()) {
    case 'low':      return '#4caf50'         // green
    case 'moderate': return '#ffc24b'         // gold (theme)
    case 'high':     return '#ff6a3d'         // ember (theme)
    case 'extreme':  return '#b71c1c'         // deep red
    default:         return '#9e9e9e'         // unknown → neutral
  }
}
