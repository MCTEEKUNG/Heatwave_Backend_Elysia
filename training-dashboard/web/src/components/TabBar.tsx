export type TabKey = 'pipeline' | 'train' | 'forecast' | 'ops' | 'lab'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'train', label: 'Train' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'ops', label: 'Ops' },
  { key: 'lab', label: 'Lab' },
]

export default function TabBar({
  active,
  onSelect,
}: {
  active: TabKey
  onSelect: (key: TabKey) => void
}) {
  return (
    <nav className="tab-bar" role="tablist" aria-label="Cockpit sections">
      {TABS.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          className={`tab ${active === t.key ? 'tab-active' : ''}`}
          onClick={() => onSelect(t.key)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}
