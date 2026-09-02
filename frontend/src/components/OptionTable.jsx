// Side-by-side breakdown of what's under consideration for one held decision.
//
// This is presentational only — it never carries its own approve/decline
// action. The API does not let a console approve one specific priced option;
// it only lets an operator answer the escalation that paused the run. Giving
// this table its own clickable "approve" per row would invite exactly the
// bypass the project's non-negotiable rule exists to prevent, so it renders
// rows and nothing else can be clicked through here.
//
// A row that needs a worker's own agreement is rendered as inert status text
// ("needs <name>'s yes"), never as a button — that is the whole point.

import { IconAlert, IconCheck } from '../icons.jsx'

export default function OptionTable({ options }) {
  if (!options || options.length === 0) return null

  return (
    <div className="option-table-wrap">
      <table className="table option-table">
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
              <td className={opt.costIsExact ? 'mono' : ''}>{opt.cost}</td>
              <td>{opt.clause}</td>
              <td>
                {opt.consentRequired ? (
                  // Deliberately a <span>, not a <button>: nothing here is
                  // clickable. A manager cannot approve a worker's own yes.
                  <span
                    className="badge badge-held"
                    role="status"
                    aria-label={opt.consentLabel || "needs this person's yes"}
                  >
                    <IconAlert width={14} height={14} />
                    {opt.consentLabel || "needs this person's yes"}
                  </span>
                ) : (
                  <span className="badge badge-cleared">
                    <IconCheck width={14} height={14} />
                    no consent needed
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
