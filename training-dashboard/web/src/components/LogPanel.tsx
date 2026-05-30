import { useEffect, useRef } from 'react'
import type { LogEntry } from '../ws'

export default function LogPanel({ logs }: { logs: LogEntry[] }) {
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [logs])

  return (
    <div className="card log-card">
      <div className="card-title">log</div>
      <div className="log-scroll">
        {logs.length === 0 ? (
          <div className="log-empty">no log messages yet</div>
        ) : (
          logs.map((entry, i) => (
            <div key={i} className={`log-line log-${entry.level}`}>
              <span className="log-level">{entry.level.toUpperCase()}</span>
              <span className="log-msg">{entry.message}</span>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
