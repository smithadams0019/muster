// One cell's worth of the Deputy-style week grid: a bordered, tinted card
// with the time range bold on the first line and a small role badge beneath.
//
// Colour is picked by `state` and applied entirely through the five shift-
// state CSS custom properties (--posted/--held/--consent/--open/--off, each
// with a *-bg and *-line partner) — never a literal colour. ScheduleGrid.jsx
// owns the structural CSS (`.sg-shift-card` and friends) in its own local
// <style> block; this file only decides which state maps to which token
// triple and renders the two lines of text.
//
// A "held for you" card is the one interactive state: it is a <button>, and
// clicking it hands off to ScheduleGrid's onClick (which the caller wires to
// `go('decisions')`). Every other state renders as an inert <div> — in
// particular a "needs consent" card is never a button, for the same reason
// OptionTable.jsx never turns a consent-required option into one: a manager
// cannot click a worker's own yes into existence.

const ROLE_TOKENS = {
  shift_lead: { bg: 'var(--role-lead-bg)', line: 'var(--role-lead-line)', ink: 'var(--role-lead)' },
  baker: { bg: 'var(--role-baker-bg)', line: 'var(--role-baker-line)', ink: 'var(--role-baker)' },
  barista: { bg: 'var(--role-barista-bg)', line: 'var(--role-barista-line)', ink: 'var(--role-barista)' },
}

const ROLE_LABELS = { barista: 'Barista', shift_lead: 'Shift lead', baker: 'Baker' }

const STATE_TOKENS = {
  posted: { ink: 'var(--posted)', bg: 'var(--posted-bg)', line: 'var(--posted-line)' },
  held: { ink: 'var(--held)', bg: 'var(--held-bg)', line: 'var(--held-line)' },
  consent: { ink: 'var(--consent)', bg: 'var(--consent-bg)', line: 'var(--consent-line)' },
  open: { ink: 'var(--open)', bg: 'var(--open-bg)', line: 'var(--open-line)' },
  off: { ink: 'var(--off)', bg: 'var(--off-bg)', line: 'var(--off-line)' },
}

const STATE_TITLES = {
  posted: 'Posted',
  held: 'Held for you — open Decisions',
  consent: 'Needs the worker’s own consent',
  open: 'Open — uncovered',
  off: 'Already worked',
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function fmtTime(iso) {
  const d = new Date(iso)
  let h = d.getUTCHours()
  const m = d.getUTCMinutes()
  const ampm = h >= 12 ? 'pm' : 'am'
  h = h % 12
  if (h === 0) h = 12
  return `${h}:${pad2(m)}${ampm}`
}

export default function ShiftCard({ shift, state = 'posted', onClick }) {
  const tokens = STATE_TOKENS[state] || STATE_TOKENS.posted
  const clickable = state === 'held' && typeof onClick === 'function'
  const Tag = clickable ? 'button' : 'div'

  // A week's shape should be readable before any text is, so each role carries
  // its own hue. State still wins: a held or consent-needed shift is coloured by
  // what it needs from a person, not by who works it.
  const roleTokens = ROLE_TOKENS[shift.role] || ROLE_TOKENS.barista
  const useRole = state === 'posted'

  return (
    <Tag
      type={clickable ? 'button' : undefined}
      className={`sg-shift-card${clickable ? ' sg-shift-card-clickable' : ''}`}
      style={{
        '--sg-card-bg': useRole ? roleTokens.bg : tokens.bg,
        '--sg-card-line': useRole ? roleTokens.line : tokens.line,
        '--sg-card-ink': useRole ? roleTokens.ink : tokens.ink,
      }}
      onClick={clickable ? onClick : undefined}
      title={STATE_TITLES[state] || undefined}
    >
      <span className="sg-shift-time">
        {fmtTime(shift.starts_at)} – {fmtTime(shift.ends_at)}
      </span>
      <span className="sg-shift-role">
        {state === 'held' && <span className="sg-shift-dot" aria-hidden="true" />}
        {ROLE_LABELS[shift.role] || shift.role}
      </span>
    </Tag>
  )
}
