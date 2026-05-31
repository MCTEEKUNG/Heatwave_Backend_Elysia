import { useEffect, useState } from 'react'
import { fetchPipelineStatus, stageTone, type PipelineStage } from '../pipeline'
import './PipelinePanel.css'

export default function PipelinePanel({ connected }: { connected: boolean }) {
  const [stages, setStages] = useState<PipelineStage[] | null>(null)

  useEffect(() => {
    let alive = true

    const tick = async () => {
      try {
        const data = await fetchPipelineStatus()
        if (alive) setStages(data.stages)
      } catch {
        /* server down — keep last known state */
      }
    }

    void tick()
    const id = setInterval(tick, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  function handleRun(stageName: string) {
    window.dispatchEvent(
      new CustomEvent('cockpit-run-stage', { detail: { name: stageName } }),
    )
  }

  function handleOpen(link: string) {
    window.location.hash = '#' + link
  }

  return (
    <div className="pipeline">
      <h2 className="pipeline-title">Pipeline</h2>

      {stages === null ? (
        <p className="pipeline-loading">Loading pipeline status…</p>
      ) : stages.length === 0 ? (
        <p className="pipeline-empty">No pipeline stages available.</p>
      ) : (
        <div className="pipeline-flow" role="list">
          {stages.map((stage, idx) => (
            <div key={stage.key} className="pipeline-step" role="listitem">
              <StageCard
                stage={stage}
                connected={connected}
                onRun={handleRun}
                onOpen={handleOpen}
              />
              {idx < stages.length - 1 && (
                <div className="pipeline-arrow" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M5 12h14M13 6l6 6-6 6"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface StageCardProps {
  stage: PipelineStage
  connected: boolean
  onRun: (stageName: string) => void
  onOpen: (link: string) => void
}

function StageCard({ stage, connected, onRun, onOpen }: StageCardProps) {
  const tone = stageTone(stage.status)

  return (
    <div className={`stage-card ${tone}`}>
      <div className="stage-label">{stage.label}</div>

      {stage.status && (
        <div className={`stage-status-badge stage-badge-${stage.status}`}>
          {stage.status}
        </div>
      )}

      {stage.detail && (
        <div className="stage-detail">{stage.detail}</div>
      )}

      <div className="stage-actions">
        {stage.runnable && stage.stage && (
          <button
            className="btn btn-primary stage-run-btn"
            disabled={!connected}
            title={connected ? `Run ${stage.label}` : 'Connect to server first'}
            onClick={() => onRun(stage.stage!)}
          >
            Run
          </button>
        )}

        {stage.link && (
          <button
            className="btn stage-open-btn"
            onClick={() => onOpen(stage.link!)}
          >
            Open {stage.link}
          </button>
        )}
      </div>
    </div>
  )
}
