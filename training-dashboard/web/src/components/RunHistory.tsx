import { useCallback, useEffect, useState } from 'react'

const API_BASE = 'http://127.0.0.1:8000'

type Run = {
  ts: string
  trainer: string
  f2: number | null
  pr_auc: number | null
  brier_skill_score: number | null
  threshold: number | null
  n_provinces: number | null
  saved: boolean
  config: Record<string, unknown>
}

type RunsResponse = {
  runs: Run[]
}

const f3 = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : v.toFixed(3)

export default function RunHistory() {
  const [data, setData] = useState<RunsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch(`${API_BASE}/api/runs`)
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
  }, [load])

  const runs = data?.runs ?? []
  const hasRuns = runs.length > 0

  return (
    <div className="card leaderboard-card">
      <div className="card-head">
        <div className="card-title">run history</div>
        <div className="lb-actions">
          <button className="btn btn-refresh" onClick={() => void load()} disabled={loading}>
            {loading ? 'loading…' : 'refresh'}
          </button>
        </div>
      </div>

      {error ? (
        <div className="lb-empty lb-error">could not load run history: {error}</div>
      ) : !hasRuns ? (
        <div className="lb-empty">no runs yet — train a model to log one here</div>
      ) : (
        <div className="lb-scroll">
          <table className="lb-table">
            <thead>
              <tr>
                <th>when</th>
                <th>model</th>
                <th>F2</th>
                <th>PR-AUC</th>
                <th>BSS</th>
                <th>thr</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((row, i) => (
                <tr key={i}>
                  <td className="tnum">{row.ts.replace('T', ' ').slice(0, 16)}</td>
                  <td>{row.trainer}</td>
                  <td className="tnum">{f3(row.f2)}</td>
                  <td className="tnum">{f3(row.pr_auc)}</td>
                  <td className="tnum">{f3(row.brier_skill_score)}</td>
                  <td className="tnum">{f3(row.threshold)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
