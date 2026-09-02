// Modelled on X's "What's happening?" composer: a textarea-led card, a site
// and shift picker, a kind selector, and a pill-shaped primary submit.
//
// Reports through the store's reportDisruption — never prices or judges
// anything itself. The only timestamp this ever touches is world.now, read
// for display; it never sends one (the API stamps reported_at itself from
// the seeded world clock, not the browser's).

import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../store.js'
import { IconClose } from '../icons.jsx'

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
      className="overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label="Report a disruption">
        <div className="modal-header">
          <span className="modal-title">What's happening?</span>
          <button type="button" className="modal-close" onClick={() => onClose?.()} aria-label="Close">
            <IconClose />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="disruption-note">Tell Muster what happened</label>
            <textarea
              id="disruption-note"
              rows={4}
              placeholder="e.g. Priya called in sick for the 6am open"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          <div className="field">
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

          <div className="field">
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

          <div className="field">
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
            <div className="error-strip">{localError || storeError}</div>
          )}

          <div className="row-actions">
            <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
              {submitting ? 'Reporting…' : 'Report it'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
