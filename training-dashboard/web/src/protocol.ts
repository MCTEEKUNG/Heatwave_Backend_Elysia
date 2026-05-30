// FROZEN PROTOCOL CONTRACT — field names match the server agent's spec exactly.

export type TrainerKind = 'simulated' | 'lgbm'

export type RunState = 'idle' | 'running' | 'done' | 'error'

export type LogLevel = 'info' | 'warn' | 'error'

// Client -> server frames
export interface StartCommand {
  command: 'start'
  trainer: TrainerKind
  config?: {
    total_steps?: number
    speed_per_sec?: number
  }
}

export interface StopCommand {
  command: 'stop'
}

export type ClientCommand = StartCommand | StopCommand

// Server -> client frames
export interface StatusEvent {
  type: 'status'
  state: RunState
  progress: number
  step: number
  total_steps: number
  speed_per_sec: number
  eta_seconds: number | null
  message: string
  ts: number
}

export interface LogEvent {
  type: 'log'
  level: LogLevel
  message: string
  ts: number
}

export interface MetricsEvent {
  type: 'metrics'
  report: Record<string, unknown>
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type ServerEvent = StatusEvent | LogEvent | MetricsEvent | ErrorEvent
