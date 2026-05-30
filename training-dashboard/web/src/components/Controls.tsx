import { useState } from 'react'
import { TRAINERS, type TrainerKind } from '../protocol'

interface ControlsProps {
  trainer: TrainerKind
  onTrainerChange: (t: TrainerKind) => void
  onStart: (config?: Record<string, number>) => void
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
  const [nEstimators, setNEstimators] = useState('')
  const [maxDepth, setMaxDepth] = useState('')
  const [learningRate, setLearningRate] = useState('')

  const showHp = trainer !== 'simulated'

  function handleStart() {
    if (!showHp) {
      onStart()
      return
    }
    const config: Record<string, number> = {}
    const ne = parseFloat(nEstimators)
    if (nEstimators !== '' && isFinite(ne)) config.n_estimators = ne
    const md = parseFloat(maxDepth)
    if (maxDepth !== '' && isFinite(md)) config.max_depth = md
    const lr = parseFloat(learningRate)
    if (learningRate !== '' && isFinite(lr)) config.learning_rate = lr
    onStart(Object.keys(config).length > 0 ? config : undefined)
  }

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
        {TRAINERS.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </select>
      {showHp && (
        <>
          <label className="control-label" htmlFor="hp-n-estimators">
            n_estimators:
          </label>
          <input
            id="hp-n-estimators"
            type="number"
            className="hp-input"
            value={nEstimators}
            disabled={running}
            placeholder="default"
            onChange={(e) => setNEstimators(e.target.value)}
          />
          <label className="control-label" htmlFor="hp-max-depth">
            max_depth:
          </label>
          <input
            id="hp-max-depth"
            type="number"
            className="hp-input"
            value={maxDepth}
            disabled={running}
            placeholder="default"
            onChange={(e) => setMaxDepth(e.target.value)}
          />
          <label className="control-label" htmlFor="hp-learning-rate">
            learning_rate:
          </label>
          <input
            id="hp-learning-rate"
            type="number"
            step="any"
            className="hp-input"
            value={learningRate}
            disabled={running}
            placeholder="default"
            onChange={(e) => setLearningRate(e.target.value)}
          />
        </>
      )}
      <button
        type="button"
        className="btn btn-start"
        onClick={handleStart}
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
