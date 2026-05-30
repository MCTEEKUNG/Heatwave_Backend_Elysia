import { useCallback, useEffect, useState } from 'react'
import FolderIcon from './FolderIcon'

const API_BASE = 'http://127.0.0.1:8000'

type Row = {
  model: string
  f2: number | null
  pr_auc: number | null
  brier_skill_score: number | null
  roc_auc: number | null
  brier: number | null
  mcc: number | null
  fit_seconds?: number | null
}

type Leaderboard = {
  available?: boolean
  error?: string
  dataset?: string
  n_provinces?: number
  n_test?: number
  test_base_rate?: number
  split?: { train: string; val: string; test: string }
  ranked_by?: string
  results?: Row[]
}

const fmt = (v: number | null | undefined, d = 3) =>
  v === null || v === undefined ? '—' : v.toFixed(d)

const COLS: { key: keyof Row; label: string; d?: number }[] = [
  { key: 'f2', label: 'F2' },
  { key: 'pr_auc', label: 'PR-AUC' },
  { key: 'brier_skill_score', label: 'BSS' },
  { key: 'roc_auc', label: 'ROC-AUC' },
  { key: 'brier', label: 'Brier', d: 4 },
  { key: 'mcc', label: 'MCC' },
  { key: 'fit_seconds', label: 'fit (s)', d: 0 },
]

export default function LeaderboardPanel({ refreshSignal }: { refreshSignal?: number }) {
  const [data, setData] = useState<Leaderboard | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch(`${API_BASE}/api/leaderboard`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshSignal])

  const results = data?.results ?? []
  const hasResults = (data?.available ?? false) && results.length > 0

  return (
    <div className="card leaderboard-card">
      <div className="card-head">
        <div className="card-title">model leaderboard</div>
        <div className="lb-actions">
          <button
            className="btn btn-refresh folder-btn"
            title="Open the saved-models folder (models/dashboard)"
            onClick={() => {
              void fetch(`${API_BASE}/api/reveal-models`, { method: 'POST' })
            }}
          >
            <FolderIcon />
            models folder
          </button>
          <button className="btn btn-refresh" onClick={() => void load()} disabled={loading}>
            {loading ? 'loading…' : 'refresh'}
          </button>
        </div>
      </div>

      {hasResults && (
        <div className="lb-meta">
          {data?.n_provinces != null && <span>{data.n_provinces} provinces</span>}
          {data?.n_test != null && <span>test n={data.n_test.toLocaleString()}</span>}
          {data?.test_base_rate != null && (
            <span>base rate {(data.test_base_rate * 100).toFixed(1)}%</span>
          )}
          {data?.split && (
            <span>
              split {data.split.train} / {data.split.val} / {data.split.test}
            </span>
          )}
          {data?.ranked_by && <span>ranked by {data.ranked_by}</span>}
        </div>
      )}

      {error ? (
        <div className="lb-empty lb-error">could not load leaderboard: {error}</div>
      ) : !hasResults ? (
        <div className="lb-empty">
          no leaderboard yet — run <code>scripts/bakeoff.py</code> to compare models
        </div>
      ) : (
        <div className="lb-scroll">
          <table className="lb-table">
            <thead>
              <tr>
                <th className="lb-rank">#</th>
                <th className="lb-model">model</th>
                {COLS.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((row, i) => (
                <tr key={row.model} className={i === 0 ? 'lb-best' : undefined}>
                  <td className="lb-rank">{i + 1}</td>
                  <td className="lb-model" title={row.model}>
                    {i === 0 ? '🏆 ' : ''}
                    {row.model}
                  </td>
                  {COLS.map((c) => (
                    <td key={c.key}>{fmt(row[c.key] as number | null | undefined, c.d ?? 3)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
