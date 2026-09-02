// The console's shell: a full-width top nav, a toolbar, the metrics strip
// (Schedule route only), the routed screen, and a footer legend pinned to
// the bottom — Deputy's Schedule screen structure, no centred column and no
// right sidebar.

import { useEffect, useMemo, useState } from 'react'
import * as V from './views.jsx'
import { useStore } from './store.js'
import MetricsStrip from './components/MetricsStrip.jsx'
import FooterLegend from './components/FooterLegend.jsx'
import DraftingModal from './components/DraftingModal.jsx'
import DisruptionComposer from './components/DisruptionComposer.jsx'
import {
  IconPin,
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconRefresh,
  IconSparkle,
  IconGear,
  IconBell,
  IconInsights,
} from './icons.jsx'

const NAV_ITEMS = [
  { route: 'schedule', label: 'Schedule' },
  { route: 'decisions', label: 'Decisions', badgeKey: 'decisions' },
  { route: 'consent', label: 'Consent', badgeKey: 'consent' },
  { route: 'people', label: 'People' },
  { route: 'autonomy', label: 'Autonomy' },
  { route: 'timeline', label: 'Timeline' },
  { route: 'receipts', label: 'Receipts' },
]

const SCREENS = {
  schedule: V.Schedule,
  decisions: V.Decisions,
  consent: V.Consent,
  people: V.People,
  autonomy: V.Autonomy,
  timeline: V.Timeline,
  receipts: V.Receipts,
}

// The Monday on or after `now`, at midnight — mirrors the server's own
// _next_week_start so the label matches the week /api/schedule posts for.
// Pure date arithmetic on a timestamp the API already gave us, not policy.
function nextWeekStart(nowIso) {
  if (!nowIso) return null
  const now = new Date(nowIso)
  const day = (now.getUTCDay() + 6) % 7 // Mon=0..Sun=6
  const daysAhead = (7 - day) % 7
  const monday = new Date(now)
  monday.setUTCDate(now.getUTCDate() + daysAhead)
  monday.setUTCHours(0, 0, 0, 0)
  return monday
}

function fmtWeekRange(monday) {
  if (!monday) return '—'
  const sunday = new Date(monday)
  sunday.setUTCDate(monday.getUTCDate() + 6)
  const opts = { day: 'numeric', month: 'short', timeZone: 'UTC' }
  return `${monday.toLocaleDateString(undefined, opts)} – ${sunday.toLocaleDateString(undefined, opts)}`
}

function AutonomyPill({ level }) {
  const label = level ? level[0].toUpperCase() + level.slice(1) : '—'
  return <span className="autonomy-pill">{label}</span>
}

function TopNav({ route, go, decisionsCount, consentCount, autonomyLevel, notifCount, onReportDisruption }) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="top-nav">
      <div className="top-nav-brand">
        <span className="brand-mark">M</span>
        <span className="brand-name">Muster</span>
      </div>

      <nav className="top-nav-items">
        {NAV_ITEMS.map((item) => {
          const count =
            item.badgeKey === 'decisions' ? decisionsCount : item.badgeKey === 'consent' ? consentCount : 0
          return (
            <button
              key={item.route}
              type="button"
              className={`top-nav-item${route === item.route ? ' active' : ''}`}
              aria-current={route === item.route ? 'page' : undefined}
              onClick={() => go(item.route)}
            >
              {item.label}
              {Boolean(count) && <span className="top-nav-badge">{count}</span>}
            </button>
          )
        })}
      </nav>

      <div className="top-nav-right">
        <AutonomyPill level={autonomyLevel} />
        <button
          type="button"
          className="icon-btn"
          aria-label="Notifications"
          title="What is waiting on you"
          onClick={() => go('decisions')}
        >
          <IconBell width={19} height={19} />
          {Boolean(notifCount) && <span className="icon-btn-badge">{notifCount}</span>}
        </button>
        <div className="operator-menu">
          <button
            type="button"
            className="operator-chip"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
          >
            <span className="operator-avatar">AS</span>
            <span>Hello, Smith</span>
            <IconChevronDown width={14} height={14} />
          </button>
          {menuOpen && (
            <div className="operator-dropdown" role="menu">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false)
                  onReportDisruption()
                }}
              >
                Report a disruption
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

function Toolbar({
  sites,
  selectedSite,
  onSelectSite,
  weekLabel,
  weekOffset,
  onWeekChange,
  groupBy,
  onGroupByChange,
  onRefresh,
  onDraft,
  draftBusy,
  onSettings,
}) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <div className="site-picker">
          <IconPin width={16} height={16} />
          <select
            value={selectedSite || ''}
            onChange={(e) => onSelectSite(e.target.value)}
            aria-label="Site"
          >
            {sites.map((s) => (
              <option key={s.site_id} value={s.site_id}>
                {s.name}
              </option>
            ))}
          </select>
          <IconChevronDown width={14} height={14} />
        </div>

        <div className="week-stepper">
          <button
            type="button"
            className="icon-btn icon-btn-sm"
            aria-label="Previous week"
            onClick={() => onWeekChange(weekOffset - 1)}
          >
            <IconChevronLeft width={16} height={16} />
          </button>
          <span className="week-range">{weekLabel}</span>
          <button
            type="button"
            className="icon-btn icon-btn-sm"
            aria-label="Next week"
            onClick={() => onWeekChange(weekOffset + 1)}
          >
            <IconChevronRight width={16} height={16} />
          </button>
        </div>

        <select
          className="view-select"
          value={groupBy}
          onChange={(e) => onGroupByChange(e.target.value)}
          aria-label="View"
        >
          <option value="role">By role</option>
          <option value="employee">By employee</option>
        </select>
      </div>

      <div className="toolbar-right">
        <button type="button" className="icon-btn" onClick={onRefresh} aria-label="Refresh" title="Refresh">
          <IconRefresh width={18} height={18} />
        </button>
        <button
          type="button"
          className="btn btn-accent-solid"
          onClick={onDraft}
          disabled={!selectedSite || draftBusy}
        >
          <IconSparkle width={16} height={16} />
          {draftBusy ? 'Drafting…' : 'Draft with Muster'}
        </button>
        <button
          type="button"
          className="icon-btn"
          aria-label="Settings"
          title="Autonomy and limits"
          onClick={onSettings}
        >
          <IconGear width={18} height={18} />
        </button>
      </div>
    </div>
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
  const world = useStore((s) => s.world)
  const decisions = useStore((s) => s.decisions) || []
  const consent = useStore((s) => s.consent) || []
  const autonomy = useStore((s) => s.autonomy)
  const busy = useStore((s) => s.busy) || {}
  const refresh = useStore((s) => s.refresh)
  const draftWeek = useStore((s) => s.draftWeek)

  const [selectedSite, setSelectedSite] = useState('')

  // The stepper moves this; the grid and the analytics both follow it.

  const [weekOffset, setWeekOffset] = useState(0)

  const [groupBy, setGroupBy] = useState('role')
  const [draftOpen, setDraftOpen] = useState(false)
  const [disruptionOpen, setDisruptionOpen] = useState(false)

  const sites = world?.sites || []

  useEffect(() => {
    go('schedule')
  }, [go])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!selectedSite && sites.length > 0) setSelectedSite(sites[0].site_id)
  }, [sites, selectedSite])

  const viewWeekStart = useMemo(() => {
    const base = nextWeekStart(world?.now)
    if (!base) return null
    const shifted = new Date(base)
    shifted.setUTCDate(base.getUTCDate() + weekOffset * 7)
    return shifted
  }, [world?.now, weekOffset])
  const weekLabel = useMemo(() => fmtWeekRange(viewWeekStart), [viewWeekStart])
  const viewWeekIso = viewWeekStart ? viewWeekStart.toISOString() : null

  const Screen = SCREENS[route] || V.Schedule
  const draftBusy = Boolean(busy[`draft:${selectedSite}`])

  return (
    <div className="app-shell">
      <TopNav
        route={route}
        go={go}
        decisionsCount={decisions.length}
        consentCount={consent.length}
        autonomyLevel={autonomy?.level}
        notifCount={decisions.length + consent.length}
        onReportDisruption={() => setDisruptionOpen(true)}
      />

      {/* Site, week, drafting and posting only mean something against a rota.
          Showing them on Receipts or Timeline offered controls that could not
          act on what was on screen. */}
      {route === 'schedule' && (
        <>
          <Toolbar
            sites={sites}
            selectedSite={selectedSite}
            onSelectSite={setSelectedSite}
            weekLabel={weekLabel}
            weekOffset={weekOffset}
            onWeekChange={setWeekOffset}
            groupBy={groupBy}
            onGroupByChange={setGroupBy}
            onRefresh={() => refresh()}
            onDraft={() => setDraftOpen(true)}
            draftBusy={draftBusy}
            onSettings={() => go('autonomy')}
          />
          <MetricsStrip siteId={selectedSite} week={viewWeekIso} />
        </>
      )}

      <main className="app-main">
        {error && <div className="error-strip error-strip-page">{error}</div>}
        <div className="screen-body">
          {loading ? <Skeleton /> : <Screen siteId={selectedSite} groupBy={groupBy} week={viewWeekIso} />}
        </div>
      </main>

      <FooterLegend />

      <DraftingModal open={draftOpen} siteId={selectedSite} onClose={() => setDraftOpen(false)} />
      <DisruptionComposer open={disruptionOpen} onClose={() => setDisruptionOpen(false)} />

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
