import { useEffect, useRef, useState } from 'react'
import './OpsPanel.css'
import {
  canPromote,
  fetchOpsModels,
  fetchOpsRuns,
  promoteModel,
  rollbackModel,
  type DashboardModel,
  type OpsRun,
  type ProductionCard,
} from '../ops'

// ---------------------------------------------------------------------------
// Small pure helpers
// ---------------------------------------------------------------------------

function fmt(v: number | undefined | null, decimals = 3): string {
  if (v === undefined || v === null) return '—'
  return v.toFixed(decimals)
}

function fmtTs(ts: string): string {
  try {
    return new Date(ts).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ts
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricPill({ label, value, hot = false }: {
  label: string
  value: string
  hot?: boolean
}) {
  return (
    <div className="ops-prod-metric">
      <span className="ops-metric-label">{label}</span>
      <span className={`ops-metric-value${hot ? ' ops-metric-hot' : ''}`}>{value}</span>
    </div>
  )
}

function ProductionBanner({ card }: { card: ProductionCard }) {
  // Card may be from original training or promotion-written — handle both shapes.
  const name =
    card.promoted_from ??
    card.model_version ??
    card.model ??
    'production model'

  const when =
    card.promoted_at ?? card.trained_at

  const m = card.test_metrics ?? card.source_metrics?.metrics

  return (
    <div className="ops-prod-banner">
      <div className="ops-prod-row">
        <span className="ops-prod-name">{name}</span>
        {when && <span className="ops-prod-meta">{fmtTs(when)}</span>}
      </div>
      {card.promoted_from && (
        <div className="ops-prod-meta" style={{ marginTop: 4 }}>
          promoted from dashboard model
        </div>
      )}
      {m && (
        <div className="ops-prod-metrics">
          <MetricPill label="F2" value={fmt(m.f2)} hot />
          <MetricPill label="PR-AUC" value={fmt(m.pr_auc)} />
          <MetricPill label="ROC-AUC" value={fmt(m.roc_auc)} />
          <MetricPill label="MCC" value={fmt(m.mcc)} />
          <MetricPill label="Threshold" value={fmt(m.threshold, 4)} />
        </div>
      )}
    </div>
  )
}

function ModelCard({
  model,
  connected,
  onPromoteSuccess,
}: {
  model: DashboardModel
  connected: boolean
  onPromoteSuccess: () => void
}) {
  const [typed, setTyped] = useState('')
  const [promoting, setPromoting] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const m = model.metrics?.metrics

  async function handlePromote() {
    if (!canPromote(typed, model.name)) return
    setPromoting(true)
    setNotice(null)
    try {
      await promoteModel(model.name)
      setNotice({ kind: 'success', text: `Promoted to production.` })
      setTyped('')
      onPromoteSuccess()
    } catch (e) {
      setNotice({
        kind: 'error',
        text: e instanceof Error ? e.message : 'Promotion failed',
      })
    } finally {
      setPromoting(false)
    }
  }

  return (
    <div className={`ops-model-card${model.file_exists ? '' : ' ops-model-missing'}`}>
      <div className="ops-model-head">
        <span className="ops-model-name">{model.name}</span>
        <span className="ops-model-size">
          {model.file_exists
            ? model.size_mb !== null
              ? `${model.size_mb} MB`
              : '.pkl'
            : <span className="ops-missing-badge">no .pkl</span>
          }
        </span>
      </div>

      {m && (
        <div className="ops-model-metrics">
          <MetricPill label="F2" value={fmt(m.f2)} hot />
          <MetricPill label="PR-AUC" value={fmt(m.pr_auc)} />
          <MetricPill label="ROC-AUC" value={fmt(m.roc_auc)} />
        </div>
      )}

      {model.metrics?.saved_at && (
        <div style={{ fontSize: '0.72rem', color: 'var(--muted, #8a8070)' }}>
          saved {fmtTs(model.metrics.saved_at)}
        </div>
      )}

      <div className="ops-promote-row">
        <input
          ref={inputRef}
          className="ops-confirm-input"
          type="text"
          placeholder={`type "${model.name}" to confirm`}
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          disabled={!connected || !model.file_exists || promoting}
          aria-label={`Confirm promotion of ${model.name}`}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && canPromote(typed, model.name)) void handlePromote()
          }}
        />
        <button
          className="btn btn-promote btn-promote-dark"
          disabled={!connected || !model.file_exists || promoting || !canPromote(typed, model.name)}
          onClick={() => void handlePromote()}
          aria-label={`Promote ${model.name} to production`}
        >
          {promoting ? 'Promoting…' : 'Promote'}
        </button>
      </div>

      {notice && (
        <div className={`ops-notice ops-notice-${notice.kind}`} role="status">
          {notice.text}
        </div>
      )}
    </div>
  )
}

function RunsSection({ runs }: { runs: OpsRun[] }) {
  if (runs.length === 0) {
    return <p className="ops-empty">No runs recorded yet.</p>
  }

  return (
    <div className="ops-runs-wrap">
      <table className="ops-runs-table" aria-label="Run history">
        <thead>
          <tr>
            <th>When</th>
            <th>Trainer</th>
            <th>F2</th>
            <th>PR-AUC</th>
            <th>Brier-SS</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run, i) => (
              <tr key={i}>
                <td className="ops-run-ts">{run.ts ? fmtTs(run.ts) : '—'}</td>
                <td className="ops-run-trainer">{run.trainer ?? '—'}</td>
                <td className={run.f2 !== undefined ? 'ops-run-metric' : 'ops-run-metric-na'}>
                  {fmt(run.f2)}
                </td>
                <td className={run.pr_auc !== undefined ? 'ops-run-metric' : 'ops-run-metric-na'}>
                  {fmt(run.pr_auc)}
                </td>
                <td className={run.brier_skill_score !== undefined ? 'ops-run-metric' : 'ops-run-metric-na'}>
                  {fmt(run.brier_skill_score)}
                </td>
              </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function OpsPanel({ connected }: { connected: boolean }) {
  const [models, setModels] = useState<DashboardModel[] | null>(null)
  const [production, setProduction] = useState<ProductionCard | null>(null)
  const [runs, setRuns] = useState<OpsRun[] | null>(null)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [rolling, setRolling] = useState(false)
  const [opsNotice, setOpsNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  async function handleRollback() {
    setRolling(true)
    setOpsNotice(null)
    try {
      await rollbackModel()
      setOpsNotice({ kind: 'success', text: 'Rolled back to the previous production model.' })
      await loadModels()
    } catch (e) {
      setOpsNotice({ kind: 'error', text: e instanceof Error ? e.message : 'Rollback failed' })
    } finally {
      setRolling(false)
    }
  }

  async function loadModels() {
    setModelsError(null)
    try {
      const data = await fetchOpsModels()
      setModels(data.models)
      setProduction(data.production)
    } catch (e) {
      setModelsError(e instanceof Error ? e.message : 'Failed to load models')
    }
  }

  async function loadRuns() {
    setRunsError(null)
    try {
      const data = await fetchOpsRuns()
      setRuns(data.runs)
    } catch (e) {
      setRunsError(e instanceof Error ? e.message : 'Failed to load runs')
    }
  }

  useEffect(() => {
    let alive = true
    void (async () => {
      if (!alive) return
      await Promise.all([loadModels(), loadRuns()])
    })()
    return () => { alive = false }
  }, [])

  return (
    <div className="ops">
      {/* ── Production model ── */}
      <section className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 className="ops-section-title" style={{ margin: 0 }}>Current production model</h3>
          <button
            className="btn btn-refresh"
            disabled={!connected || rolling}
            onClick={() => void handleRollback()}
            aria-label="Rollback to the previous production model"
          >
            {rolling ? 'Rolling back…' : 'Rollback'}
          </button>
        </div>
        {opsNotice && (
          <div className={`ops-notice ops-notice-${opsNotice.kind}`} role="status" style={{ marginBottom: 12 }}>
            {opsNotice.text}
          </div>
        )}
        {production === undefined || (models === null && !modelsError) ? (
          <p className="ops-loading">Loading…</p>
        ) : production ? (
          <ProductionBanner card={production} />
        ) : (
          <p className="ops-empty">No production model card found.</p>
        )}
      </section>

      {/* ── Dashboard models / promote ── */}
      <section className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 className="ops-section-title" style={{ margin: 0 }}>Dashboard models</h3>
          <button
            className="btn btn-refresh"
            onClick={() => void loadModels()}
            aria-label="Refresh models list"
          >
            Refresh
          </button>
        </div>

        {!connected && (
          <div className="ops-notice ops-notice-error" style={{ marginBottom: 12 }}>
            Server disconnected — promotion disabled.
          </div>
        )}

        {modelsError && (
          <p className="ops-notice ops-notice-error">{modelsError}</p>
        )}

        {models === null && !modelsError ? (
          <p className="ops-loading">Loading…</p>
        ) : models !== null && models.length === 0 ? (
          <p className="ops-empty">No trained dashboard models found. Run a training job first.</p>
        ) : models !== null ? (
          <div className="ops-model-grid">
            {models.map((m) => (
              <ModelCard
                key={m.name}
                model={m}
                connected={connected}
                onPromoteSuccess={() => void loadModels()}
              />
            ))}
          </div>
        ) : null}
      </section>

      {/* ── Run history ── */}
      <section className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 className="ops-section-title" style={{ margin: 0 }}>Run history</h3>
          <button
            className="btn btn-refresh"
            onClick={() => void loadRuns()}
            aria-label="Refresh run history"
          >
            Refresh
          </button>
        </div>

        {runsError && (
          <p className="ops-notice ops-notice-error">{runsError}</p>
        )}

        {runs === null && !runsError ? (
          <p className="ops-loading">Loading…</p>
        ) : runs !== null ? (
          <RunsSection runs={runs} />
        ) : null}
      </section>
    </div>
  )
}
