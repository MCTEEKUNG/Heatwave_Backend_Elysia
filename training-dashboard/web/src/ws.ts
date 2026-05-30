import type {
  ClientCommand,
  LogLevel,
  RunState,
  ServerEvent,
  TrainerKind,
} from './protocol'

export const WS_URL = 'ws://127.0.0.1:8000/ws'

export type ConnectionState = 'connecting' | 'open' | 'closed'

export interface LogEntry {
  level: LogLevel
  message: string
  ts: number
}

export interface UiState {
  connection: ConnectionState
  state: RunState
  progress: number
  step: number
  total_steps: number
  speed_per_sec: number
  eta_seconds: number | null
  message: string
  logs: LogEntry[]
  speedHistory: number[]
  metrics: Record<string, unknown> | null
  error: string | null
}

export const initialState: UiState = {
  connection: 'connecting',
  state: 'idle',
  progress: 0,
  step: 0,
  total_steps: 0,
  speed_per_sec: 0,
  eta_seconds: null,
  message: '',
  logs: [],
  speedHistory: [],
  metrics: null,
  error: null,
}

const MAX_LOGS = 500
const MAX_SPEED_POINTS = 240

/**
 * Pure reducer that folds the four protocol event types into UI state.
 * Exported for unit testing — must stay free of side effects.
 *
 * Connection lifecycle is intentionally NOT handled here (it is not one of
 * the four protocol events); it is applied separately via `setConnection`.
 */
export function reduce(state: UiState, event: ServerEvent): UiState {
  switch (event.type) {
    case 'status':
      return {
        ...state,
        state: event.state,
        progress: event.progress,
        step: event.step,
        total_steps: event.total_steps,
        speed_per_sec: event.speed_per_sec,
        eta_seconds: event.eta_seconds,
        message: event.message,
        speedHistory: [...state.speedHistory, event.speed_per_sec].slice(
          -MAX_SPEED_POINTS,
        ),
        // a fresh successful status clears a prior transient error
        error: event.state === 'error' ? state.error : null,
      }
    case 'log':
      return {
        ...state,
        logs: [
          ...state.logs,
          { level: event.level, message: event.message, ts: event.ts },
        ].slice(-MAX_LOGS),
      }
    case 'metrics':
      // Setting metrics must NOT reset run state (it stays e.g. "done").
      return { ...state, metrics: event.report }
    case 'error':
      return { ...state, error: event.message }
    default:
      return state
  }
}

/** Apply a connection-state change. Kept out of `reduce` to keep it pure. */
export function setConnection(
  state: UiState,
  connection: ConnectionState,
): UiState {
  return { ...state, connection }
}

export type EventListener = (event: ServerEvent) => void
export type ConnectionListener = (connection: ConnectionState) => void

export interface WsClientOptions {
  url?: string
  /** Backoff schedule in ms; the last value is reused once exhausted. */
  backoff?: number[]
}

/**
 * WebSocket client that connects to the training server, auto-reconnects with
 * capped exponential backoff, lets callers send start/stop commands, and
 * dispatches parsed protocol events + connection-state changes to subscribers.
 */
export class WsClient {
  private url: string
  private backoff: number[]
  private attempt = 0
  private socket: WebSocket | null = null
  private closedByUser = false
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private eventListeners = new Set<EventListener>()
  private connectionListeners = new Set<ConnectionListener>()

  constructor(options: WsClientOptions = {}) {
    this.url = options.url ?? WS_URL
    this.backoff = options.backoff ?? [1000, 2000, 4000, 8000, 10000]
  }

  onEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener)
    return () => this.eventListeners.delete(listener)
  }

  onConnection(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener)
    return () => this.connectionListeners.delete(listener)
  }

  private emitEvent(event: ServerEvent) {
    for (const l of this.eventListeners) l(event)
  }

  private emitConnection(connection: ConnectionState) {
    for (const l of this.connectionListeners) l(connection)
  }

  connect(): void {
    this.closedByUser = false
    this.clearReconnect()
    this.emitConnection('connecting')

    let ws: WebSocket
    try {
      ws = new WebSocket(this.url)
    } catch {
      this.scheduleReconnect()
      return
    }
    this.socket = ws

    ws.onopen = () => {
      this.attempt = 0
      this.emitConnection('open')
    }

    ws.onmessage = (ev: MessageEvent) => {
      const parsed = this.parse(ev.data)
      if (parsed) this.emitEvent(parsed)
    }

    ws.onerror = () => {
      // onclose will follow and drive reconnection.
    }

    ws.onclose = () => {
      this.socket = null
      this.emitConnection('closed')
      if (!this.closedByUser) this.scheduleReconnect()
    }
  }

  private parse(data: unknown): ServerEvent | null {
    if (typeof data !== 'string') return null
    let obj: unknown
    try {
      obj = JSON.parse(data)
    } catch {
      return null
    }
    if (!obj || typeof obj !== 'object') return null
    const type = (obj as { type?: unknown }).type
    if (
      type === 'status' ||
      type === 'log' ||
      type === 'metrics' ||
      type === 'error'
    ) {
      return obj as ServerEvent
    }
    return null
  }

  private scheduleReconnect(): void {
    this.clearReconnect()
    const idx = Math.min(this.attempt, this.backoff.length - 1)
    const delay = this.backoff[idx]
    this.attempt += 1
    this.reconnectTimer = setTimeout(() => {
      if (!this.closedByUser) this.connect()
    }, delay)
  }

  private clearReconnect(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  send(command: ClientCommand): boolean {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(command))
      return true
    }
    return false
  }

  start(trainer: TrainerKind, config?: Record<string, number>): boolean {
    return this.send(config ? { command: 'start', trainer, config } : { command: 'start', trainer })
  }

  stop(): boolean {
    return this.send({ command: 'stop' })
  }

  /** Permanently close the socket and stop reconnecting. */
  close(): void {
    this.closedByUser = true
    this.clearReconnect()
    if (this.socket) {
      this.socket.onclose = null
      this.socket.close()
      this.socket = null
    }
    this.emitConnection('closed')
  }
}
