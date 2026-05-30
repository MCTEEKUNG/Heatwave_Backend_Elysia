// FROZEN PROTOCOL CONTRACT — field names match the server agent's spec exactly.

// Trainers offered in the dashboard. The server registry is the source of
// truth; this list mirrors it with human labels for the dropdown.
export const TRAINERS = [
  { value: 'simulated', label: 'Simulated (demo)' },
  { value: 'lgbm', label: 'LightGBM — production' },
  { value: 'balanced_rf', label: 'Balanced Random Forest' },
  { value: 'random_forest', label: 'Random Forest' },
  { value: 'xgboost', label: 'XGBoost' },
  { value: 'catboost', label: 'CatBoost' },
  { value: 'mlp', label: 'MLP — neural net (slow)' },
] as const

export type TrainerKind = (typeof TRAINERS)[number]['value']

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
