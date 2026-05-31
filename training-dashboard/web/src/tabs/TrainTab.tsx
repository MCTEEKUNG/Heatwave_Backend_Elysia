import type { TrainerKind } from '../protocol'
import type { UiState } from '../ws'
import Controls from '../components/Controls'
import ProgressBar from '../components/ProgressBar'
import Eta from '../components/Eta'
import SpeedChart from '../components/SpeedChart'
import LogPanel from '../components/LogPanel'
import MetricsPanel from '../components/MetricsPanel'
import LeaderboardPanel from '../components/LeaderboardPanel'
import RunHistory from '../components/RunHistory'
import ModelReport from '../components/ModelReport'
import FolderIcon from '../components/FolderIcon'

const API_BASE = 'http://127.0.0.1:8000'

export default function TrainTab({
  state, trainer, setTrainer, onStart, onStop, connected, running, refreshSignal,
}: {
  state: UiState
  trainer: TrainerKind
  setTrainer: (t: TrainerKind) => void
  onStart: (config?: Record<string, number>) => void
  onStop: () => void
  connected: boolean
  running: boolean
  refreshSignal: number
}) {
  const saved = state.metrics?.saved as
    | { name: string; file: string; path: string; size_kb: number }
    | undefined
  return (
    <>
      <Controls
        trainer={trainer}
        onTrainerChange={setTrainer}
        onStart={onStart}
        onStop={onStop}
        running={running}
        connected={connected}
      />
      <ProgressBar progress={state.progress} step={state.step} total={state.total_steps} />
      <div className="status-row">
        <Eta seconds={state.eta_seconds} />
        <span className="status-state" data-state={state.state}>state: {state.state}</span>
        {state.message ? <span className="status-message">{state.message}</span> : null}
      </div>
      <div className="panels">
        <SpeedChart history={state.speedHistory} current={state.speed_per_sec} />
        <MetricsPanel metrics={state.metrics} />
      </div>
      {state.state === 'done' && saved ? (
        <div className="saved-banner">
          <span className="saved-check" aria-hidden="true">✓</span>
          <span>saved model <code>{saved.path}</code> ({saved.size_kb} KB)</span>
          <button
            className="btn btn-refresh folder-btn"
            title="Open the models folder in your file explorer"
            onClick={() => { void fetch(`${API_BASE}/api/reveal-models`, { method: 'POST' }) }}
          >
            <FolderIcon /> open folder
          </button>
        </div>
      ) : null}
      <LogPanel logs={state.logs} />
      <LeaderboardPanel refreshSignal={refreshSignal} />
      <RunHistory refreshSignal={refreshSignal} />
      <ModelReport />
    </>
  )
}
