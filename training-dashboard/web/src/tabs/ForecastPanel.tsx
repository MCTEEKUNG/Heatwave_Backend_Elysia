import { useEffect, useMemo, useState } from 'react'
import './ForecastPanel.css'
import {
  fetchProvinces,
  fetchForecastMap,
  fetchProvinceSeries,
  riskColor,
  type Province,
  type ForecastMap,
  type ProvinceSeries,
} from '../forecast'

// ---------------------------------------------------------------------------
// Legend entries (pure data — no fabricated forecast values)
// ---------------------------------------------------------------------------

const LEGEND: { label: string; risk: string }[] = [
  { label: 'No data', risk: '' },
  { label: 'Low', risk: 'low' },
  { label: 'Moderate', risk: 'moderate' },
  { label: 'High', risk: 'high' },
  { label: 'Extreme', risk: 'extreme' },
]

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

export default function ForecastPanel() {
  // --- provinces (always loads from real CSV via API) ----------------------
  const [provinces, setProvinces] = useState<Province[]>([])
  const [provincesLoading, setProvincesLoading] = useState(true)
  const [provincesError, setProvincesError] = useState<string | null>(null)

  // --- lead selector -------------------------------------------------------
  const [lead, setLead] = useState(1)

  // --- map data (from DB — may be unavailable) -----------------------------
  const [mapData, setMapData] = useState<ForecastMap | null>(null)
  const [mapLoading, setMapLoading] = useState(false)

  // --- selected province + detail series -----------------------------------
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [series, setSeries] = useState<ProvinceSeries | null>(null)
  const [seriesLoading, setSeriesLoading] = useState(false)

  // Load provinces once on mount
  useEffect(() => {
    let alive = true
    setProvincesLoading(true)
    setProvincesError(null)
    fetchProvinces()
      .then((data) => {
        if (alive) setProvinces(data)
      })
      .catch((err: unknown) => {
        if (alive) setProvincesError(String(err))
      })
      .finally(() => {
        if (alive) setProvincesLoading(false)
      })
    return () => { alive = false }
  }, [])

  // Load map whenever lead changes
  useEffect(() => {
    let alive = true
    setMapLoading(true)
    fetchForecastMap(lead)
      .then((data) => {
        if (alive) setMapData(data)
      })
      .catch(() => {
        if (alive) {
          setMapData({ available: false, reason: 'Network error reaching server', cells: {} })
        }
      })
      .finally(() => {
        if (alive) setMapLoading(false)
      })
  }, [lead])

  // Load detail series when a province is selected
  useEffect(() => {
    if (selectedId === null) { setSeries(null); return }
    let alive = true
    setSeriesLoading(true)
    fetchProvinceSeries(selectedId)
      .then((data) => {
        if (alive) setSeries(data)
      })
      .catch(() => {
        if (alive) {
          setSeries({ available: false, reason: 'Network error reaching server', series: [] })
        }
      })
      .finally(() => {
        if (alive) setSeriesLoading(false)
      })
    return () => { alive = false }
  }, [selectedId])

  // Group provinces by region (stable order based on first appearance)
  const regionGroups = useMemo(() => {
    const order: string[] = []
    const groups: Record<string, Province[]> = {}
    for (const p of provinces) {
      if (!groups[p.region]) {
        groups[p.region] = []
        order.push(p.region)
      }
      groups[p.region].push(p)
    }
    return order.map((r) => ({ region: r, provinces: groups[r] }))
  }, [provinces])

  // Selected province name for the detail header
  const selectedProvince = useMemo(
    () => provinces.find((p) => p.id === selectedId) ?? null,
    [provinces, selectedId],
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="forecast-panel">
      {/* Controls */}
      <div className="forecast-controls">
        <label htmlFor="forecast-lead-select">Lead day:</label>
        <select
          id="forecast-lead-select"
          className="forecast-lead-select"
          value={lead}
          onChange={(e) => setLead(Number(e.target.value))}
        >
          {[1, 2, 3, 4, 5, 6, 7].map((k) => (
            <option key={k} value={k}>Day +{k}</option>
          ))}
        </select>

        {mapData?.available && mapData.generated_at && (
          <span className="forecast-meta">
            Snapshot: {new Date(mapData.generated_at).toLocaleString()}
          </span>
        )}
        {mapLoading && <span className="forecast-loading">Loading forecast data…</span>}
      </div>

      {/* Provinces loading error */}
      {provincesLoading && (
        <p className="forecast-loading">Loading provinces…</p>
      )}
      {provincesError && (
        <div className="forecast-banner forecast-banner--error" role="alert">
          Could not load province list from server: {provincesError}
        </div>
      )}

      {/* DB unavailable banner — honest, no fabricated data */}
      {!mapLoading && mapData && !mapData.available && (
        <div className="forecast-banner forecast-banner--warning" role="status">
          <strong>No forecast data available.</strong>{' '}
          {mapData.reason
            ? `Reason: ${mapData.reason}.`
            : 'DB unreachable or daily forecast job has not yet run.'}{' '}
          Province grid is shown in neutral colour. Populate the grid by running
          the daily forecast pipeline and ensuring the DB is reachable.
        </div>
      )}

      {/* Legend */}
      <div className="forecast-legend" aria-label="Risk level legend">
        {LEGEND.map(({ label, risk }) => (
          <div key={label} className="forecast-legend-item">
            <span
              className="forecast-legend-swatch"
              style={{ backgroundColor: riskColor(risk || undefined) }}
            />
            <span>{label}</span>
          </div>
        ))}
      </div>

      {/* Main body: grid + detail */}
      {!provincesLoading && !provincesError && provinces.length > 0 && (
        <div className="forecast-body">
          {/* Province grid grouped by region */}
          <div className="forecast-grid" role="list" aria-label="Province forecast grid">
            {regionGroups.map(({ region, provinces: group }) => (
              <div key={region} className="forecast-region-group">
                <p className="forecast-region-title">{region}</p>
                <div className="forecast-cells">
                  {group.map((p) => {
                    const cellData = mapData?.cells[String(p.id)]
                    const color = riskColor(cellData?.risk_level ?? undefined)
                    const isSelected = selectedId === p.id
                    return (
                      <div
                        key={p.id}
                        role="listitem"
                        className={`forecast-cell${isSelected ? ' forecast-cell--selected' : ''}`}
                        style={{ backgroundColor: color }}
                        title={
                          cellData
                            ? `${p.name_en} · ${cellData.risk_level ?? 'unknown'} · ${
                                cellData.probability != null
                                  ? (cellData.probability * 100).toFixed(0) + '% prob'
                                  : 'no prob'
                              }`
                            : `${p.name_en} — no data`
                        }
                        onClick={() => setSelectedId(isSelected ? null : p.id)}
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setSelectedId(isSelected ? null : p.id)
                          }
                        }}
                        aria-label={
                          cellData
                            ? `${p.name_en}, risk ${cellData.risk_level ?? 'unknown'}`
                            : `${p.name_en}, no data`
                        }
                        aria-pressed={isSelected}
                      >
                        {p.code}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Detail panel */}
          <div className="forecast-detail">
            {selectedProvince ? (
              <>
                <h3>{selectedProvince.name_en}</h3>
                {seriesLoading && (
                  <p className="forecast-detail-loading">Loading series…</p>
                )}
                {!seriesLoading && series && !series.available && (
                  <p className="forecast-detail-empty">
                    No series data available.
                    {series.reason ? ` (${series.reason})` : ''}
                  </p>
                )}
                {!seriesLoading && series?.available && series.series.length === 0 && (
                  <p className="forecast-detail-empty">No horizon data for this province.</p>
                )}
                {!seriesLoading && series?.available && series.series.length > 0 && (
                  <div className="forecast-series" role="list" aria-label="Forecast series">
                    {series.series.map((pt) => {
                      const pct = pt.probability != null
                        ? Math.round(pt.probability * 100)
                        : null
                      return (
                        <div key={pt.horizon_days} className="forecast-series-row" role="listitem">
                          <div className="forecast-series-label">
                            <span>Day +{pt.horizon_days} · {pt.target_date}</span>
                            <span>
                              {pt.risk_level ?? 'unknown'}
                              {pct != null ? ` · ${pct}%` : ''}
                            </span>
                          </div>
                          <div className="forecast-series-bar-track">
                            <div
                              className="forecast-series-bar-fill"
                              style={{
                                width: pct != null ? `${pct}%` : '0%',
                                backgroundColor: riskColor(pt.risk_level ?? undefined),
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </>
            ) : (
              <p className="forecast-detail-empty">
                Click a province cell to see its forecast series.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
