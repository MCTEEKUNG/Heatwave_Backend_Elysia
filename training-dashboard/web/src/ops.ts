const API_BASE = 'http://127.0.0.1:8000'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DashboardModelMetrics {
  f2?: number
  pr_auc?: number
  roc_auc?: number
  mcc?: number
  brier?: number
  threshold?: number
  n?: number
  n_pos?: number
  base_rate?: number
  [key: string]: unknown
}

export interface DashboardModelSidecar {
  trainer?: string
  saved_at?: string
  model_version?: string
  class?: string
  metrics?: DashboardModelMetrics
  [key: string]: unknown
}

export interface DashboardModel {
  name: string
  /** Full sidecar JSON (may include trainer, saved_at, metrics sub-object, etc.) */
  metrics: DashboardModelSidecar
  file_exists: boolean
  size_mb: number | null
}

/** The production model card — shape may vary (original or promotion-written). */
export interface ProductionCard {
  // Original training card fields
  model?: string
  stage?: string
  trained_at?: string
  model_version?: string
  test_metrics?: DashboardModelMetrics
  // Promotion-written fields
  promoted_from?: string
  promoted_at?: string
  source_metrics?: DashboardModelSidecar
  [key: string]: unknown
}

export interface OpsModelsResponse {
  models: DashboardModel[]
  production: ProductionCard | null
}

export interface PromoteResponse {
  promoted: boolean
  name: string
  target: string
}

export interface OpsRun {
  ts: string
  /** trainer name written by lgbm.py / sklearn_models.py */
  trainer?: string
  /** flat metric keys written directly by append_run callers */
  f2?: number
  pr_auc?: number
  brier_skill_score?: number
  threshold?: number
  n_provinces?: number
  saved?: string
  config?: Record<string, unknown>
  [key: string]: unknown
}

export interface OpsRunsResponse {
  runs: OpsRun[]
}

// ---------------------------------------------------------------------------
// Pure helper — typed-confirm gate
// ---------------------------------------------------------------------------

/**
 * Returns true when the user has typed a valid confirmation string.
 * Accepts either the exact model name or the word "promote" (case-insensitive).
 */
export function canPromote(typed: string, modelName: string): boolean {
  const t = typed.trim()
  if (t.length === 0) return false
  return t === modelName || t.toLowerCase() === 'promote'
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function fetchOpsModels(): Promise<OpsModelsResponse> {
  const r = await fetch(`${API_BASE}/api/ops/models`)
  if (!r.ok) throw new Error(`GET /api/ops/models → ${r.status}`)
  return (await r.json()) as OpsModelsResponse
}

export async function promoteModel(name: string): Promise<PromoteResponse> {
  const r = await fetch(`${API_BASE}/api/ops/promote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!r.ok) {
    const detail = await r.text()
    throw new Error(`POST /api/ops/promote → ${r.status}: ${detail}`)
  }
  return (await r.json()) as PromoteResponse
}

export async function rollbackModel(): Promise<{ ok: boolean; restored?: unknown[] }> {
  const r = await fetch(`${API_BASE}/api/ops/rollback`, { method: 'POST' })
  if (!r.ok) {
    const detail = await r.text()
    throw new Error(`POST /api/ops/rollback → ${r.status}: ${detail}`)
  }
  return (await r.json()) as { ok: boolean; restored?: unknown[] }
}

export async function fetchOpsRuns(): Promise<OpsRunsResponse> {
  const r = await fetch(`${API_BASE}/api/ops/runs`)
  if (!r.ok) throw new Error(`GET /api/ops/runs → ${r.status}`)
  return (await r.json()) as OpsRunsResponse
}
