// The bottom legend, pinned to the viewport like Deputy's. A row of
// coloured dots each followed by a count and a label — the same five states
// a shift card can be in, so the dot colours here are literally the tokens
// a card renders with.
//
// Every number is a count of records already in the store. Nothing here
// prices anything or decides whether a rule fired — "unavailable" reads the
// worker_declined tag the backend already attached to a held decision, it
// does not re-derive availability itself.

import { useMemo } from 'react'
import { useStore } from '../store.js'

function useLegendCounts() {
  const schedules = useStore((s) => s.schedules) || {}
  const decisions = useStore((s) => s.decisions) || []
  const consent = useStore((s) => s.consent) || []

  return useMemo(() => {
    const allShifts = Object.values(schedules)
      .filter(Boolean)
      .flatMap((sch) => sch.shifts || [])

    const posted = Object.values(schedules)
      .filter((sch) => sch?.posted_at)
      .reduce((sum, sch) => sum + (sch.shifts || []).length, 0)

    const uncovered = allShifts.filter((sh) => !sh.worker_id).length

    const unavailable = decisions.filter((d) =>
      (d.rule_hits || []).some((h) => h.rule === 'worker_declined'),
    ).length

    return {
      posted,
      held: decisions.length,
      consent: consent.length,
      uncovered,
      unavailable,
    }
  }, [schedules, decisions, consent])
}

const ITEMS = [
  { key: 'posted', label: 'posted', tone: 'posted' },
  { key: 'held', label: 'held for you', tone: 'held' },
  { key: 'consent', label: 'needs consent', tone: 'consent' },
  { key: 'uncovered', label: 'uncovered', tone: 'open' },
  { key: 'unavailable', label: 'unavailable', tone: 'off' },
]

export default function FooterLegend() {
  const counts = useLegendCounts()

  return (
    <footer className="footer-legend">
      {ITEMS.map((item) => (
        <span className="legend-item" key={item.key}>
          <span className={`legend-dot legend-dot-${item.tone}`} aria-hidden="true" />
          {counts[item.key]} {item.label}
        </span>
      ))}
    </footer>
  )
}
