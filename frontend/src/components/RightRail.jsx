// X's right sidebar: a search pill, then a stack of small stat cards. Every
// number here is a client-side sum of numbers the API already computed
// (receipt totals, a threshold from /api/autonomy) — never a price and
// never a rule evaluation of its own.

import { useMemo, useState } from 'react'
import { useStore } from '../store.js'
import { IconSearch } from '../icons.jsx'

function weekWindow(nowIso) {
  if (!nowIso) return null
  const now = new Date(nowIso)
  const diffToMonday = (now.getUTCDay() + 6) % 7
  const monday = new Date(now)
  monday.setUTCDate(now.getUTCDate() - diffToMonday)
  monday.setUTCHours(0, 0, 0, 0)
  const nextMonday = new Date(monday)
  nextMonday.setUTCDate(monday.getUTCDate() + 7)
  return [monday, nextMonday]
}

function centsFromDollarsStr(str) {
  const n = Number(str)
  return Number.isFinite(n) ? Math.round(n * 100) : 0
}

function formatCents(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

export default function RightRail() {
  const world = useStore((s) => s.world)
  const decisions = useStore((s) => s.decisions) || []
  const consent = useStore((s) => s.consent) || []
  const receipts = useStore((s) => s.receipts) || []
  const autonomy = useStore((s) => s.autonomy)
  const go = useStore((s) => s.go)
  const [query, setQuery] = useState('')

  const weekTotals = useMemo(() => {
    const window = weekWindow(world?.now)
    if (!window) return { count: 0, cents: 0 }
    const [start, end] = window
    const inWeek = receipts.filter((r) => {
      const at = new Date(r.at)
      return at >= start && at < end
    })
    return {
      count: inWeek.length,
      cents: inWeek.reduce((sum, r) => sum + centsFromDollarsStr(r.total), 0),
    }
  }, [receipts, world?.now])

  const budgetCents = autonomy?.thresholds?.weekly_budget_cents ?? null

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    const workerHits = (world?.workers || [])
      .filter((w) => w.name.toLowerCase().includes(q))
      .slice(0, 4)
      .map((w) => ({ key: `w-${w.worker_id}`, label: w.name, sub: 'Team', route: 'team' }))
    const siteHits = (world?.sites || [])
      .filter((s) => s.name.toLowerCase().includes(q))
      .slice(0, 4)
      .map((s) => ({ key: `s-${s.site_id}`, label: s.name, sub: 'Schedule', route: 'schedule' }))
    return [...workerHits, ...siteHits].slice(0, 6)
  }, [query, world])

  return (
    <aside className="right">
      <div className="search-pill">
        <IconSearch width={18} height={18} />
        <input
          type="text"
          placeholder="Search workers and sites"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {matches.length > 0 && (
        <div className="card">
          {matches.map((m) => (
            <div key={m.key} className="card-row">
              <span>{m.label}</span>
              <button type="button" className="btn btn-sm" onClick={() => go?.(m.route)}>
                {m.sub}
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div className="card-title">This week</div>
        <div className="card-row">
          <span>Waiting on you</span>
          <span className="badge badge-held">{decisions.length + consent.length}</span>
        </div>
        <div className="card-row">
          <span>Handled by Muster</span>
          <span className="badge badge-cleared">{weekTotals.count}</span>
        </div>
        <div className="card-row">
          <span>Premium spent</span>
          <span className="mono">
            {formatCents(weekTotals.cents)}
            {budgetCents != null ? ` / ${formatCents(budgetCents)}` : ''}
          </span>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Autonomy</div>
        <div className="card-row">
          <span>Current level</span>
          <span className="badge badge-neutral">{autonomy?.level || '—'}</span>
        </div>
        <button type="button" className="btn btn-sm" onClick={() => go?.('autonomy')}>
          Adjust the dial
        </button>
      </div>

      <div className="card">
        <div className="card-title">Jurisdictions encoded</div>
        {(world?.jurisdictions || []).map((j) => (
          <div key={j.code} className="card-row">
            <span>{j.name}</span>
            <a href={j.citation} target="_blank" rel="noreferrer" className="btn btn-sm">
              Source
            </a>
          </div>
        ))}
      </div>
    </aside>
  )
}
