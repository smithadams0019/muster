// The seven screens of the Muster console: Schedule, Decisions, Consent,
// People, Autonomy, Timeline, Receipts.
//
// App.jsx (owned by another agent in this same task) mounts exactly one of
// these per route and owns the global loading skeleton and error strip — a
// screen only ever renders once `loading` is false.
//
// Two rules hold across every screen in this file, and in ScheduleGrid.jsx,
// ShiftCard.jsx and DraftingModal.jsx alongside it:
//   1. Nothing here prices anything or evaluates a policy rule. Every number
//      rendered either came straight off an API response, or is a plain sum
//      / comparison of numbers the API already computed (a week's receipt
//      totals against a threshold, a shift's duration from two timestamps).
//   2. "Now" always means world.now, read from the store. This file never
//      calls `new Date()` with no argument.
//
// Styling is entirely local: a single <style> block (`ScreenStyle`, `vw-`
// prefixed classes) built only from the design tokens in tokens.css, plus
// inline styles for genuinely dynamic values. Nothing here depends on
// styles.css or icons.jsx, both of which are being replaced concurrently
// with this file — small glyphs (✓ ⚠ ▾ ⬇) stand in for icons.

import { useMemo, useState } from 'react'
import { useStore } from './store.js'
import { receiptsCsvUrl } from './api.js'
import OptionTable from './components/OptionTable.jsx'
import ScheduleGrid from './components/ScheduleGrid.jsx'

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

// -- shared local styling --------------------------------------------------
// Every class below is defined here, in this file, and nowhere else. None of
// it depends on the shared stylesheet the other agent is replacing.

function ScreenStyle() {
  return (
    <style>{`
      .vw-pad { padding: 18px 20px; display: flex; flex-direction: column; gap: 16px; font-family: var(--sans); }
      .vw-lede { font-size: 14px; color: var(--ink-2); margin: 0; }
      .vw-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); padding: 14px 16px; }
      .vw-card-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
        color: var(--ink-3); margin-bottom: 8px; }
      .vw-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
        padding: 10px 0; border-bottom: 1px solid var(--line); }
      .vw-row:last-child { border-bottom: none; }
      .vw-row-main { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
      .vw-row-title { font-size: 13.5px; font-weight: 600; color: var(--ink); }
      .vw-row-sub { font-size: 12.5px; color: var(--ink-2); }
      .vw-row-actions { display: flex; align-items: center; gap: 8px; flex: none; flex-wrap: wrap; }
      .vw-mono { font-family: var(--mono); }
      .vw-empty { padding: 20px 0; color: var(--ink-3); font-size: 13px; }

      .vw-btn { font-family: var(--sans); font-size: 12.5px; font-weight: 600; padding: 7px 14px;
        border-radius: var(--r-pill); border: 1px solid var(--line-strong); background: var(--surface);
        color: var(--ink); cursor: pointer; }
      .vw-btn:disabled { opacity: 0.55; cursor: default; }
      .vw-btn-primary { border-color: var(--accent-line); background: var(--accent); color: var(--accent-ink); }
      .vw-btn-danger { border-color: var(--consent-line); background: var(--consent-bg); color: var(--consent); }
      .vw-btn-sm { padding: 5px 11px; font-size: 12px; }

      .vw-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: var(--r-pill);
        font-size: 11.5px; font-weight: 600; white-space: nowrap; }
      .vw-badge-held { background: var(--held-bg); color: var(--held); border: 1px solid var(--held-line); }
      .vw-badge-consent { background: var(--consent-bg); color: var(--consent); border: 1px solid var(--consent-line); }
      .vw-badge-posted { background: var(--posted-bg); color: var(--posted); border: 1px solid var(--posted-line); }
      .vw-badge-open { background: var(--open-bg); color: var(--open); border: 1px solid var(--open-line); }
      .vw-badge-neutral { background: var(--surface-2); color: var(--ink-2); border: 1px solid var(--line); }

      .vw-table-wrap { overflow-x: auto; }
      .vw-table { width: 100%; border-collapse: collapse; font-size: 13px; }
      .vw-table th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
        color: var(--ink-3); padding: 8px 10px; border-bottom: 1px solid var(--line-strong); }
      .vw-table td { padding: 9px 10px; border-bottom: 1px solid var(--line); color: var(--ink); }

      .vw-field { display: flex; flex-direction: column; gap: 5px; padding: 8px 0; }
      .vw-field label { font-size: 12px; font-weight: 600; color: var(--ink-2); }
      .vw-field textarea { font-family: var(--sans); font-size: 13px; color: var(--ink); background: var(--ground);
        border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: 8px 10px; resize: vertical; }

      .vw-alert { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border-radius: var(--r-sm);
        background: var(--consent-bg); border: 1px solid var(--consent-line); color: var(--consent); font-size: 13px; }

      .vw-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
      .vw-tab { font-family: var(--sans); font-size: 12.5px; font-weight: 600; padding: 6px 13px;
        border-radius: var(--r-pill); border: 1px solid var(--line-strong); background: var(--surface);
        color: var(--ink-2); cursor: pointer; }
      .vw-tab-active { background: var(--accent); border-color: var(--accent-line); color: var(--accent-ink); }

      .vw-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
      .vw-chip { font-family: var(--mono); font-size: 11px; background: var(--surface-2); color: var(--ink-2);
        border: 1px solid var(--line); border-radius: var(--r-sm); padding: 2px 8px; }

      .vw-avatar { width: 30px; height: 30px; border-radius: 999px; background: var(--accent-soft);
        color: var(--accent); border: 1px solid var(--accent-line); display: flex; align-items: center; justify-content: center;
        font-size: 11.5px; font-weight: 700; flex: none; }
    `}</style>
  )
}

function Empty({ children }) {
  return <div className="vw-empty">{children}</div>
}

function initials(name) {
  const stripped = (name || '').replace(/\s*\([^)]*\)\s*$/, '').trim()
  const parts = stripped.split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

// -- Schedule ---------------------------------------------------------------
// The product's face: a Deputy-style week grid, one site at a time.

export function Schedule({ siteId, groupBy, week }) {
  const world = useStore((s) => s.world)
  // The site comes from the toolbar picker, which is the only site selector in
  // the product. This screen used to carry its own tab row as well, so the page
  // had two controls for one choice and they could disagree.
  const sites = world?.sites || []
  const activeSiteId = sites.some((s) => s.site_id === siteId) ? siteId : sites[0]?.site_id

  return (
    <div className="vw-pad">
      <ScreenStyle />
      {sites.length === 0 ? (
        <Empty>No sites yet.</Empty>
      ) : (
        activeSiteId && <ScheduleGrid siteId={activeSiteId} groupBy={groupBy} week={week} />
      )}
    </div>
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

  // Two different things pause a run and they are not the same shape. A cover
  // decision is about one shift and has priced options behind it. A posting
  // decision is about a whole week and has no worker and no per-option cost, so
  // rendering it through the options table produced an em dash for the worker,
  // the rule's own sentence in the money column, and "no consent needed" beside
  // it — three claims about a cover that does not exist.
  const isPosting = decision.kind === 'posting'
  const subject = decision.subject || {}

  return (
    <div className="vw-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span className="vw-badge vw-badge-held">held</span>
        <span className="vw-row-sub">
          {isPosting ? 'posting next week' : 'covering a shift'}
        </span>
      </div>
      <div className="vw-row-title" style={{ fontSize: 14.5 }}>{RULE_LABELS[decision.rule] || decision.rule}</div>
      {isPosting ? (
        <div className="vw-row-sub">
          {subject.site_name || subject.site_id} · Muster drafted the week and stopped before posting it.
        </div>
      ) : (
        located && (
          <div className="vw-row-sub">
            {siteName(world, located.site_id)} · {ROLE_LABELS[located.shift.role] || located.shift.role} ·{' '}
            {fmtDateTime(located.shift.starts_at)}–{fmtTime(located.shift.ends_at)}
          </div>
        )
      )}

      {!isPosting && <OptionTable options={options} />}

      <div style={{ padding: '10px 0' }}>
        <div className="vw-card-title">Rules that fired</div>
        {(decision.rule_hits || []).map((h, i) => (
          <div className="vw-row" key={`${h.rule}-${i}`}>
            <div className="vw-row-main">
              <span className="vw-row-title">{RULE_LABELS[h.rule] || h.rule}</span>
              <span className="vw-row-sub">{h.detail}</span>
            </div>
            {NON_NEGOTIABLE.has(h.rule) && <span className="vw-badge vw-badge-consent">fixed at every level</span>}
          </div>
        ))}
      </div>

      {nonNegotiable && (
        <div className="vw-alert">
          ⚠ This needs the worker's own yes — a manager cannot approve it away. Check{' '}
          <button type="button" className="vw-btn vw-btn-sm" onClick={() => go?.('consent')}>Consent</button>,
          or decline to have Muster try another route.
        </div>
      )}

      <div className="vw-field">
        <label htmlFor={`note-${decision.decision_id}`}>Note (recorded against the operator)</label>
        <textarea
          id={`note-${decision.decision_id}`}
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Why you're approving or declining"
        />
      </div>

      <div className="vw-row-actions">
        <button
          type="button"
          className="vw-btn vw-btn-primary"
          disabled={nonNegotiable || busyNow}
          title={nonNegotiable ? "Needs the worker's own consent" : undefined}
          onClick={() => answer('approve')}
        >
          Approve
        </button>
        <button type="button" className="vw-btn vw-btn-danger" disabled={busyNow} onClick={() => answer('decline')}>
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
    <div className="vw-pad">
      <ScreenStyle />
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

  return (
    <div className="vw-pad">
      <ScreenStyle />
      {consent.length === 0 ? (
        <Empty>No outstanding consent asks.</Empty>
      ) : (
        <div className="vw-card">
          {consent.map((c) => {
            const now = world?.now ? new Date(world.now) : null
            const expired = now ? new Date(c.expires_at) <= now : false
            const busyNow = Boolean(busy[`consent:${c.request_id}`])

            return (
              <div className="vw-row" key={c.request_id}>
                <div className="vw-row-main">
                  <span className="vw-row-title">
                    {workerName(world, c.worker_id)} — {c.kind.replace('_', ' ')}
                  </span>
                  <span className="vw-row-sub">{c.what_it_means}</span>
                  <span className="vw-row-sub">
                    Owed {formatDollarsStr(c.premium_owed)} · asked {fmtDateTime(c.asked_at)} · expires{' '}
                    {fmtDateTime(c.expires_at)}
                  </span>
                </div>
                <div className="vw-row-actions">
                  {expired ? (
                    <span className="vw-badge vw-badge-consent">expired — final</span>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="vw-btn vw-btn-sm"
                        disabled={busyNow}
                        onClick={() => answerConsent?.(c.request_id, 'granted')?.catch(() => {})}
                      >
                        They said yes
                      </button>
                      <button
                        type="button"
                        className="vw-btn vw-btn-sm vw-btn-danger"
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
      )}
    </div>
  )
}

// -- People ---------------------------------------------------------------

export function People() {
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
    <div className="vw-pad">
      <ScreenStyle />
      <div className="vw-card">
        The standby-list carve-out is Oregon-only — it exists nowhere else in the rulebook.
      </div>

      {workers.length === 0 ? (
        <Empty>No roster yet.</Empty>
      ) : (
        [...bySite.entries()].map(([siteId, roster]) => (
          <div className="vw-card" key={siteId}>
            <div className="vw-card-title">{siteName(world, siteId)}</div>
            <div className="vw-table-wrap">
              <table className="vw-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Rate</th>
                    <th>Good-faith hours</th>
                    <th>Certifications</th>
                    <th>Standby list</th>
                  </tr>
                </thead>
                <tbody>
                  {roster.map((w) => (
                    <tr key={w.worker_id}>
                      <td><span className="vw-avatar">{initials(w.name)}</span></td>
                      <td>{w.name}</td>
                      <td>{ROLE_LABELS[w.role] || w.role}</td>
                      <td className="vw-mono">{formatDollarsStr(w.hourly_rate)}/hr</td>
                      <td>{w.good_faith_hours}h</td>
                      <td>
                        {Array.isArray(w.certifications) && w.certifications.length > 0
                          ? <span className="vw-chips">{w.certifications.map((c) => (
                              <span className="vw-chip" key={c}>{c}</span>
                            ))}</span>
                          : '—'}
                      </td>
                      <td>
                        {typeof w.on_standby_list === 'boolean'
                          ? (w.on_standby_list
                              ? <span className="vw-badge vw-badge-posted">on standby list</span>
                              : '—')
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
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
    <div className="vw-pad">
      <ScreenStyle />
      <div className="vw-card">
        <div className="vw-card-title">The dial</div>
        <div className="vw-row-actions" style={{ padding: '4px 0 12px' }}>
          {DIAL_LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              className={`vw-btn${autonomy?.level === level ? ' vw-btn-primary' : ''}`}
              disabled={busyNow}
              onClick={() => setAutonomy?.(level)?.catch(() => {})}
            >
              {level}
            </button>
          ))}
        </div>

        {t && typeof t.max_unattended_cents === 'number' && (
          <div>
            <div className="vw-row">
              <span className="vw-row-sub">Spends per incident, unattended, up to</span>
              <span className="vw-mono">{formatCents(t.max_unattended_cents)}</span>
            </div>
            <div className="vw-row">
              <span className="vw-row-sub">Spends per week, unattended, up to</span>
              <span className="vw-mono">{formatCents(t.weekly_budget_cents)}</span>
            </div>
            <div className="vw-row">
              <span className="vw-row-sub">Overtime tolerated per worker per week</span>
              <span className="vw-mono">{t.max_overtime_hours.toFixed(1)}h</span>
            </div>
            <div className="vw-row">
              <span className="vw-row-sub">May take a worker below good-faith hours by</span>
              <span className="vw-mono">{Math.round(t.max_shortfall_fraction * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      <div className="vw-card">
        <div className="vw-card-title">Fixed at every level — the dial cannot move these</div>
        {RULE_CATALOG.filter((r) => r.nonNegotiable).map((r) => (
          <div className="vw-row" key={r.rule}>
            <div className="vw-row-main">
              <span className="vw-row-title">{r.label}</span>
              <span className="vw-row-sub">
                {r.rule === 'rest_waiver_required'
                  ? "Oregon requires the worker's own request or consent before a rest period is "
                    + "shortened; NYC requires written consent for a clopening; Chicago's guidance says "
                    + 'the Right to Rest has no exceptions.'
                  : 'Muster does not ask a worker twice once they have said no.'}
              </span>
            </div>
            <span className="vw-badge vw-badge-consent">fixed at every level</span>
          </div>
        ))}
      </div>

      <div className="vw-card">
        <div className="vw-card-title">Every rule that can stop the agent</div>
        {RULE_CATALOG.filter((r) => !r.nonNegotiable).map((r) => (
          <div className="vw-row" key={r.rule}>
            <span className="vw-row-title">{r.label}</span>
            <span className="vw-badge vw-badge-neutral">moves with the dial</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// -- Timeline -----------------------------------------------------------

const KIND_BADGE = {
  model_call: 'vw-badge-neutral',
  tool_call: 'vw-badge-posted',
  tool_result: 'vw-badge-neutral',
  refusal: 'vw-badge-consent',
}

export function Timeline() {
  const timeline = useStore((s) => s.timeline) || []

  return (
    <div className="vw-pad">
      <ScreenStyle />
      {timeline.length === 0 ? (
        <Empty>No activity recorded yet.</Empty>
      ) : (
        <div className="vw-card">
          {timeline.map((entry, i) => {
            const guarded = entry.kind === 'tool_call' && GUARDED_TOOLS.has(entry.label)
            return (
              <div className="vw-row" key={`${entry.at}-${i}`}>
                <div className="vw-row-main">
                  <span className="vw-row-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className={`vw-badge ${KIND_BADGE[entry.kind] || 'vw-badge-neutral'}`}>{entry.kind}</span>
                    {entry.label}
                    {guarded && <span className="vw-badge vw-badge-held">guarded</span>}
                  </span>
                  {entry.detail && Object.keys(entry.detail).length > 0 && (
                    <span className="vw-chips">
                      {Object.entries(entry.detail).map(([k, v]) => (
                        <span className="vw-chip" key={k}>{k}: {String(v)}</span>
                      ))}
                    </span>
                  )}
                </div>
                <span className="vw-row-sub vw-mono">{fmtDateTime(entry.at)}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// -- Receipts -----------------------------------------------------------

export function Receipts() {
  const world = useStore((s) => s.world)
  const receipts = useStore((s) => s.receipts) || []

  return (
    <div className="vw-pad">
      <ScreenStyle />
      <a className="vw-btn vw-btn-primary" href={receiptsCsvUrl()} style={{ alignSelf: 'flex-start' }}>
        ⬇ Download receipts.csv
      </a>

      {receipts.length === 0 ? (
        <Empty>No receipts yet.</Empty>
      ) : (
        <div className="vw-card">
          {receipts.map((r, i) => (
            <div className="vw-row" key={`${r.shift_id}-${r.at}-${i}`}>
              <div className="vw-row-main">
                <span className="vw-row-title">
                  {workerName(world, r.worker_id)} — {siteName(world, r.site_id)}
                </span>
                <span className="vw-row-sub">
                  {r.kind.replace('_', ' ')} · {r.jurisdiction_code} · {fmtDateTime(r.at)}
                </span>
                <span className="vw-chips">
                  {r.lines.map((line, li) => (
                    <span className="vw-chip" key={li}>{line.clause}: {formatDollarsStr(line.amount)}</span>
                  ))}
                </span>
                {r.carve_outs_applied.length > 0 && (
                  <span className="vw-row-sub">Carve-outs: {r.carve_outs_applied.join(', ')}</span>
                )}
                <span className="vw-row-sub">
                  Decided by {r.decided_by}
                  {r.consent ? ` · consent ${r.consent.outcome}` : ''}
                </span>
              </div>
              <span className="vw-badge vw-badge-posted vw-mono">{formatDollarsStr(r.total)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
