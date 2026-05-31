const API_BASE = 'http://127.0.0.1:8000'

export interface PipelineStage {
  /** Unique identifier, e.g. "data", "gefs", "train", "forecast", "deploy" */
  key: string
  /** Human-readable label shown on the card */
  label: string
  /** "ready" | "missing" — only present when the server computed a binary state */
  status?: string
  /** Detail line: mtime, row count, last-run info, etc. */
  detail?: string
  /** If true, a Run button is rendered */
  runnable?: boolean
  /**
   * Stage name to dispatch via cockpit-run-stage when the user clicks Run.
   * Only present when runnable === true.
   */
  stage?: string
  /** Hash fragment of the tab to navigate to when the card's Open link is clicked */
  link?: string
}

export interface PipelineStatus {
  stages: PipelineStage[]
}

export async function fetchPipelineStatus(): Promise<PipelineStatus> {
  const r = await fetch(`${API_BASE}/api/pipeline/status`)
  return (await r.json()) as PipelineStatus
}

/**
 * Pure helper: map a status string to a CSS tone class.
 * "ready"   -> "tone-ready"
 * "missing" -> "tone-missing"
 * anything else or undefined -> "tone-unknown"
 */
export function stageTone(status: string | undefined): string {
  if (status === 'ready') return 'tone-ready'
  if (status === 'missing') return 'tone-missing'
  return 'tone-unknown'
}
