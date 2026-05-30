interface SpeedChartProps {
  history: number[]
  current: number
}

const WIDTH = 320
const HEIGHT = 80
const PAD = 4

/**
 * Lightweight sparkline of speed_per_sec over time using inline SVG only.
 * No charting library by design.
 */
export default function SpeedChart({ history, current }: SpeedChartProps) {
  const data = history.length > 0 ? history : current > 0 ? [current] : []

  let path = ''
  if (data.length >= 2) {
    const max = Math.max(...data, 1)
    const min = Math.min(...data)
    const range = max - min || 1
    const innerW = WIDTH - PAD * 2
    const innerH = HEIGHT - PAD * 2
    path = data
      .map((v, i) => {
        const x = PAD + (i / (data.length - 1)) * innerW
        const y = PAD + innerH - ((v - min) / range) * innerH
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }

  return (
    <div className="card sparkline-card">
      <div className="card-title">
        speed <span className="speed-now">{current.toFixed(0)} /s</span>
      </div>
      <svg
        className="sparkline"
        width="100%"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Speed sparkline, latest ${current.toFixed(0)} per second`}
      >
        {path ? (
          <path d={path} className="sparkline-line" fill="none" />
        ) : (
          <text x={WIDTH / 2} y={HEIGHT / 2} className="sparkline-empty" textAnchor="middle">
            no data yet
          </text>
        )}
      </svg>
    </div>
  )
}
