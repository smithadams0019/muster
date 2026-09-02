// A Deputy-style week grid: a sticky worker column on the left, seven day
// columns across, shifts grouped by role with a collapsible header per
// group, and an "Open shifts" row above every group for whatever the posted
// week left uncovered.
//
// Every number this file renders is either read straight off the API
// (`world`, `schedules[siteId]`, `decisions`, `consent`, `receipts`) or a
// plain sum/comparison of numbers the API already computed: a shift's
// duration from two timestamps, a worker's scheduled hours as a sum of
// those durations, a worker's premium-this-week as a sum of receipt totals
// the pricing engine already produced. Nothing here prices a cover or
// evaluates a policy rule — see the module docstring in views.jsx for the
// two rules this whole console holds to.
//
// Colour is entirely CSS custom properties. The five shift states each map
// to a token triple (--STATE, --STATE-bg, --STATE-line) defined in
// tokens.css; this file and ShiftCard.jsx never spell out a hex value.

import { useMemo, useState } from 'react'
import { useStore } from '../store.js'
import ShiftCard from './ShiftCard.jsx'

const ROLE_ORDER = ['shift_lead', 'baker', 'barista']
const ROLE_LABELS = { shift_lead: 'Shift lead', baker: 'Baker', barista: 'Barista' }
const ROLE_DOT_OPACITY = { shift_lead: 1, baker: 0.68, barista: 0.4 }

const WEEKDAY_ABBR = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function dateKey(iso) {
  return new Date(iso).toISOString().slice(0, 10)
}

function hoursBetween(startIso, endIso) {
  const ms = new Date(endIso) - new Date(startIso)
  return Math.round((ms / 3_600_000) * 10) / 10
}

function fmtHours(h) {
  return `${h.toFixed(1)}h`
}

function formatDollarsStr(str) {
  const n = Number(str)
  return Number.isFinite(n) ? `$${n.toFixed(2)}` : `$${str}`
}

// A deterministic hue per worker. A wall of identical grey circles gives the eye
// nothing to hold on to when scanning twenty rows for one person.
function avatarHue(id) {
  let sum = 0
  for (let i = 0; i < id.length; i += 1) sum = (sum + id.charCodeAt(i) * (i + 1)) % 360
  return sum
}

function initials(name) {
  const stripped = (name || '').replace(/\s*\([^)]*\)\s*$/, '').trim()
  const parts = stripped.split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

function weekDays(weekStartsAtIso) {
  if (!weekStartsAtIso) return []
  const start = new Date(weekStartsAtIso)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start)
    d.setUTCDate(start.getUTCDate() + i)
    return d
  })
}

function shiftState(shift, heldIds, consentIds, nowIso) {
  if (heldIds.has(shift.shift_id)) return 'held'
  if (consentIds.has(shift.shift_id)) return 'consent'
  if (!shift.worker_id) return 'open'
  if (nowIso && new Date(shift.ends_at) <= new Date(nowIso)) return 'off'
  return 'posted'
}

function GridStyle() {
  return (
    <style>{`
      .sg-wrap { border: 1px solid var(--line); border-radius: var(--r); background: var(--surface); overflow: hidden; }
      .sg-head-bar { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
      .sg-head-title { font-family: var(--sans); font-weight: 700; font-size: 15px; color: var(--ink); }
      .sg-head-sub { font-family: var(--sans); font-size: 12.5px; color: var(--ink-2); margin-left: 8px; }
      .sg-scroll { overflow-x: auto; }
      .sg-grid { display: grid; grid-template-columns: var(--worker-col, 230px) repeat(7, minmax(128px, 1fr)); min-width: calc(var(--worker-col, 230px) + 7 * 128px); }

      .sg-corner, .sg-daycol {
        position: sticky; top: 0; z-index: 3; background: var(--surface-2);
        border-bottom: 1px solid var(--line-strong); padding: 8px 10px;
        font-family: var(--sans); font-size: 12px; color: var(--ink-2);
      }
      .sg-corner { left: 0; z-index: 4; }
      .sg-daycol { text-align: left; font-weight: 600; }
      .sg-daycol-today { color: var(--accent-ink); background: var(--accent-soft); }

      .sg-group-head {
        grid-column: 1 / -1; display: flex; align-items: center; gap: 8px;
        padding: 8px 10px; background: var(--surface-2); border-top: 1px solid var(--line);
        border-bottom: 1px solid var(--line); cursor: pointer; user-select: none;
        font-family: var(--sans);
      }
      .sg-group-dot { width: 9px; height: 9px; border-radius: 999px; background: var(--accent); flex: none; }
      .sg-group-name { font-weight: 700; font-size: 13px; color: var(--ink); }
      .sg-group-count { font-size: 12px; color: var(--ink-3); }
      .sg-group-chevron { margin-left: auto; font-size: 11px; color: var(--ink-3); transition: transform 120ms ease; }
      .sg-group-chevron-open { transform: rotate(180deg); }

      .sg-worker-cell {
        position: sticky; left: 0; z-index: 2; background: var(--surface);
        border-bottom: 1px solid var(--line); border-right: 1px solid var(--line);
        padding: 8px 10px; display: flex; align-items: center; gap: 8px; min-width: 0;
      }
      .sg-avatar {
        flex: none; width: 30px; height: 30px; border-radius: 999px; background: var(--accent-soft);
        color: var(--accent-ink); display: flex; align-items: center; justify-content: center;
        font-family: var(--sans); font-size: 11.5px; font-weight: 700;
      }
      .sg-avatar-open { background: var(--open-bg); color: var(--open); border: 1px dashed var(--open-line); }
      .sg-worker-meta { min-width: 0; display: flex; flex-direction: column; }
      .sg-worker-name { font-family: var(--sans); font-size: 13px; font-weight: 600; color: var(--ink);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .sg-worker-sub { font-family: var(--mono); font-size: 11px; color: var(--ink-3); }

      .sg-cell {
        position: relative; border-bottom: 1px solid var(--line); border-right: 1px solid var(--line);
        padding: 6px; min-height: 56px; display: flex; flex-direction: column; gap: 4px;
      }
      .sg-cell-plus {
        position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
        color: var(--ink-3); font-size: 16px; opacity: 0; pointer-events: none; transition: opacity 100ms ease;
      }
      .sg-cell:hover .sg-cell-plus { opacity: 1; }

      .sg-shift-card {
        display: flex; flex-direction: column; gap: 2px; text-align: left;
        border: 1px solid var(--sg-card-line); background: var(--sg-card-bg);
        border-radius: var(--r-sm); padding: 5px 7px; font: inherit; width: 100%;
      }
      .sg-shift-card-clickable { cursor: pointer; }
      .sg-shift-card-clickable:hover { filter: brightness(0.97); }
      .sg-shift-time { font-family: var(--mono); font-size: 11.5px; font-weight: 700; color: var(--ink); }
      .sg-shift-role { font-family: var(--sans); font-size: 10.5px; color: var(--sg-card-ink); display: flex; align-items: center; gap: 4px; }
      .sg-shift-dot { width: 6px; height: 6px; border-radius: 999px; background: var(--sg-card-ink); flex: none; }

      .sg-empty { padding: 24px 16px; font-family: var(--sans); font-size: 13px; color: var(--ink-2); }
    `}</style>
  )
}

// A posted (untouched) shift is tinted by role in ShiftCard.jsx, using the
// --role-lead/-baker/-barista tokens; the other four states override that
// with their own token triple. The legend mirrors both halves so the two
// colour systems it's built from stay honest about what's on screen.
const ROLE_SWATCHES = [
  ['shift_lead', 'Shift lead', '--role-lead'],
  ['baker', 'Baker', '--role-baker'],
  ['barista', 'Barista', '--role-barista'],
]
const STATE_SWATCHES = [
  ['held', 'Held for you'],
  ['consent', 'Needs consent'],
  ['open', 'Uncovered'],
  ['off', 'Already worked'],
]

function Swatch({ bg, line, label }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--ink-2)' }}>
      <span style={{ width: 9, height: 9, borderRadius: 3, background: bg, border: `1px solid ${line}` }} />
      {label}
    </span>
  )
}

function Legend() {
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', padding: '0 16px 12px', fontFamily: 'var(--sans)', fontSize: 11.5 }}>
      {ROLE_SWATCHES.map(([role, label, tokenBase]) => (
        <Swatch key={role} bg={`var(${tokenBase}-bg)`} line={`var(${tokenBase}-line)`} label={label} />
      ))}
      {STATE_SWATCHES.map(([state, label]) => (
        <Swatch key={state} bg={`var(--${state}-bg)`} line={`var(--${state}-line)`} label={label} />
      ))}
    </div>
  )
}

export default function ScheduleGrid({ siteId }) {
  const world = useStore((s) => s.world)
  const schedules = useStore((s) => s.schedules) || {}
  const decisions = useStore((s) => s.decisions) || []
  const consent = useStore((s) => s.consent) || []
  const receipts = useStore((s) => s.receipts) || []
  const go = useStore((s) => s.go)

  const [collapsed, setCollapsed] = useState(() => new Set())

  const site = (world?.sites || []).find((s) => s.site_id === siteId)
  const schedule = schedules[siteId]
  const nowIso = world?.now

  const heldIds = useMemo(() => new Set(decisions.map((d) => d.offer_id)), [decisions])
  const consentIds = useMemo(() => new Set(consent.map((c) => c.shift_id)), [consent])

  const days = useMemo(() => weekDays(schedule?.week_starts_at), [schedule?.week_starts_at])
  const todayKey = nowIso ? dateKey(nowIso) : null

  const workers = useMemo(
    () => (world?.workers || []).filter((w) => w.site_id === siteId),
    [world?.workers, siteId],
  )

  // shift_id -> shift, and per-worker / open buckets, each bucketed by day.
  // A site's schedule can carry a bridge shift from the day before the week
  // starts (see adapters/simulated.py) — real data, but outside these seven
  // columns, so it is excluded here rather than counted in a total nothing
  // on screen explains.
  const { byWorkerByDay, openByDay, workerHours, workerPremiumCents, openHours } = useMemo(() => {
    const dayKeys = new Set(days.map((d) => d.toISOString().slice(0, 10)))
    const shifts = (schedule?.shifts || []).filter((sh) => dayKeys.has(dateKey(sh.starts_at)))
    const byWorkerByDay = new Map() // worker_id -> Map(dayKey -> [shift])
    const openByDay = new Map() // dayKey -> [shift]
    const workerHours = new Map()
    let openHours = 0

    for (const sh of shifts) {
      const key = dateKey(sh.starts_at)
      const hrs = hoursBetween(sh.starts_at, sh.ends_at)
      if (sh.worker_id) {
        if (!byWorkerByDay.has(sh.worker_id)) byWorkerByDay.set(sh.worker_id, new Map())
        const perDay = byWorkerByDay.get(sh.worker_id)
        if (!perDay.has(key)) perDay.set(key, [])
        perDay.get(key).push(sh)
        workerHours.set(sh.worker_id, (workerHours.get(sh.worker_id) || 0) + hrs)
      } else {
        if (!openByDay.has(key)) openByDay.set(key, [])
        openByDay.get(key).push(sh)
        openHours += hrs
      }
    }

    // Premium paid this week per worker: a plain sum of receipt totals the
    // pricing engine already produced, scoped to this site's posted week.
    const workerPremiumCents = new Map()
    if (schedule?.week_starts_at) {
      const weekStart = new Date(schedule.week_starts_at)
      const weekEnd = new Date(weekStart)
      weekEnd.setUTCDate(weekEnd.getUTCDate() + 7)
      for (const r of receipts) {
        if (r.site_id !== siteId) continue
        const at = new Date(r.at)
        if (at < weekStart || at >= weekEnd) continue
        const cents = Math.round(Number(r.total) * 100)
        workerPremiumCents.set(r.worker_id, (workerPremiumCents.get(r.worker_id) || 0) + cents)
      }
    }

    return { byWorkerByDay, openByDay, workerHours, workerPremiumCents, openHours }
  }, [schedule?.shifts, schedule?.week_starts_at, receipts, siteId, days])

  const groups = useMemo(() => {
    const byRole = new Map(ROLE_ORDER.map((r) => [r, []]))
    for (const w of workers) {
      if (!byRole.has(w.role)) byRole.set(w.role, [])
      byRole.get(w.role).push(w)
    }
    return [...byRole.entries()].filter(([, roster]) => roster.length > 0)
  }, [workers])

  function toggleGroup(role) {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(role)) next.delete(role)
      else next.add(role)
      return next
    })
  }

  function renderCell(shifts) {
    if (!shifts || shifts.length === 0) {
      return <div className="sg-cell"><span className="sg-cell-plus" aria-hidden="true">+</span></div>
    }
    return (
      <div className="sg-cell">
        {shifts.map((sh) => {
          const state = shiftState(sh, heldIds, consentIds, nowIso)
          return (
            <ShiftCard
              key={sh.shift_id}
              shift={sh}
              state={state}
              onClick={state === 'held' ? () => go?.('decisions') : undefined}
            />
          )
        })}
      </div>
    )
  }

  if (!site) {
    return <div className="sg-empty">Unknown site {siteId}.</div>
  }

  return (
    <div className="sg-wrap">
      <GridStyle />
      <div className="sg-head-bar">
        <div>
          <span className="sg-head-title">{site.name}</span>
          <span className="sg-head-sub">
            {site.jurisdiction_code}
            {schedule?.posted_at
              ? ` · posted week of ${schedule.week_starts_at?.slice(0, 10)}`
              : ' · not posted'}
          </span>
        </div>
      </div>

      {!schedule ? (
        <div className="sg-empty">No schedule loaded for this site yet.</div>
      ) : (
        <div className="sg-scroll">
          <div className="sg-grid">
            <div className="sg-corner" />
            {days.map((day) => {
              const key = day.toISOString().slice(0, 10)
              const isToday = key === todayKey
              return (
                <div key={key} className={`sg-daycol${isToday ? ' sg-daycol-today' : ''}`}>
                  {WEEKDAY_ABBR[day.getUTCDay()]} {day.getUTCDate()}
                </div>
              )
            })}

            {/* Open shifts: uncovered posted shifts, above every role group. */}
            <div className="sg-worker-cell">
              <div className="sg-avatar sg-avatar-open">＋</div>
              <div className="sg-worker-meta">
                <span className="sg-worker-name">Open shifts</span>
                <span className="sg-worker-sub">{fmtHours(openHours)} uncovered</span>
              </div>
            </div>
            {days.map((day) => {
              const key = day.toISOString().slice(0, 10)
              return <div key={key}>{renderCell(openByDay.get(key))}</div>
            })}

            {groups.map(([role, roster]) => {
              const isCollapsed = collapsed.has(role)
              return (
                <div key={role} style={{ display: 'contents' }}>
                  <div className="sg-group-head" onClick={() => toggleGroup(role)}>
                    <span className="sg-group-dot" style={{ opacity: ROLE_DOT_OPACITY[role] ?? 0.6 }} />
                    <span className="sg-group-name">{ROLE_LABELS[role] || role}</span>
                    <span className="sg-group-count">{roster.length}</span>
                    <span className={`sg-group-chevron${isCollapsed ? '' : ' sg-group-chevron-open'}`}>▾</span>
                  </div>

                  {!isCollapsed && roster.map((w) => {
                    const perDay = byWorkerByDay.get(w.worker_id)
                    const hrs = workerHours.get(w.worker_id) || 0
                    const premiumCents = workerPremiumCents.get(w.worker_id) || 0
                    return (
                      <div key={w.worker_id} style={{ display: 'contents' }}>
                        <div className="sg-worker-cell">
                          <div className="sg-avatar" style={{ background: `hsl(${avatarHue(w.worker_id)} 72% 94%)`, color: `hsl(${avatarHue(w.worker_id)} 55% 34%)`, border: `1px solid hsl(${avatarHue(w.worker_id)} 55% 82%)` }}>{initials(w.name)}</div>
                          <div className="sg-worker-meta">
                            <span className="sg-worker-name" title={w.name}>{w.name}</span>
                            <span className="sg-worker-sub">
                              {fmtHours(hrs)} scheduled
                              {premiumCents > 0 ? ` · +${formatDollarsStr((premiumCents / 100).toFixed(2))} premium` : ''}
                            </span>
                          </div>
                        </div>
                        {days.map((day) => {
                          const key = day.toISOString().slice(0, 10)
                          return <div key={key}>{renderCell(perDay?.get(key))}</div>
                        })}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
