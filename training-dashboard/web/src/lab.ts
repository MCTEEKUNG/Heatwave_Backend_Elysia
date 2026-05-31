const API_BASE = 'http://127.0.0.1:8000'

export interface GefsStatus {
  inits: number
  target: number
  rows: number
  by_year: Record<string, number>
  fc_spfh_pct: number
  running: boolean
  log_tail: string
}

export interface P0Run {
  ts: number
  a_roc: number
  origin_years?: number[]
  matched_rows?: number
  pos_rate?: number
  b_roc?: number
  a_lift?: number
  b_lift?: number
}

export function gefsPercent(s: GefsStatus): number {
  if (!s.target) return 0
  return Math.max(0, Math.min(100, Math.round((s.inits / s.target) * 100)))
}

export async function fetchGefsStatus(): Promise<GefsStatus> {
  const r = await fetch(`${API_BASE}/api/gefs/status`)
  return (await r.json()) as GefsStatus
}
export async function startGefs(): Promise<void> {
  await fetch(`${API_BASE}/api/gefs/start`, { method: 'POST' })
}
export async function stopGefs(): Promise<void> {
  await fetch(`${API_BASE}/api/gefs/stop`, { method: 'POST' })
}
export async function fetchP0Runs(): Promise<P0Run[]> {
  const r = await fetch(`${API_BASE}/api/p0/runs`)
  const body = (await r.json()) as { runs: P0Run[] }
  return body.runs ?? []
}
