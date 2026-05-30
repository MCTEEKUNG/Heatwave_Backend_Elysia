function MetricsNode({ k, value }: { k: string; value: unknown }) {
  const isObject =
    value !== null && typeof value === 'object' && !Array.isArray(value)
  const isArray = Array.isArray(value)

  if (isObject) {
    const entries = Object.entries(value as Record<string, unknown>)
    return (
      <div className="metric-node">
        <span className="metric-key">{k}</span>
        <div className="metric-children">
          {entries.map(([ck, cv]) => (
            <MetricsNode key={ck} k={ck} value={cv} />
          ))}
        </div>
      </div>
    )
  }

  if (isArray) {
    return (
      <div className="metric-node">
        <span className="metric-key">{k}</span>
        <div className="metric-children">
          {(value as unknown[]).map((cv, i) => (
            <MetricsNode key={i} k={`[${i}]`} value={cv} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="metric-leaf">
      <span className="metric-key">{k}</span>
      <span className="metric-val">{String(value)}</span>
    </div>
  )
}

export default function MetricsPanel({
  metrics,
}: {
  metrics: Record<string, unknown> | null
}) {
  return (
    <div className="card metrics-card">
      <div className="card-title">final metrics</div>
      <div className="metrics-body">
        {metrics ? (
          Object.entries(metrics).map(([k, v]) => (
            <MetricsNode key={k} k={k} value={v} />
          ))
        ) : (
          <div className="metrics-empty">no metrics yet</div>
        )}
      </div>
    </div>
  )
}
