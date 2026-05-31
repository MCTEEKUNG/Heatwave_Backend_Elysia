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
import TabBar, { type TabKey } from './components/TabBar'
import TrainTab from './tabs/TrainTab'
import LabPanel from './tabs/LabPanel'
import StubTab from './tabs/StubTab'
import Toast, { type ToastMessage } from './components/Toast'

type Action =
  | { kind: 'event'; event: ServerEvent }
  | { kind: 'connection'; connection: ConnectionState }

function appReducer(state: UiState, action: Action): UiState {
  if (action.kind === 'connection') return setConnection(state, action.connection)
  return reduce(state, action.event)
}

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  connecting: 'connecting…',
  open: 'connected',
  closed: 'disconnected',
}

export default function App() {
  const [state, dispatch] = useReducer(appReducer, initialState)
  const [trainer, setTrainer] = useState<TrainerKind>('simulated')
  const [toast, setToast] = useState<ToastMessage | null>(null)
  const [refreshSignal, setRefreshSignal] = useState(0)
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
        setRefreshSignal((s) => s + 1)
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

  function handleStart(config?: Record<string, number>) {
    clientRef.current?.start(trainer, config)
  }
  function handleStop() {
    clientRef.current?.stop()
  }

  const [tab, setTab] = useState<TabKey>(
    (window.location.hash.replace('#', '') as TabKey) || 'train',
  )
  function selectTab(k: TabKey) {
    setTab(k)
    window.location.hash = k
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Heatwave Cockpit</h1>
        <div className={`conn-indicator ${indicatorClass}`}>
          <span className="conn-dot" aria-hidden="true">●</span>
          <span className="conn-text">{CONNECTION_LABEL[state.connection]}</span>
        </div>
      </header>

      <TabBar active={tab} onSelect={selectTab} />

      {tab === 'train' && (
        <TrainTab
          state={state} trainer={trainer} setTrainer={setTrainer}
          onStart={handleStart} onStop={handleStop}
          connected={connected} running={running} refreshSignal={refreshSignal}
        />
      )}
      {tab === 'lab' && <LabPanel connected={connected} />}
      {tab === 'pipeline' && <StubTab title="Pipeline" />}
      {tab === 'forecast' && <StubTab title="Forecast" />}
      {tab === 'ops' && <StubTab title="Ops" />}

      <Toast message={toast} />
    </div>
  )
}
