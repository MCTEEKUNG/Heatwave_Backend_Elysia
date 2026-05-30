import { useCallback, useEffect, useState } from 'react'

const API_BASE = 'http://127.0.0.1:8000'

// ---- helpers ---------------------------------------------------------------
const f3 = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : v.toFixed(3)
const pct = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(d)}%`

/** bad(red) -> mid(amber) -> good(green) ramp for an F2 cell (domain ~0..0.7). */
function perfColor(f2: number | null | undefined): string {
  if (f2 === null || f2 === undefined) return 'var(--muted-2)'
  const t = Math.max(0, Math.min(1, f2 / 0.65))
  const stops =
    t < 0.5
      ? ['255,93,93', '240,180,41', (t / 0.5).toFixed(2)]
      : ['240,180,41', '86,192,141', ((t - 0.5) / 0.5).toFixed(2)]
  const a = stops[0].split(',').map(Number)
  const b = stops[1].split(',').map(Number)
  const m = Number(stops[2])
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * m))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

type Report = Record<string, any>

// ---- tiny SVG chart primitives --------------------------------------------
function Axes({ w, h, pad }: { w: number; h: number; pad: number }) {
  return (
    <>
      <line x1={pad} y1={h - pad} x2={w - 4} y2={h - pad} className="axis" />
      <line x1={pad} y1={4} x2={pad} y2={h - pad} className="axis" />
    </>
  )
}

function PerHorizon({ rows }: { rows: any[] }) {
  const w = 440, h = 200, pad = 34
  const xs = rows.map((_, i) => pad + (i * (w - pad - 8)) / Math.max(1, rows.length - 1))
  const yFor = (v: number) => h - pad - v * (h - pad - 8) // domain 0..1
  const line = (key: string) =>
    rows.map((r, i) => `${i ? 'L' : 'M'}${xs[i].toFixed(1)},${yFor(r[key] ?? 0).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" role="img" aria-label="skill by lead time">
      <Axes w={w} h={h} pad={pad} />
      {[0.25, 0.5, 0.75].map((g) => (
        <line key={g} x1={pad} y1={yFor(g)} x2={w - 4} y2={yFor(g)} className="grid" />
      ))}
      {[0, 0.5, 1].map((g) => (
        <text key={g} x={pad - 6} y={yFor(g) + 3} className="tick" textAnchor="end">{g}</text>
      ))}
      <path d={line('f2')} className="series series-f2" />
      <path d={line('pr_auc')} className="series series-pr" />
      {rows.map((r, i) => (
        <g key={i}>
          <circle cx={xs[i]} cy={yFor(r.f2 ?? 0)} r={3} className="dot-f2" />
          <text x={xs[i]} y={h - pad + 14} className="tick" textAnchor="middle">{r.horizon}</text>
        </g>
      ))}
      <text x={(w + pad) / 2} y={h - 2} className="axis-label" textAnchor="middle">lead time (days ahead)</text>
    </svg>
  )
}

function Calibration({ bins }: { bins: any[] }) {
  const pts = bins.filter((b) => b.count > 0 && b.mean_pred != null && b.frac_pos != null)
  const w = 300, h = 240, pad = 34
  const max = Math.max(0.2, ...pts.flatMap((p) => [p.mean_pred, p.frac_pos])) * 1.1
  const X = (v: number) => pad + (v / max) * (w - pad - 8)
  const Y = (v: number) => h - pad - (v / max) * (h - pad - 8)
  const maxCount = Math.max(...pts.map((p) => p.count), 1)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" role="img" aria-label="calibration curve">
      <Axes w={w} h={h} pad={pad} />
      <line x1={X(0)} y1={Y(0)} x2={X(max)} y2={Y(max)} className="ideal-line" />
      <path d={pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.mean_pred).toFixed(1)},${Y(p.frac_pos).toFixed(1)}`).join(' ')} className="series series-cal" />
      {pts.map((p, i) => (
        <circle key={i} cx={X(p.mean_pred)} cy={Y(p.frac_pos)} r={3 + 5 * (p.count / maxCount)} className="dot-cal" />
      ))}
      <text x={(w + pad) / 2} y={h - 2} className="axis-label" textAnchor="middle">predicted prob</text>
      <text x={10} y={14} className="axis-label">observed</text>
    </svg>
  )
}

function ThresholdSweep({ sweep }: { sweep: any }) {
  const pts = sweep.points
  const w = 440, h = 200, pad = 34
  const tmax = Math.max(...pts.map((p: any) => p.threshold), 0.1)
  const X = (t: number) => pad + (t / tmax) * (w - pad - 8)
  const Y = (v: number) => h - pad - v * (h - pad - 8)
  const line = (key: string) =>
    pts.map((p: any, i: number) => `${i ? 'L' : 'M'}${X(p.threshold).toFixed(1)},${Y(p[key]).toFixed(1)}`).join(' ')
  const cx = X(sweep.chosen_threshold)
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" role="img" aria-label="threshold sweep">
      <Axes w={w} h={h} pad={pad} />
      {[0.5, 1].map((g) => (
        <text key={g} x={pad - 6} y={Y(g) + 3} className="tick" textAnchor="end">{g}</text>
      ))}
      <line x1={cx} y1={4} x2={cx} y2={h - pad} className="chosen-line" />
      <text x={cx + 4} y={14} className="chosen-label">thr {sweep.chosen_threshold}</text>
      <path d={line('precision')} className="series series-prec" />
      <path d={line('recall')} className="series series-rec" />
      <path d={line('f2')} className="series series-f2" />
      <text x={(w + pad) / 2} y={h - 2} className="axis-label" textAnchor="middle">threshold</text>
    </svg>
  )
}

function FeatureImportance({ top }: { top: any[] }) {
  const items = top.slice(0, 12)
  const max = Math.max(...items.map((d) => d.importance), 1)
  return (
    <div className="fi-list">
      {items.map((d) => (
        <div className="fi-row" key={d.feature}>
          <span className="fi-name" title={d.feature}>{d.feature}</span>
          <span className="fi-bar-wrap">
            <span className="fi-bar" style={{ width: `${(d.importance / max) * 100}%` }} />
          </span>
        </div>
      ))}
    </div>
  )
}

function SliceTable({ rows, label }: { rows: any[]; label: string }) {
  return (
    <table className="slice-table tnum">
      <thead>
        <tr>
          <th className="slice-name">{label}</th>
          <th>F2</th><th>recall</th><th>prec</th><th>base</th><th>n+</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td className="slice-name" title={r.region}>{r.province ?? r.region}{r.province && r.region ? <span className="slice-sub"> · {r.region}</span> : null}</td>
            <td><span className="f2-pill" style={{ background: perfColor(r.f2) }}>{f3(r.f2)}</span></td>
            <td>{f3(r.recall)}</td>
            <td>{f3(r.precision)}</td>
            <td>{pct(r.base_rate)}</td>
            <td className="muted">{r.n_pos}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ---- main ------------------------------------------------------------------
export default function ModelReport() {
  const [d, setD] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await fetch(`${API_BASE}/api/model-report`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setD(await r.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const available = d?.available && d?.headline
  if (!available) {
    return (
      <section className="report">
        <div className="report-head">
          <div>
            <div className="report-eyebrow">model diagnostics</div>
            <h2 className="report-title">Deep-dive</h2>
          </div>
          <button className="btn btn-refresh" onClick={() => void load()} disabled={loading}>
            {loading ? 'loading…' : 'refresh'}
          </button>
        </div>
        <div className="lb-empty">
          {error ? `could not load report: ${error}` : (
            <>no report yet — run <code>scripts/model_report.py</code> to generate diagnostics</>
          )}
        </div>
      </section>
    )
  }

  const h = d.headline, c = d.confusion, b = d.baselines, sp = d.split
  const cards = [
    { k: 'F2', v: f3(h.f2), sub: `vs clim ${f3(b.climatology.f2)} · persist ${f3(b.persistence.f2)}`, hot: true },
    { k: 'recall', v: f3(h.recall), sub: 'caught heatwaves' },
    { k: 'precision', v: f3(h.precision), sub: 'alarm purity' },
    { k: 'Brier skill', v: f3(h.brier_skill_score), sub: 'vs climatology' },
  ]

  return (
    <section className="report">
      <div className="report-head">
        <div>
          <div className="report-eyebrow">model diagnostics · what to fix next</div>
          <h2 className="report-title">{d.model} <span className="report-title-dim">deep-dive</span></h2>
          <div className="report-note">{d.note}</div>
        </div>
        <button className="btn btn-refresh" onClick={() => void load()} disabled={loading}>
          {loading ? 'loading…' : 'refresh'}
        </button>
      </div>

      <div className="report-meta">
        {d.git_sha && <span className="chip">commit {d.git_sha}</span>}
        <span className="chip">{d.dataset?.n_provinces} provinces</span>
        <span className="chip">{d.dataset?.rows_frame?.toLocaleString()} rows</span>
        <span className="chip">train ≤{sp?.train?.replace('<=', '')} · val {sp?.val} · test {sp?.test}</span>
        <span className="chip">test base rate {pct(sp?.test_pos_rate)}</span>
        {d.generated_at && <span className="chip chip-dim">{d.generated_at.replace('T', ' ').replace('+00:00', 'Z')}</span>}
      </div>

      <div className="metric-grid">
        {cards.map((m) => (
          <div className={`metric-card-lg${m.hot ? ' metric-hot' : ''}`} key={m.k}>
            <div className="metric-value-lg tnum">{m.v}</div>
            <div className="metric-k">{m.k}</div>
            <div className="metric-compare">{m.sub}</div>
          </div>
        ))}
      </div>

      {/* CENTERPIECE: error analysis */}
      <div className="report-block">
        <div className="block-head">
          <h3>Error analysis — where it fails <span className="split-tag">test 2025</span></h3>
        </div>
        <div className="report-row report-row-2">
          <div className="card">
            <div className="card-title">skill by lead time</div>
            <PerHorizon rows={d.per_horizon.rows} />
            <div className="legend"><span className="lg lg-f2">F2</span><span className="lg lg-pr">PR-AUC</span></div>
          </div>
          <div className="card">
            <div className="card-title">weakest regions (sorted by F2)</div>
            <SliceTable rows={d.slices.by_region} label="region" />
          </div>
        </div>
        <div className="card">
          <div className="card-title">
            worst provinces (n+ ≥ {d.slices.min_pos}) — prioritize these for the next iteration
          </div>
          <SliceTable rows={d.slices.worst_provinces} label="province" />
        </div>
      </div>

      <div className="report-row report-row-2">
        <div className="card">
          <div className="card-title">confusion @ threshold {c.threshold} <span className="split-tag">test 2025</span></div>
          <div className="confusion-grid">
            <div className="cm cm-tp"><span className="cm-n tnum">{c.tp.toLocaleString()}</span><span className="cm-l">true positive</span></div>
            <div className="cm cm-fn"><span className="cm-n tnum">{c.fn.toLocaleString()}</span><span className="cm-l">missed (FN)</span></div>
            <div className="cm cm-fp"><span className="cm-n tnum">{c.fp.toLocaleString()}</span><span className="cm-l">false alarm (FP)</span></div>
            <div className="cm cm-tn"><span className="cm-n tnum">{c.tn.toLocaleString()}</span><span className="cm-l">true negative</span></div>
          </div>
          <div className="cm-note">recall {pct(h.recall)} · precision {pct(h.precision)} — recall-leaning operating point (F2)</div>
        </div>
        <div className="card">
          <div className="card-title">calibration <span className="split-tag">test 2025</span></div>
          <Calibration bins={d.calibration.bins} />
          <div className="legend"><span className="lg lg-ideal">ideal</span><span className="lg lg-cal">model</span> · dot size = count</div>
        </div>
      </div>

      <div className="report-row report-row-2">
        <div className="card">
          <div className="card-title">operating point — threshold sweep <span className="split-tag">validation 2024</span></div>
          <ThresholdSweep sweep={d.threshold_sweep} />
          <div className="legend"><span className="lg lg-prec">precision</span><span className="lg lg-rec">recall</span><span className="lg lg-f2">F2</span></div>
        </div>
        <div className="card">
          <div className="card-title">feature importance (gain)</div>
          <FeatureImportance top={d.feature_importance.top} />
        </div>
      </div>
    </section>
  )
}
