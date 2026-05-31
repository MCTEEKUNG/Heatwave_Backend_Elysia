import { useEffect, useState } from 'react'
import {
  fetchGefsStatus, startGefs, stopGefs, fetchP0Runs, gefsPercent,
  type GefsStatus, type P0Run,
} from '../lab'

export function p0Gate(aRoc: number, bRoc: number): { tone: 'good' | 'null' | 'broken'; text: string } {
  if (aRoc < 0.58) return { tone: 'broken', text: 'A still ~random — evaluation underpowered/broken; more data or pivot' }
  if (bRoc - aRoc >= 0.01) return { tone: 'good', text: 'A recovered and forecast covariate adds lift — real P0 signal' }
  return { tone: 'null', text: 'A recovered but B ≈ A — honest null; forecast covariate does not help here' }
}

export default function LabPanel({ connected }: { connected: boolean }) {
  const [gefs, setGefs] = useState<GefsStatus | null>(null)
  const [runs, setRuns] = useState<P0Run[]>([])

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const [g, r] = await Promise.all([fetchGefsStatus(), fetchP0Runs()])
        if (alive) { setGefs(g); setRuns(r) }
      } catch { /* server down; keep last */ }
    }
    void tick()
    const id = setInterval(tick, 4000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const latest = runs.length ? runs[runs.length - 1] : undefined
  const gate = latest ? p0Gate(latest.a_roc, latest.b_roc) : null

  return (
    <div className="lab">
      <section className="card lab-card">
        <div className="lab-head">
          <h3>GEFS reforecast pull</h3>
          <div className="lab-actions">
            <button className="btn" disabled={gefs?.running} onClick={() => void startGefs()}>Start / resume</button>
            <button className="btn" disabled={!gefs?.running} onClick={() => void stopGefs()}>Stop</button>
          </div>
        </div>
        {gefs ? (
          <>
            <div className="lab-progress">
              <div className="lab-bar" style={{ width: `${gefsPercent(gefs)}%` }} />
            </div>
            <p className="lab-stat">
              <strong>{gefs.inits}/{gefs.target}</strong> inits · {gefs.rows.toLocaleString()} rows ·
              humidity {gefs.fc_spfh_pct}% · {gefs.running ? '● running' : 'idle'}
            </p>
            <p className="lab-years">{Object.entries(gefs.by_year).map(([y, n]) => `${y}:${n}`).join('  ')}</p>
            <pre className="lab-log">{gefs.log_tail}</pre>
          </>
        ) : <p className="subtitle">loading…</p>}
      </section>

      <section className="card lab-card">
        <div className="lab-head">
          <h3>P0 forecast-covariate measurement</h3>
          <button className="btn btn-primary" disabled={!connected}
            onClick={() => window.dispatchEvent(new CustomEvent('lab-run-p0'))}>
            Run P0
          </button>
        </div>
        {latest && gate ? (
          <>
            <table className="lab-table">
              <thead><tr><th>model</th><th>ROC</th><th>PR-AUC lift</th></tr></thead>
              <tbody>
                <tr><td>A antecedent</td><td>{latest.a_roc.toFixed(3)}</td><td>{latest.a_lift.toFixed(2)}×</td></tr>
                <tr><td>B + GEFS forecast</td><td>{latest.b_roc.toFixed(3)}</td><td>{latest.b_lift.toFixed(2)}×</td></tr>
              </tbody>
            </table>
            <div className={`lab-gate gate-${gate.tone}`}>{gate.text}</div>
            <p className="lab-meta">matched {latest.matched_rows?.toLocaleString?.() ?? '—'} rows ·
              years {latest.origin_years?.join(', ')} · pos {(latest.pos_rate * 100).toFixed(1)}%</p>
          </>
        ) : <p className="subtitle">No P0 run yet — click "Run P0".</p>}
      </section>
    </div>
  )
}
