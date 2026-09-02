// The eight screens of the Muster console.
//
// App.jsx owns the global loading skeleton and the top-level error strip —
// a screen only ever mounts once `loading` is false, so screens here render
// content, not loading/error chrome.
//
// Two rules hold across every screen in this file:
//   1. Nothing here prices anything or evaluates a policy rule. Every number
//      rendered either came straight off an API response, or is a plain sum
//      / comparison of numbers the API already computed (a week's receipt
//      totals against a threshold, a shift's duration from two timestamps).
//   2. "Now" always means world.now, read from the store. This file never
//      calls `new Date()` with no argument.

import { useMemo, useState } from 'react'
import { useStore } from './store.js'
import { receiptsCsvUrl } from './api.js'
import OptionTable from './components/OptionTable.jsx'
import { IconAlert, IconDownload } from './icons.jsx'

// -- shared vocabulary --------------------------------------------------
// Fixed identifiers the server already returns (policy/rules.py, domain/
// types.py). Mapping them to friendlier prose is a label lookup, not a
// policy decision — the server already decided which of these fired.

const NON_NEGOTIABLE = new Set(['rest_waiver_required', 'worker_declined'])

const RULE_LABELS = {
  cost_over_budget: 'Cost over per-incident budget',
  weekly_budget_exhausted: 'Weekly premium budget exhausted',
  overtime_threshold: 'Overtime threshold exceeded',
  hours_shortfall: 'Good-faith hours shortfall',
  understaffed_below_minimum: 'Below role or certification minimum',
  rest_waiver_required: "Rest period waiver — needs the worker's own consent",
  worker_declined: 'Worker already declined this shift',
  unassessable: 'Cannot be assessed automatically',
}

const ROLE_LABELS = { barista: 'Barista', shift_lead: 'Shift lead', baker: 'Baker' }

const GUARDED_TOOLS = new Set([
  'post_schedule', 'assign_cover', 'cancel_shift', 'request_consent', 'notify_worker',
])

// -- generic helpers ------------------------------------------------------

function hasNonNegotiable(decision) {
  return (decision.rule_hits || []).some((h) => NON_NEGOTIABLE.has(h.rule))
}

function byNonNegotiableFirst(a, b) {
  return (hasNonNegotiable(a) ? 0 : 1) - (hasNonNegotiable(b) ? 0 : 1)
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC',
  })
}

function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: 'numeric', minute: '2-digit', timeZone: 'UTC',
  })
}

function fmtDateTime(iso) {
  if (!iso) return '—'
  return `${fmtDate(iso)}, ${fmtTime(iso)}`
}

function hoursBetween(startIso, endIso) {
  const ms = new Date(endIso) - new Date(startIso)
  return Math.round((ms / 3_600_000) * 10) / 10
}

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

function formatDollarsStr(str) {
  const n = Number(str)
  return Number.isFinite(n) ? `$${n.toFixed(2)}` : `$${str}`
}

function workerName(world, workerId) {
  return world?.workers?.find((w) => w.worker_id === workerId)?.name || workerId
}

function siteName(world, siteId) {
  return world?.sites?.find((s) => s.site_id === siteId)?.name || siteId
}

function findShift(schedules, shiftId) {
  for (const schedule of Object.values(schedules || {})) {
    const hit = (schedule?.shifts || []).find((sh) => sh.shift_id === shiftId)
    if (hit) return { shift: hit, site_id: schedule.site_id }
  }
  return null
}

function useWeekTotals() {
  const world = useStore((s) => s.world)
  const receipts = useStore((s) => s.receipts) || []
  return useMemo(() => {
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
}

function Empty({ children }) {
  return <div className="empty-state">{children}</div>
}

// -- Today ------------------------------------------------------------------

export function Today() {
  const world = useStore((s) => s.world)
  const decisions = useStore((s) => s.decisions) || []
  const consent = useStore((s) => s.consent) || []
  const schedules = useStore((s) => s.schedules) || {}
  const autonomy = useStore((s) => s.autonomy)
  const go = useStore((s) => s.go)

  const weekTotals = useWeekTotals()
  const budgetCents = autonomy?.thresholds?.weekly_budget_cents ?? null
  const overBudget = budgetCents != null && weekTotals.cents > budgetCents

  const sortedDecisions = useMemo(
    () => [...decisions].sort(byNonNegotiableFirst),
    [decisions],
  )

  const waiting = decisions.length + consent.length
  const summary =
    waiting === 0 && weekTotals.count === 0
      ? 'Nothing has moved this week. Muster is watching the posted rota.'
      : waiting === 0
        ? `Muster covered ${weekTotals.count} ${weekTotals.count === 1 ? 'shift' : 'shifts'} this week without interrupting you.`
        : `${waiting} ${waiting === 1 ? 'call needs' : 'calls need'} you. Muster handled ${weekTotals.count} ${weekTotals.count === 1 ? 'other' : 'others'} on its own.`

  const sitesPosted = (world?.sites || []).filter((s) => schedules[s.site_id]?.posted_at).length
  const soonestConsentExpiry = [...consent].map((c) => c.expires_at).sort()[0]

  return (
    <>
      {/* The right rail already carries the same three figures as a standing
          card. Repeating them here wasted the top of the feed, so the centre
          column opens with the sentence a coordinator would actually say. */}
      <div className="section-pad">
        <p className="lede">{summary}</p>
      </div>

      <div className="section-pad">
        <div className="card-title">The three loops</div>
        <div className="row">
          <div className="row-main">
            <span className="row-title">Draft — next week's schedule</span>
            <span className="row-sub">{sitesPosted} of {world?.sites?.length || 0} sites posted</span>
          </div>
          <div className="row-actions">
            <button type="button" className="btn btn-sm" onClick={() => go?.('schedule')}>
              Open Schedule
            </button>
          </div>
        </div>
        <div className="row">
          <div className="row-main">
            <span className="row-title">Hold — covering the posted week</span>
            <span className="row-sub">
              {decisions.length} held decision{decisions.length === 1 ? '' : 's'}
            </span>
          </div>
          <div className="row-actions">
            <button type="button" className="btn btn-sm" onClick={() => go?.('decisions')}>
              Open Decisions
            </button>
          </div>
        </div>
        <div className="row">
          <div className="row-main">
            <span className="row-title">Consent — asks out to workers</span>
            <span className="row-sub">
              {consent.length} outstanding
              {soonestConsentExpiry ? `, soonest expires ${fmtDateTime(soonestConsentExpiry)}` : ''}
            </span>
          </div>
          <div className="row-actions">
            <button type="button" className="btn btn-sm" onClick={() => go?.('consent')}>
              Open Consent
            </button>
          </div>
        </div>
      </div>

      <div className="section-pad">
        <div className="card-title">Waiting on you</div>
        {sortedDecisions.length === 0 ? (
          <Empty>Nothing held right now.</Empty>
        ) : (
          sortedDecisions.map((d) => (
            <div className="row" key={d.decision_id}>
              <div className="row-main">
                <span className="row-title">{RULE_LABELS[d.rule] || d.rule}</span>
                <span className="row-sub">{d.prompt}</span>
              </div>
              <div className="row-actions">
                {hasNonNegotiable(d) && (
                  <span className="badge badge-critical">
                    <IconAlert width={14} height={14} /> needs consent
                  </span>
                )}
                <button type="button" className="btn btn-sm" onClick={() => go?.('decisions')}>
                  Review
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}

// -- Decisions ----------------------------------------------------------------
// The screen that sells the product.

function optionsFromDecision(decision, consentList, world) {
  const consentForShift = consentList.filter((c) => c.shift_id === decision.offer_id)
  return (decision.rule_hits || []).map((hit, i) => {
    const isConsentRule = NON_NEGOTIABLE.has(hit.rule)
    const match = isConsentRule ? consentForShift[0] : null
    return {
      id: `${decision.decision_id}-${hit.rule}-${i}`,
      worker: match ? workerName(world, match.worker_id) : null,
      cost: match ? formatDollarsStr(match.premium_owed) : hit.detail,
      costIsExact: Boolean(match),
      clause: RULE_LABELS[hit.rule] || hit.rule,
      consentRequired: isConsentRule,
      consentLabel: match
        ? `needs ${workerName(world, match.worker_id)}'s yes`
        : "needs this person's yes",
    }
  })
}

function DecisionCard({ decision }) {
  const world = useStore((s) => s.world)
  const consent = useStore((s) => s.consent) || []
  const schedules = useStore((s) => s.schedules) || {}
  const busy = useStore((s) => s.busy) || {}
  const answerDecision = useStore((s) => s.answerDecision)
  const go = useStore((s) => s.go)

  const [note, setNote] = useState('')

  const nonNegotiable = hasNonNegotiable(decision)
  const options = optionsFromDecision(decision, consent, world)
  const located = findShift(schedules, decision.offer_id)
  const busyNow = Boolean(busy[`decision:${decision.decision_id}`])

  function answer(outcome) {
    answerDecision?.(decision.decision_id, outcome, note)?.catch(() => {})
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-row">
        <span className="badge badge-held">held</span>
        <span className="row-sub mono">{decision.offer_id}</span>
      </div>
      <div className="card-title">{RULE_LABELS[decision.rule] || decision.rule}</div>
      {located && (
        <div className="row-sub">
          {siteName(world, located.site_id)} · {ROLE_LABELS[located.shift.role] || located.shift.role} ·{' '}
          {fmtDateTime(located.shift.starts_at)}–{fmtTime(located.shift.ends_at)}
        </div>
      )}

      <OptionTable options={options} />

      <div style={{ padding: '12px 0' }}>
        <div className="row-title">Rules that fired</div>
        {(decision.rule_hits || []).map((h, i) => (
          <div className="row" key={`${h.rule}-${i}`}>
            <div className="row-main">
              <span className="row-title">{RULE_LABELS[h.rule] || h.rule}</span>
              <span className="row-sub">{h.detail}</span>
            </div>
            {NON_NEGOTIABLE.has(h.rule) && <span className="badge badge-critical">fixed at every level</span>}
          </div>
        ))}
      </div>

      {nonNegotiable && (
        <div className="error-strip">
          <IconAlert width={14} height={14} /> This needs the worker's own yes — a manager cannot approve
          it away. Check <button type="button" className="btn btn-sm" onClick={() => go?.('consent')}>
            Consent
          </button>, or decline to have Muster try another route.
        </div>
      )}

      <div className="field">
        <label htmlFor={`note-${decision.decision_id}`}>Note (recorded against the operator)</label>
        <textarea
          id={`note-${decision.decision_id}`}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Why you're approving or declining"
        />
      </div>

      <div className="row-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={nonNegotiable || busyNow}
          title={nonNegotiable ? "Needs the worker's own consent" : undefined}
          onClick={() => answer('approve')}
        >
          Approve
        </button>
        <button type="button" className="btn btn-danger" disabled={busyNow} onClick={() => answer('decline')}>
          Decline
        </button>
      </div>
    </div>
  )
}

export function Decisions() {
  const decisions = useStore((s) => s.decisions) || []
  const sorted = useMemo(() => [...decisions].sort(byNonNegotiableFirst), [decisions])

  return (
    <div className="section-pad">
      {sorted.length === 0 ? (
        <Empty>No held decisions. Muster is covering everything inside its limits.</Empty>
      ) : (
        sorted.map((d) => <DecisionCard decision={d} key={d.decision_id} />)
      )}
    </div>
  )
}

// -- Consent --------------------------------------------------------------

export function Consent() {
  const world = useStore((s) => s.world)
  const consent = useStore((s) => s.consent) || []
  const busy = useStore((s) => s.busy) || {}
  const answerConsent = useStore((s) => s.answerConsent)

  if (consent.length === 0) return <div className="section-pad"><Empty>No outstanding consent asks.</Empty></div>

  return (
    <div className="section-pad">
      {consent.map((c) => {
        const now = world?.now ? new Date(world.now) : null
        const expired = now ? new Date(c.expires_at) <= now : false
        const isFinal = Boolean(c.outcome) || expired
        const busyNow = Boolean(busy[`consent:${c.request_id}`])

        return (
          <div className="row" key={c.request_id}>
            <div className="row-main">
              <span className="row-title">
                {workerName(world, c.worker_id)} — {c.kind.replace('_', ' ')}
              </span>
              <span className="row-sub">{c.what_it_means}</span>
              <span className="row-sub">
                Owed {formatDollarsStr(c.premium_owed)} · asked {fmtDateTime(c.asked_at)} · expires{' '}
                {fmtDateTime(c.expires_at)}
              </span>
            </div>
            <div className="row-actions">
              {isFinal ? (
                <span className={`badge ${c.outcome === 'granted' ? 'badge-cleared' : 'badge-critical'}`}>
                  {c.outcome || 'expired'} — final
                </span>
              ) : (
                <>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busyNow}
                    onClick={() => answerConsent?.(c.request_id, 'granted')?.catch(() => {})}
                  >
                    They said yes
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    disabled={busyNow}
                    onClick={() => answerConsent?.(c.request_id, 'declined')?.catch(() => {})}
                  >
                    They said no
                  </button>
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// -- Schedule ---------------------------------------------------------------

function SiteSchedule({ site }) {
  const world = useStore((s) => s.world)
  const schedules = useStore((s) => s.schedules) || {}
  const busy = useStore((s) => s.busy) || {}
  const draftWeek = useStore((s) => s.draftWeek)
  const schedule = schedules[site.site_id]
  const busyNow = Boolean(busy[`draft:${site.site_id}`])

  const days = useMemo(() => {
    if (!schedule?.week_starts_at) return []
    const start = new Date(schedule.week_starts_at)
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start)
      d.setUTCDate(start.getUTCDate() + i)
      return d
    })
  }, [schedule?.week_starts_at])

  const byDay = useMemo(() => {
    const map = new Map()
    for (const day of days) map.set(day.toISOString().slice(0, 10), [])
    for (const sh of schedule?.shifts || []) {
      const key = new Date(sh.starts_at).toISOString().slice(0, 10)
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(sh)
    }
    return map
  }, [days, schedule?.shifts])

  return (
    <div className="section-pad">
      <div className="card-row">
        <div className="card-title">{site.name}</div>
        <button
          type="button"
          className="btn btn-sm"
          disabled={busyNow}
          onClick={() => draftWeek?.(site.site_id)?.catch(() => {})}
        >
          {busyNow ? 'Drafting…' : 'Draft next week'}
        </button>
      </div>
      <div className="row-sub">
        {site.jurisdiction_code}
        {schedule?.posted_at ? ` · posted ${fmtDateTime(schedule.posted_at)}` : ' · not posted'}
      </div>

      {!schedule ? (
        <Empty>No schedule loaded for this site yet.</Empty>
      ) : (
        days.map((day) => {
          const key = day.toISOString().slice(0, 10)
          const shifts = byDay.get(key) || []
          return (
            <div key={key} className="row">
              <div className="row-main" style={{ minWidth: 90 }}>
                <span className="row-title">
                  {day.toLocaleDateString(undefined, {
                    weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC',
                  })}
                </span>
              </div>
              <div className="row-main">
                {shifts.length === 0 ? (
                  <span className="row-sub">No shifts posted</span>
                ) : (
                  shifts.map((sh) => (
                    <span className="row-sub" key={sh.shift_id}>
                      {sh.worker_id ? workerName(world, sh.worker_id) : 'Unassigned'} —{' '}
                      {ROLE_LABELS[sh.role] || sh.role} — {fmtTime(sh.starts_at)}–{fmtTime(sh.ends_at)} (
                      {hoursBetween(sh.starts_at, sh.ends_at)}h)
                    </span>
                  ))
                )}
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}

export function Schedule() {
  const world = useStore((s) => s.world)
  const sites = world?.sites || []

  if (sites.length === 0) return <div className="section-pad"><Empty>No sites yet.</Empty></div>

  return (
    <>
      {sites.map((site) => <SiteSchedule site={site} key={site.site_id} />)}
    </>
  )
}

// -- Team ---------------------------------------------------------------

export function Team() {
  const world = useStore((s) => s.world)
  const workers = world?.workers || []
  const bySite = useMemo(() => {
    const map = new Map()
    for (const w of workers) {
      if (!map.has(w.site_id)) map.set(w.site_id, [])
      map.get(w.site_id).push(w)
    }
    return map
  }, [workers])

  return (
    <>
      <div className="section-pad">
        <div className="card">
          The standby-list carve-out is Oregon-only — it exists nowhere else in the rulebook.
        </div>
      </div>
      {workers.length === 0 ? (
        <div className="section-pad"><Empty>No roster yet.</Empty></div>
      ) : (
        [...bySite.entries()].map(([siteId, roster]) => (
          <div className="section-pad" key={siteId}>
            <div className="card-title">{siteName(world, siteId)}</div>
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Rate</th>
                  <th>Good-faith hours</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((w) => (
                  <tr key={w.worker_id}>
                    <td>{w.name}</td>
                    <td>{ROLE_LABELS[w.role] || w.role}</td>
                    <td className="mono">{formatDollarsStr(w.hourly_rate)}/hr</td>
                    <td>{w.good_faith_hours}h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </>
  )
}

// -- Autonomy ---------------------------------------------------------------

const DIAL_LEVELS = ['conservative', 'balanced', 'trusted']

const RULE_CATALOG = [
  { rule: 'cost_over_budget', label: RULE_LABELS.cost_over_budget, nonNegotiable: false },
  { rule: 'weekly_budget_exhausted', label: RULE_LABELS.weekly_budget_exhausted, nonNegotiable: false },
  { rule: 'overtime_threshold', label: RULE_LABELS.overtime_threshold, nonNegotiable: false },
  { rule: 'hours_shortfall', label: RULE_LABELS.hours_shortfall, nonNegotiable: false },
  { rule: 'understaffed_below_minimum', label: RULE_LABELS.understaffed_below_minimum, nonNegotiable: false },
  { rule: 'unassessable', label: RULE_LABELS.unassessable, nonNegotiable: false },
  { rule: 'rest_waiver_required', label: RULE_LABELS.rest_waiver_required, nonNegotiable: true },
  { rule: 'worker_declined', label: RULE_LABELS.worker_declined, nonNegotiable: true },
]

export function Autonomy() {
  const autonomy = useStore((s) => s.autonomy)
  const setAutonomy = useStore((s) => s.setAutonomy)
  const busy = useStore((s) => s.busy) || {}
  const busyNow = Boolean(busy.autonomy)
  const t = autonomy?.thresholds

  return (
    <>
      <div className="section-pad">
        <div className="card-title">The dial</div>
        <div className="row-actions" style={{ padding: '8px 0' }}>
          {DIAL_LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              className={`btn ${autonomy?.level === level ? 'btn-primary' : ''}`}
              disabled={busyNow}
              onClick={() => setAutonomy?.(level)?.catch(() => {})}
            >
              {level}
            </button>
          ))}
        </div>

        {t && typeof t.max_unattended_cents === 'number' && (
          <div className="card">
            <div className="card-title">{autonomy.level}'s thresholds</div>
            <div className="card-row">
              <span>Spends per incident, unattended, up to</span>
              <span className="mono">{formatCents(t.max_unattended_cents)}</span>
            </div>
            <div className="card-row">
              <span>Spends per week, unattended, up to</span>
              <span className="mono">{formatCents(t.weekly_budget_cents)}</span>
            </div>
            <div className="card-row">
              <span>Overtime tolerated per worker per week</span>
              <span className="mono">{t.max_overtime_hours.toFixed(1)}h</span>
            </div>
            <div className="card-row">
              <span>May take a worker below good-faith hours by</span>
              <span className="mono">{Math.round(t.max_shortfall_fraction * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      <div className="section-pad">
        <div className="card-title">Fixed at every level — the dial cannot move these</div>
        {RULE_CATALOG.filter((r) => r.nonNegotiable).map((r) => (
          <div className="row" key={r.rule}>
            <div className="row-main">
              <span className="row-title">{r.label}</span>
              <span className="row-sub">
                {r.rule === 'rest_waiver_required'
                  ? "Oregon requires the worker's own request or consent before a rest period is "
                    + "shortened; NYC requires written consent for a clopening; Chicago's guidance says "
                    + 'the Right to Rest has no exceptions.'
                  : 'Muster does not ask a worker twice once they have said no.'}
              </span>
            </div>
            <span className="badge badge-critical">fixed at every level</span>
          </div>
        ))}
      </div>

      <div className="section-pad">
        <div className="card-title">Every rule that can stop the agent</div>
        {RULE_CATALOG.filter((r) => !r.nonNegotiable).map((r) => (
          <div className="row" key={r.rule}>
            <div className="row-main">
              <span className="row-title">{r.label}</span>
            </div>
            <span className="badge badge-neutral">moves with the dial</span>
          </div>
        ))}
      </div>
    </>
  )
}

// -- Timeline -----------------------------------------------------------

const KIND_BADGE = {
  model_call: 'badge-neutral',
  tool_call: 'badge-cleared',
  tool_result: 'badge-neutral',
  refusal: 'badge-critical',
}

export function Timeline() {
  const timeline = useStore((s) => s.timeline) || []

  if (timeline.length === 0) return <div className="section-pad"><Empty>No activity recorded yet.</Empty></div>

  return (
    <div className="section-pad">
      {timeline.map((entry, i) => {
        const guarded = entry.kind === 'tool_call' && GUARDED_TOOLS.has(entry.label)
        return (
          <div className="row" key={`${entry.at}-${i}`}>
            <div className="row-main">
              <span className="row-title">
                <span className={`badge ${KIND_BADGE[entry.kind] || 'badge-neutral'}`}>{entry.kind}</span>{' '}
                {entry.label}
                {guarded && <span className="badge badge-held" style={{ marginLeft: 6 }}>guarded</span>}
              </span>
              {entry.detail && Object.keys(entry.detail).length > 0 && (
                <span className="row-sub" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {Object.entries(entry.detail).map(([k, v]) => (
                    <span className="badge badge-neutral" key={k}>
                      {k}: {String(v)}
                    </span>
                  ))}
                </span>
              )}
            </div>
            <span className="row-sub mono">{fmtDateTime(entry.at)}</span>
          </div>
        )
      })}
    </div>
  )
}

// -- Receipts -----------------------------------------------------------

export function Receipts() {
  const world = useStore((s) => s.world)
  const receipts = useStore((s) => s.receipts) || []

  return (
    <>
      <div className="section-pad">
        <a className="btn btn-primary" href={receiptsCsvUrl()}>
          <IconDownload width={16} height={16} /> Download receipts.csv
        </a>
      </div>
      <div className="section-pad">
        {receipts.length === 0 ? (
          <Empty>No receipts yet.</Empty>
        ) : (
          receipts.map((r, i) => (
            <div className="row" key={`${r.shift_id}-${r.at}-${i}`}>
              <div className="row-main">
                <span className="row-title">
                  {workerName(world, r.worker_id)} — {siteName(world, r.site_id)}
                </span>
                <span className="row-sub">
                  {r.kind.replace('_', ' ')} · {r.jurisdiction_code} · {fmtDateTime(r.at)}
                </span>
                <span className="row-sub" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {r.lines.map((line, li) => (
                    <span className="badge badge-neutral" key={li}>
                      {line.clause}: {formatDollarsStr(line.amount)}
                    </span>
                  ))}
                </span>
                {r.carve_outs_applied.length > 0 && (
                  <span className="row-sub">Carve-outs: {r.carve_outs_applied.join(', ')}</span>
                )}
                <span className="row-sub">
                  Decided by {r.decided_by}
                  {r.consent ? ` · consent ${r.consent.outcome}` : ''}
                </span>
              </div>
              <span className="badge badge-cleared mono">{formatDollarsStr(r.total)}</span>
            </div>
          ))
        )}
      </div>
    </>
  )
}
