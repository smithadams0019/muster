// Modelled on X's "What's happening?" composer: a textarea-led card, a site
// and shift picker, a kind selector, and a pill-shaped primary submit.
//
// Reports through the store's reportDisruption — never prices or judges
// anything itself. The only timestamp this ever touches is world.now, read
// for display; it never sends one (the API stamps reported_at itself from
// the seeded world clock, not the browser's).
//
// Local styles only (own <style> block, `dc-` prefixed classes) — this file
// does not depend on icons.jsx or the shared stylesheet, both of which are
// being replaced concurrently with this file.

import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../store.js'

const KIND_OPTIONS = [
  { value: 'sick_call', label: 'Sick call' },
  { value: 'no_show', label: 'No-show' },
  { value: 'demand_spike', label: 'Demand spike' },
]

function fmtShiftSpan(startsAt, endsAt) {
  const start = new Date(startsAt)
  const end = new Date(endsAt)
  const day = start.toLocaleDateString(undefined, { weekday: 'short', timeZone: 'UTC' })
  const startTime = start.toLocaleTimeString(undefined, {
    hour: 'numeric', minute: '2-digit', timeZone: 'UTC',
  })
  const endTime = end.toLocaleTimeString(undefined, {
    hour: 'numeric', minute: '2-digit', timeZone: 'UTC',
  })
  return `${day} ${startTime}–${endTime}`
}

function ComposerStyle() {
  return (
    <style>{`
      .dc-overlay { position: fixed; inset: 0; background: color-mix(in srgb, var(--ink) 45%, transparent);
        display: flex; align-items: flex-start; justify-content: center; z-index: 50; padding: 64px 16px; overflow-y: auto; }
      .dc-modal { width: 480px; max-width: 100%; background: var(--surface); border: 1px solid var(--line-strong);
        border-radius: var(--r); box-shadow: 0 12px 40px color-mix(in srgb, var(--ink) 24%, transparent); font-family: var(--sans); }
      .dc-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid var(--line); }
      .dc-title { font-size: 14px; font-weight: 700; color: var(--ink); }
      .dc-close { border: none; background: none; color: var(--ink-2); font-size: 18px; line-height: 1; cursor: pointer; padding: 2px 6px; }
      .dc-form { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
      .dc-field { display: flex; flex-direction: column; gap: 5px; }
      .dc-field label { font-size: 12px; font-weight: 600; color: var(--ink-2); }
      .dc-field textarea, .dc-field select {
        font-family: var(--sans); font-size: 13px; color: var(--ink); background: var(--ground);
        border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: 8px 10px; resize: vertical;
      }
      .dc-error { font-size: 12.5px; color: var(--consent); background: var(--consent-bg);
        border: 1px solid var(--consent-line); border-radius: var(--r-sm); padding: 8px 10px; }
      .dc-actions { display: flex; justify-content: flex-end; }
      .dc-submit { font-size: 13px; font-weight: 700; padding: 9px 18px; border-radius: var(--r-pill);
        border: 1px solid var(--accent-line); background: var(--accent); color: var(--accent-ink); cursor: pointer; }
      .dc-submit:disabled { opacity: 0.55; cursor: default; }
    `}</style>
  )
}

export default function DisruptionComposer({ open, onClose }) {
  const world = useStore((s) => s.world)
  const schedules = useStore((s) => s.schedules)
  const storeError = useStore((s) => s.error)
  const reportDisruption = useStore((s) => s.reportDisruption)

  const sites = world?.sites || []
  const [siteId, setSiteId] = useState('')
  const [shiftId, setShiftId] = useState('')
  const [kind, setKind] = useState('sick_call')
  const [note, setNote] = useState('')
  const [localError, setLocalError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (open && !siteId && sites.length > 0) setSiteId(sites[0].site_id)
  }, [open, sites, siteId])

  const shiftOptions = useMemo(() => {
    const schedule = schedules?.[siteId]
    if (!schedule) return []
    return (schedule.shifts || []).filter((sh) => sh.worker_id)
  }, [schedules, siteId])

  const workerName = (workerId) =>
    world?.workers?.find((w) => w.worker_id === workerId)?.name || workerId

  if (!open) return null

  const canSubmit = Boolean(siteId && shiftId && kind) && !submitting

  async function handleSubmit(e) {
    e.preventDefault()
    setLocalError('')
    if (!shiftId) {
      setLocalError('Pick the shift this disruption affects.')
      return
    }
    setSubmitting(true)
    try {
      await reportDisruption({ kind, shift_id: shiftId, note })
      setNote('')
      setShiftId('')
      onClose?.()
    } catch (err) {
      setLocalError(err?.message || 'Could not report the disruption.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="dc-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <ComposerStyle />
      <div className="dc-modal" role="dialog" aria-modal="true" aria-label="Report a disruption">
        <div className="dc-head">
          <span className="dc-title">What's happening?</span>
          <button type="button" className="dc-close" onClick={() => onClose?.()} aria-label="Close">×</button>
        </div>
        <form className="dc-form" onSubmit={handleSubmit}>
          <div className="dc-field">
            <label htmlFor="disruption-note">Tell Muster what happened</label>
            <textarea
              id="disruption-note"
              rows={4}
              placeholder="e.g. Priya called in sick for the 6am open"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          <div className="dc-field">
            <label htmlFor="disruption-site">Site</label>
            <select
              id="disruption-site"
              value={siteId}
              onChange={(e) => {
                setSiteId(e.target.value)
                setShiftId('')
              }}
            >
              {sites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="dc-field">
            <label htmlFor="disruption-shift">Shift</label>
            <select id="disruption-shift" value={shiftId} onChange={(e) => setShiftId(e.target.value)}>
              <option value="">
                {shiftOptions.length ? 'Choose a shift…' : 'No posted shifts loaded for this site'}
              </option>
              {shiftOptions.map((sh) => (
                <option key={sh.shift_id} value={sh.shift_id}>
                  {workerName(sh.worker_id)} — {fmtShiftSpan(sh.starts_at, sh.ends_at)}
                </option>
              ))}
            </select>
          </div>

          <div className="dc-field">
            <label htmlFor="disruption-kind">Kind</label>
            <select id="disruption-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
              {KIND_OPTIONS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </div>

          {(localError || storeError) && (
            <div className="dc-error">{localError || storeError}</div>
          )}

          <div className="dc-actions">
            <button type="submit" className="dc-submit" disabled={!canSubmit}>
              {submitting ? 'Reporting…' : 'Report it'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
