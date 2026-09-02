// Modelled on Deputy's "Auto Build" dialog: a title, an indeterminate
// progress bar (the DRAFT run is a real Bedrock agent and can take a minute
// or more — there is nothing honest to measure progress against), a live
// status line, and a final outcome.
//
// The one rule this file exists to enforce: it never reports success for a
// run that drafted nothing. `draftWeek` can resolve in three shapes —
// paused on a decision, posted something, or posted nothing — and only the
// middle one gets the "done" treatment. A run that came back "drafted" but
// added zero shifts (the demo's already-posted week is the common way this
// happens) is rendered exactly like a run that failed: plainly, with no
// green tick.

import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store.js'

const PHASES = [
  'Reading the posted rota…',
  'Checking demand against coverage…',
  'Weighing lawful cover options…',
  'Checking autonomy limits…',
  'Writing the draft…',
]

function siteName(world, siteId) {
  return world?.sites?.find((s) => s.site_id === siteId)?.name || siteId
}

function ModalStyle() {
  return (
    <style>{`
      .dm-overlay { position: fixed; inset: 0; background: color-mix(in srgb, var(--ink) 45%, transparent);
        display: flex; align-items: center; justify-content: center; z-index: 50; padding: 16px; }
      .dm-modal { width: 420px; max-width: 100%; background: var(--surface); border: 1px solid var(--line-strong);
        border-radius: var(--r); box-shadow: 0 12px 40px color-mix(in srgb, var(--ink) 24%, transparent); font-family: var(--sans); }
      .dm-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px;
        border-bottom: 1px solid var(--line); }
      .dm-title { font-size: 14px; font-weight: 700; color: var(--ink); }
      .dm-close { border: none; background: none; color: var(--ink-2); font-size: 18px; line-height: 1; cursor: pointer; padding: 2px 4px; }
      .dm-body { padding: 18px 16px 20px; }
      .dm-progress { height: 6px; border-radius: 999px; background: var(--surface-2); overflow: hidden; margin-bottom: 14px; }
      .dm-progress-bar { width: 40%; height: 100%; border-radius: 999px; background: var(--accent);
        animation: dm-indeterminate 1.3s ease-in-out infinite; }
      @keyframes dm-indeterminate { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }
      .dm-status { font-size: 13px; color: var(--ink); margin: 0 0 6px; }
      .dm-phase { font-size: 12.5px; color: var(--ink-2); margin: 0 0 14px; }
      .dm-note { font-size: 11.5px; color: var(--ink-3); margin: 0; }
      .dm-result-title { font-size: 14px; font-weight: 700; margin: 0 0 4px; }
      .dm-result-message { font-size: 13px; color: var(--ink-2); margin: 0 0 16px; }
      .dm-result-drafted .dm-result-title { color: var(--posted); }
      .dm-result-held .dm-result-title, .dm-result-empty .dm-result-title, .dm-result-error .dm-result-title { color: var(--ink); }
      .dm-actions { display: flex; gap: 8px; justify-content: flex-end; }
      .dm-btn { font-size: 12.5px; font-weight: 600; padding: 7px 14px; border-radius: var(--r-pill);
        border: 1px solid var(--line-strong); background: var(--surface); color: var(--ink); cursor: pointer; }
      .dm-btn-primary { border-color: var(--accent-line); background: var(--accent); color: var(--accent-ink); }
    `}</style>
  )
}

export default function DraftingModal({ open, siteId, onClose }) {
  const world = useStore((s) => s.world)
  const busy = useStore((s) => s.busy) || {}
  const schedules = useStore((s) => s.schedules) || {}
  const draftWeek = useStore((s) => s.draftWeek)
  const go = useStore((s) => s.go)

  const key = `draft:${siteId}`
  const alreadyRunning = Boolean(busy[key])

  const [outcome, setOutcome] = useState(null)
  const [phaseIdx, setPhaseIdx] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const startedRef = useRef(false)
  const beforeCountRef = useRef(0)
  const borrowedRef = useRef(false) // true if another trigger (e.g. the toolbar) started this run
  const wasRunningRef = useRef(false)

  useEffect(() => {
    if (!open || !siteId || startedRef.current) return
    startedRef.current = true
    beforeCountRef.current = schedules[siteId]?.shifts?.length ?? 0
    setOutcome(null)

    if (alreadyRunning) {
      // Someone else (the toolbar's own "Draft with Muster") already kicked
      // this off for this site. Don't call draftWeek a second time — just
      // watch busy flip back to false below and read the outcome then.
      borrowedRef.current = true
      return
    }

    draftWeek(siteId)
      .then((res) => {
        const after = useStore.getState().schedules[siteId]
        const afterCount = after?.shifts?.length ?? 0
        if (res?.status === 'awaiting_decision') {
          setOutcome({ kind: 'held', message: 'Held for your review before the draft can finish.' })
        } else if (afterCount > beforeCountRef.current) {
          const added = afterCount - beforeCountRef.current
          setOutcome({ kind: 'drafted', message: `Week drafted — ${added} shift${added === 1 ? '' : 's'} added.` })
        } else {
          setOutcome({ kind: 'empty', message: 'Muster finished but drafted nothing for this week.' })
        }
      })
      .catch((err) => {
        setOutcome({ kind: 'error', message: err?.message || 'Could not draft the week.' })
      })
    // Only re-run when the modal is opened for a (possibly new) site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, siteId])

  // A run this modal only borrowed (didn't start itself) has no promise to
  // await here, so watch the shared busy flag instead: once it flips back
  // to false, the store has already refreshed and we can read the result.
  useEffect(() => {
    if (open && borrowedRef.current && wasRunningRef.current && !alreadyRunning && !outcome) {
      const after = useStore.getState().schedules[siteId]
      const afterCount = after?.shifts?.length ?? 0
      if (afterCount > beforeCountRef.current) {
        const added = afterCount - beforeCountRef.current
        setOutcome({ kind: 'drafted', message: `Week drafted — ${added} shift${added === 1 ? '' : 's'} added.` })
      } else {
        setOutcome({ kind: 'empty', message: "Muster finished. Check Decisions if it's still waiting on you." })
      }
      borrowedRef.current = false
    }
    wasRunningRef.current = alreadyRunning
  }, [alreadyRunning, open, outcome, siteId])

  useEffect(() => {
    if (!open) {
      startedRef.current = false
      borrowedRef.current = false
      wasRunningRef.current = false
      setOutcome(null)
      setPhaseIdx(0)
      setElapsed(0)
    }
  }, [open])

  useEffect(() => {
    if (!open || outcome) return
    const t = setInterval(() => {
      setElapsed((s) => s + 1)
      setPhaseIdx((i) => (i + 1) % PHASES.length)
    }, 2600)
    return () => clearInterval(t)
  }, [open, outcome])

  if (!open) return null

  const name = siteName(world, siteId)
  const running = !outcome

  return (
    <div
      className="dm-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <ModalStyle />
      <div className="dm-modal" role="dialog" aria-modal="true" aria-label="Auto build">
        <div className="dm-head">
          <span className="dm-title">Auto build — {name}</span>
          <button type="button" className="dm-close" onClick={() => onClose?.()} aria-label="Close">×</button>
        </div>
        <div className="dm-body">
          {running ? (
            <>
              <div className="dm-progress"><div className="dm-progress-bar" /></div>
              <p className="dm-status">
                Drafting the week for {name}… this is a real agent call and can take a minute or more.
              </p>
              <p className="dm-phase">{PHASES[phaseIdx]} · running {elapsed}s</p>
              <p className="dm-note">You can close this — Muster keeps running and will tell you when it's done.</p>
            </>
          ) : (
            <>
              <div className={`dm-result dm-result-${outcome.kind}`}>
                <p className="dm-result-title">
                  {outcome.kind === 'drafted' && 'Done'}
                  {outcome.kind === 'held' && 'Paused for you'}
                  {outcome.kind === 'empty' && 'Nothing drafted'}
                  {outcome.kind === 'error' && 'Could not finish'}
                </p>
                <p className="dm-result-message">{outcome.message}</p>
              </div>
              <div className="dm-actions">
                {outcome.kind === 'held' && (
                  <button
                    type="button"
                    className="dm-btn dm-btn-primary"
                    onClick={() => {
                      onClose?.()
                      go?.('decisions')
                    }}
                  >
                    Review the decision
                  </button>
                )}
                <button type="button" className="dm-btn" onClick={() => onClose?.()}>Close</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
