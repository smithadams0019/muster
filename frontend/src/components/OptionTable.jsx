// Side-by-side breakdown of what's under consideration for one held decision.
//
// This is presentational only — it never carries its own approve/decline
// action. The API does not let a console approve one specific priced option;
// it only lets an operator answer the escalation that paused the run. Giving
// this table its own clickable "approve" per row would invite exactly the
// bypass the project's non-negotiable rule exists to prevent, so it renders
// rows and nothing else can be clicked through here.
//
// A row that needs a worker's own agreement is rendered as a <span>, not a
// <button> — inert status text ("needs <name>'s yes") that cannot be clicked
// through. That is the whole point: a manager cannot approve a worker's own
// consent into existence.
//
// Local styles only (own <style> block, `ot-` prefixed classes) — this file
// does not depend on icons.jsx or the shared stylesheet, both of which are
// being replaced concurrently with this file.

function TableStyle() {
  return (
    <style>{`
      .ot-wrap { overflow-x: auto; margin: 10px 0; border: 1px solid var(--line); border-radius: var(--r-sm); }
      .ot-table { width: 100%; border-collapse: collapse; font-family: var(--sans); font-size: 13px; }
      .ot-table th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
        color: var(--ink-3); padding: 8px 10px; background: var(--surface-2); border-bottom: 1px solid var(--line); }
      .ot-table td { padding: 9px 10px; border-bottom: 1px solid var(--line); color: var(--ink); vertical-align: top; }
      .ot-table tr:last-child td { border-bottom: none; }
      .ot-mono { font-family: var(--mono); white-space: nowrap; }
      .ot-detail { font-size: 12px; color: var(--ink-2); margin-top: 2px; }
      .ot-pill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: var(--r-pill);
        font-size: 11.5px; font-weight: 600; white-space: nowrap; }
      .ot-pill-consent { background: var(--consent-bg); color: var(--consent); border: 1px solid var(--consent-line); }
      .ot-pill-clear { background: var(--posted-bg); color: var(--posted); border: 1px solid var(--posted-line); }
    `}</style>
  )
}

export default function OptionTable({ options }) {
  if (!options || options.length === 0) return null

  return (
    <div className="ot-wrap">
      <TableStyle />
      <table className="ot-table">
        <thead>
          <tr>
            <th>Worker</th>
            <th>Cost</th>
            <th>Clause</th>
            <th>Consent</th>
          </tr>
        </thead>
        <tbody>
          {options.map((opt) => (
            <tr key={opt.id}>
              <td>{opt.worker || '—'}</td>
              <td className={opt.costIsExact ? 'ot-mono' : ''}>{opt.cost}</td>
              <td>
                {opt.clause}
                {opt.detail && <div className="ot-detail">{opt.detail}</div>}
              </td>
              <td>
                {opt.consentRequired ? (
                  // Deliberately a <span>, not a <button>: nothing here is
                  // clickable. A manager cannot approve a worker's own yes.
                  <span
                    className="ot-pill ot-pill-consent"
                    role="status"
                    aria-label={opt.consentLabel || "needs this person's yes"}
                  >
                    ⚠ {opt.consentLabel || "needs this person's yes"}
                  </span>
                ) : (
                  <span className="ot-pill ot-pill-clear">✓ no consent needed</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
