const DASH = '—' // em dash

/**
 * Format an ETA in seconds into a compact human string.
 *   108  -> "1 m 48 s"
 *   8100 -> "2 h 15 m"   (seconds omitted once hours are present)
 *   0 / null / negative / non-finite -> "—"
 * Exported as a pure function for unit testing.
 */
export function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) {
    return DASH
  }
  const total = Math.floor(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60

  if (h > 0) {
    return `${h} h ${m} m`
  }
  if (m > 0) {
    return `${m} m ${s} s`
  }
  return `${s} s`
}

export default function Eta({ seconds }: { seconds: number | null }) {
  return (
    <span className="eta-value" title="Estimated time remaining">
      ETA ~{formatEta(seconds)}
    </span>
  )
}
