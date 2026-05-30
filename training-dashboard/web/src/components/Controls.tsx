import type { TrainerKind } from '../protocol'

interface ControlsProps {
  trainer: TrainerKind
  onTrainerChange: (t: TrainerKind) => void
  onStart: () => void
  onStop: () => void
  running: boolean
  connected: boolean
}

export default function Controls({
  trainer,
  onTrainerChange,
  onStart,
  onStop,
  running,
  connected,
}: ControlsProps) {
  return (
    <div className="controls">
      <label className="control-label" htmlFor="trainer-select">
        Trainer:
      </label>
      <select
        id="trainer-select"
        className="trainer-select"
        value={trainer}
        disabled={running}
        onChange={(e) => onTrainerChange(e.target.value as TrainerKind)}
      >
        <option value="simulated">simulated</option>
        <option value="lgbm">lgbm</option>
      </select>
      <button
        type="button"
        className="btn btn-start"
        onClick={onStart}
        disabled={running || !connected}
      >
        Start
      </button>
      <button
        type="button"
        className="btn btn-stop"
        onClick={onStop}
        disabled={!running || !connected}
      >
        Stop
      </button>
    </div>
  )
}
