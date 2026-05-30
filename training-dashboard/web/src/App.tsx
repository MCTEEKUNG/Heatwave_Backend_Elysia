import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import './App.css'
import type { ServerEvent, TrainerKind } from './protocol'
import {
  initialState,
  reduce,
  setConnection,
  WsClient,
  type ConnectionState,
  type UiState,
} from './ws'
import Controls from './components/Controls'
import ProgressBar from './components/ProgressBar'
import Eta from './components/Eta'
import SpeedChart from './components/SpeedChart'
import LogPanel from './components/LogPanel'
import MetricsPanel from './components/MetricsPanel'
import LeaderboardPanel from './components/LeaderboardPanel'
import ModelReport from './components/ModelReport'
import Toast, { type ToastMessage } from './components/Toast'

type Action =
  | { kind: 'event'; event: ServerEvent }
  | { kind: 'connection'; connection: ConnectionState }

function appReducer(state: UiState, action: Action): UiState {
  if (action.kind === 'connection') return setConnection(state, action.connection)
  return reduce(state, action.event)
}

const API_BASE = 'http://127.0.0.1:8000'

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  connecting: 'connecting…',
  open: 'connected',
  closed: 'disconnected',
}

export default function App() {
  const [state, dispatch] = useReducer(appReducer, initialState)
  const [trainer, setTrainer] = useState<TrainerKind>('simulated')
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const clientRef = useRef<WsClient | null>(null)
  const nonceRef = useRef(0)
  const prevRunState = useRef(state.state)

  useEffect(() => {
    const client = new WsClient()
    clientRef.current = client
    const offEvent = client.onEvent((event) => dispatch({ kind: 'event', event }))
    const offConn = client.onConnection((connection) =>
      dispatch({ kind: 'connection', connection }),
    )
    client.connect()
    return () => {
      offEvent()
      offConn()
      client.close()
      clientRef.current = null
    }
  }, [])

  // Fire toast + notification on transitions into done / error.
  useEffect(() => {
    const prev = prevRunState.current
    if (state.state !== prev) {
      if (state.state === 'done') {
        nonceRef.current += 1
        setToast({ kind: 'success', text: 'Training complete', nonce: nonceRef.current })
      } else if (state.state === 'error') {
        nonceRef.current += 1
        setToast({
          kind: 'error',
          text: state.error ?? state.message ?? 'Training error',
          nonce: nonceRef.current,
        })
      }
      prevRunState.current = state.state
    }
  }, [state.state, state.error, state.message])

  const connected = state.connection === 'open'
  const running = state.state === 'running'

  const indicatorClass = useMemo(() => {
    if (state.connection === 'open') return 'dot-open'
    if (state.connection === 'connecting') return 'dot-connecting'
    return 'dot-closed'
  }, [state.connection])

  function handleStart() {
    clientRef.current?.start(trainer)
  }
  function handleStop() {
    clientRef.current?.stop()
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Heatwave Training Dashboard</h1>
        <div className={`conn-indicator ${indicatorClass}`}>
          <span className="conn-dot" aria-hidden="true">
            ●
          </span>
          <span className="conn-text">{CONNECTION_LABEL[state.connection]}</span>
        </div>
      </header>

      <Controls
        trainer={trainer}
        onTrainerChange={setTrainer}
        onStart={handleStart}
        onStop={handleStop}
        running={running}
        connected={connected}
      />

      <ProgressBar progress={state.progress} step={state.step} total={state.total_steps} />

      <div className="status-row">
        <Eta seconds={state.eta_seconds} />
        <span className="status-state" data-state={state.state}>
          state: {state.state}
        </span>
        {state.message ? <span className="status-message">{state.message}</span> : null}
      </div>

      <div className="panels">
        <SpeedChart history={state.speedHistory} current={state.speed_per_sec} />
        <MetricsPanel metrics={state.metrics} />
      </div>

      {(() => {
        const saved = state.metrics?.saved as
          | { name: string; file: string; path: string; size_kb: number }
          | undefined
        if (state.state !== 'done' || !saved) return null
        return (
          <div className="saved-banner">
            <span className="saved-check" aria-hidden="true">✓</span>
            <span>
              saved model <code>{saved.path}</code> ({saved.size_kb} KB)
            </span>
            <a className="btn btn-refresh" href={`${API_BASE}/api/model-file/${saved.name}`}>
              download .pkl
            </a>
          </div>
        )
      })()}

      <LogPanel logs={state.logs} />

      <LeaderboardPanel />

      <ModelReport />

      <Toast message={toast} />
    </div>
  )
}
