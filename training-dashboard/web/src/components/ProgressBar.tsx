interface ProgressBarProps {
  progress: number
  step: number
  total: number
}

export default function ProgressBar({ progress, step, total }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, progress))
  return (
    <div className="progress">
      <div
        className="progress-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-meta">
        <span className="progress-pct">{pct.toFixed(0)}%</span>
        <span className="progress-steps">
          step {step.toLocaleString()} / {total.toLocaleString()}
        </span>
      </div>
    </div>
  )
}
