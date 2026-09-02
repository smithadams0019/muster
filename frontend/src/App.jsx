import { useEffect, useState } from 'react'
import * as V from './views.jsx'
import RightRail from './components/RightRail.jsx'
import DisruptionComposer from './components/DisruptionComposer.jsx'
import { useStore } from './store.js'
import {
  IconToday,
  IconDecisions,
  IconConsent,
  IconSchedule,
  IconTeam,
  IconAutonomy,
  IconTimeline,
  IconReceipts,
} from './icons.jsx'

const NAV_ITEMS = [
  { route: 'today', label: 'Today', icon: IconToday },
  { route: 'decisions', label: 'Decisions', icon: IconDecisions, badgeKey: 'decisions' },
  { route: 'consent', label: 'Consent', icon: IconConsent, badgeKey: 'consent' },
  { route: 'schedule', label: 'Schedule', icon: IconSchedule },
  { route: 'team', label: 'Team', icon: IconTeam },
  { route: 'autonomy', label: 'Autonomy', icon: IconAutonomy },
  { route: 'timeline', label: 'Timeline', icon: IconTimeline },
  { route: 'receipts', label: 'Receipts', icon: IconReceipts },
]

const SCREENS = {
  today: V.Today,
  decisions: V.Decisions,
  consent: V.Consent,
  schedule: V.Schedule,
  team: V.Team,
  autonomy: V.Autonomy,
  timeline: V.Timeline,
  receipts: V.Receipts,
}

function NavItem({ item, active, count, onClick }) {
  const Icon = item.icon
  return (
    <button
      type="button"
      className={`nav-item${active ? ' active' : ''}`}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
    >
      <span className="nav-icon">
        <Icon />
      </span>
      <span className="nav-label">
        {item.label}
        {Boolean(count) && <span className="nav-badge">{count}</span>}
      </span>
    </button>
  )
}

function Rail({ route, go, decisionsCount, consentCount, onCompose }) {
  return (
    <nav className="rail">
      <div className="rail-brand">M</div>
      <div className="rail-nav">
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.route}
            item={item}
            active={route === item.route}
            count={
              item.badgeKey === 'decisions'
                ? decisionsCount
                : item.badgeKey === 'consent'
                  ? consentCount
                  : 0
            }
            onClick={() => go(item.route)}
          />
        ))}
      </div>
      <button type="button" className="rail-primary" onClick={onCompose}>
        Report a disruption
      </button>
      <div className="rail-spacer" />
      <div className="operator-chip">
        <div className="operator-avatar">RK</div>
        <div className="operator-meta">
          <span className="operator-name">Roger Koranteng</span>
          <span className="operator-handle">@muster</span>
        </div>
        <span className="operator-more">···</span>
      </div>
    </nav>
  )
}

function Skeleton() {
  return (
    <div className="skeleton">
      <div className="skeleton-line" style={{ width: '40%' }} />
      <div className="skeleton-line" style={{ width: '90%' }} />
      <div className="skeleton-line" style={{ width: '85%' }} />
      <div className="skeleton-line" style={{ width: '70%' }} />
      <div className="skeleton-line" style={{ width: '80%' }} />
    </div>
  )
}

export default function App() {
  const route = useStore((s) => s.route)
  const go = useStore((s) => s.go)
  const loading = useStore((s) => s.loading)
  const error = useStore((s) => s.error)
  const toast = useStore((s) => s.toast)
  const decisions = useStore((s) => s.decisions)
  const consent = useStore((s) => s.consent)
  const refresh = useStore((s) => s.refresh)

  const [composerOpen, setComposerOpen] = useState(false)

  useEffect(() => {
    refresh()
  }, [refresh])

  const Screen = SCREENS[route] || V.Today
  const title = NAV_ITEMS.find((item) => item.route === route)?.label || 'Today'

  return (
    <div className="shell">
      <Rail
        route={route}
        go={go}
        decisionsCount={decisions.length}
        consentCount={consent.length}
        onCompose={() => setComposerOpen(true)}
      />

      <main className="center">
        <header className="center-header">
          <h1 className="screen-title">{title}</h1>
        </header>
        {error && <div className="error-strip">{error}</div>}
        <div className="screen-body">
          {loading ? <Skeleton /> : <Screen />}
        </div>
      </main>

      <RightRail />

      <DisruptionComposer open={composerOpen} onClose={() => setComposerOpen(false)} />

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
