// The day-by-day summary row beneath the toolbar, mirroring Deputy's
// coverage strip. One column per day of the posted week: a small
// required-vs-scheduled coverage chart, then shifts / hours / est. cost /
// premium exposure underneath.
//
// This component computes presentation only. It never prices a change or
// evaluates a rule — required cover comes straight from /api/demand, an
// hourly count of how many people the day needs, already computed
// server-side. Scheduled cover, shift/hour counts and estimated cost are
// plain arithmetic over timestamps and rates the API already returned
// (duration between two given instants, hours × a posted rate). Premium
// exposure is never estimated here — it is the sum of receipt totals the
// backend already wrote for that day.

import { useEffect, useState } from 'react'
import { useStore } from '../store.js'

const BASE = import.meta.env.VITE_MUSTER_API || '/api'

const DAY_LABEL = { day: 'numeric', month: 'short', timeZone: 'UTC' }
const WEEKDAY_LABEL = { weekday: 'short', timeZone: 'UTC' }

function isoDate(iso) {
  return String(iso).slice(0, 10)
}

function hoursBetween(startIso, endIso) {
  const ms = new Date(endIso) - new Date(startIso)
  return Math.round((ms / 3_600_000) * 10) / 10
}

function money(n) {
  return `$${n.toFixed(2)}`
}

function shiftsForDay(schedule, day) {
  return (schedule?.shifts || []).filter((sh) => isoDate(sh.starts_at) === day)
}

function scheduledCoverByHour(shifts, hourList, day) {
  return hourList.map((h) => {
    const bucketStart = new Date(`${day}T${String(h).padStart(2, '0')}:00:00+00:00`)
    const bucketEnd = new Date(bucketStart.getTime() + 3_600_000)
    return shifts.reduce((n, sh) => {
      const s = new Date(sh.starts_at)
      const e = new Date(sh.ends_at)
      return s < bucketEnd && e > bucketStart ? n + 1 : n
    }, 0)
  })
}

const CHART_W = 120
const CHART_H = 44

export default function MetricsStrip({ siteId, week }) {
  const schedules = useStore((s) => s.schedules)
  const workers = useStore((s) => s.world?.workers) || []
  const receipts = useStore((s) => s.receipts) || []

  const [demand, setDemand] = useState(null)
  const [error, setError] = useState(null)
  const [dayIndex, setDayIndex] = useState(0)

  useEffect(() => {
    if (!siteId) return
    let cancelled = false
    setDemand(null)
    setError(null)
    const qs = week ? `?week=${encodeURIComponent(week)}` : ''
    fetch(`${BASE}/demand/${encodeURIComponent(siteId)}${qs}`)
      .then((res) => {
        if (!res.ok) throw new Error(`demand fetch failed: ${res.status}`)
        return res.json()
      })
      .then((data) => { if (!cancelled) setDemand(data) })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Could not load demand') })
    return () => { cancelled = true }
  }, [siteId, week])

  if (!siteId) return null
  if (error) return <div className="coverage-panel coverage-panel-error">{error}</div>
  if (!demand) return <div className="coverage-panel coverage-panel-loading" />

  const day = demand.days[Math.min(dayIndex, demand.days.length - 1)]
  const schedule = schedules?.[siteId]
  const rateByWorker = new Map(workers.map((w) => [w.worker_id, Number(w.hourly_rate) || 0]))

  const hourList = []
  for (let h = demand.opens_at_hour; h < demand.closes_at_hour; h += 1) hourList.push(h)

  const shifts = shiftsForDay(schedule, day.day)
  const required = hourList.map((h) => day.hours[String(h)] || 0)
  const scheduled = scheduledCoverByHour(shifts, hourList, day.day)

  const hours = shifts.reduce((sum, sh) => sum + hoursBetween(sh.starts_at, sh.ends_at), 0)
  const cost = shifts.reduce(
    (sum, sh) => sum + hoursBetween(sh.starts_at, sh.ends_at) * (rateByWorker.get(sh.worker_id) || 0),
    0,
  )
  const premium = receipts
    .filter((r) => r.site_id === siteId && isoDate(r.at) === day.day)
    .reduce((sum, r) => sum + (Number(r.total) || 0), 0)

  const short = hourList.filter((_, i) => scheduled[i] < required[i]).length

  return (
    <section className="coverage-panel">
      <header className="coverage-head">
        <div>
          <h2 className="coverage-title">Cover against demand</h2>
          <p className="coverage-sub">
            {short === 0
              ? 'Every trading hour has at least the cover it needs.'
              : `${short} ${short === 1 ? 'hour is' : 'hours are'} below the cover this day needs.`}
          </p>
        </div>
        <div className="day-toggle" role="tablist" aria-label="Day of the week">
          {demand.days.map((d, i) => {
            const date = new Date(`${d.day}T00:00:00Z`)
            return (
              <button
                key={d.day}
                role="tab"
                aria-selected={i === dayIndex}
                className={`day-tab${i === dayIndex ? ' active' : ''}`}
                onClick={() => setDayIndex(i)}
              >
                <span className="day-tab-weekday">
                  {date.toLocaleDateString(undefined, WEEKDAY_LABEL)}
                </span>
                <span className="day-tab-date">
                  {date.toLocaleDateString(undefined, DAY_LABEL)}
                </span>
              </button>
            )
          })}
        </div>
      </header>

      <div className="coverage-body">
        <dl className="coverage-figures">
          <div><dt>Shifts</dt><dd>{shifts.length}</dd></div>
          <div><dt>Hours</dt><dd>{hours.toFixed(1)}</dd></div>
          <div><dt>Est. cost</dt><dd>${cost.toFixed(2)}</dd></div>
          <div className={premium > 0 ? 'is-held' : undefined}>
            <dt>Premium owed</dt><dd>${premium.toFixed(2)}</dd>
          </div>
        </dl>
        <CoverageChart hours={hourList} required={required} scheduled={scheduled} />
        <div className="coverage-legend">
          <span className="coverage-key coverage-key-required"><i />Cover needed</span>
          <span className="coverage-key coverage-key-scheduled"><i />People scheduled</span>
        </div>
      </div>
    </section>
  )
}

/** One readable chart beats seven thumbnails.
 *
 * Seven identical 120px sparklines showed the same silhouette every day and
 * carried no information a person could act on. This draws one day at full
 * width with real hour ticks and a headcount axis, so "we are one short at
 * seven" is legible rather than implied.
 */
function CoverageChart({ hours, required, scheduled }) {
  const W = 1040
  const H = 150
  const padL = 44
  const padR = 16
  const padT = 16
  const padB = 26
  const peak = Math.max(1, ...required, ...scheduled)
  const stepX = (W - padL - padR) / Math.max(1, hours.length)
  const y = (v) => padT + (H - padT - padB) * (1 - v / peak)

  const stepPath = (series, close) => {
    const pts = []
    series.forEach((v, i) => {
      const x0 = padL + i * stepX
      const x1 = padL + (i + 1) * stepX
      pts.push(`${i === 0 ? 'M' : 'L'}${x0},${y(v)}`, `L${x1},${y(v)}`)
    })
    if (close) {
      pts.push(`L${padL + series.length * stepX},${H - padB}`, `L${padL},${H - padB}`, 'Z')
    }
    return pts.join(' ')
  }

  const ticks = []
  for (let v = 0; v <= peak; v += Math.max(1, Math.round(peak / 3))) ticks.push(v)

  return (
    <svg className="coverage-chart" viewBox={`0 0 ${W} ${H}`} role="img"
         aria-label="Required cover against scheduled cover, by hour">
      <defs>
        <linearGradient id="reqfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--chart-required)" stopOpacity="0.85" />
          <stop offset="100%" stopColor="var(--chart-required)" stopOpacity="0.15" />
        </linearGradient>
      </defs>

      {ticks.map((v) => (
        <g key={v}>
          <line x1={padL} x2={W - padR} y1={y(v)} y2={y(v)} className="coverage-grid" />
          <text x={padL - 10} y={y(v) + 4} className="coverage-axis" textAnchor="end">{v}</text>
        </g>
      ))}

      <path d={stepPath(required, true)} fill="url(#reqfill)" />
      <path d={stepPath(scheduled, false)} className="coverage-line" fill="none" />

      {hours.map((h, i) => (
        i % 2 === 0 ? (
          <text key={h} x={padL + i * stepX + stepX / 2} y={H - 10}
                className="coverage-axis" textAnchor="middle">
            {h}:00
          </text>
        ) : null
      ))}
    </svg>
  )
}
