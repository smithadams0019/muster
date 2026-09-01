# The evals — Muster's safety argument

This directory is not a coverage exercise. It is the case for why Muster's policy
layer can be trusted to act alone within the bounds it claims, made as executable
assertions instead of prose. Three files carry three different parts of that case,
each against `src/muster/policy/rules.py`, `src/muster/domain/carve_outs.py`,
`src/muster/domain/pricing.py` and `src/muster/adapters/simulated.py` exactly as
shipped — no stubs, no mocks of the policy itself.

## What each file asserts

### `test_non_negotiable.py`

That two rules — `rest_waiver_required` and `worker_declined` — fire at every
autonomy level, including `TRUSTED`, and that no threshold in `THRESHOLDS` ever
mentions either rule name (so no future tuning of the dial could quietly loosen
one). This is the file that makes good on the docstring in `policy/rules.py`:
"two rules ignore the dial at every level."

### `test_monotonic.py`

That raising the autonomy dial (`CONSERVATIVE → BALANCED → TRUSTED`) never
*increases* the number of escalations a given cover produces, and that every rule
which fires at `TRUSTED` also fires at `CONSERVATIVE` (a superset relationship, not
just a matching count). Both properties are checked across a 5×4×4 grid of cost,
overtime and shortfall combinations. A dial that surfaced more decisions as you
trusted it more would train an operator to distrust the setting, which is worse
than a dial that does nothing.

### `test_scenarios.py`

Six scenarios an operator would actually describe, each driven through the real
pricing path (`price_change`, `carve_out_applies`, `enumerate_cover_options`) over
`SableCoffee`, the seeded three-site demo world — real workers, real hourly rates,
real rulebooks, real evidence registries:

1. **"the standby list is empty at 6am, and every remaining cover costs money"** —
   both Oregon standby workers decline, so every surviving cover option prices
   above zero.
2. **"the same sick call in Portland, Chicago and New York costs three different
   amounts"** — identical worker index, identical notice, identical frozen clock;
   Oregon prices it $18.50 (an hour at rate), Chicago $20.00 (an hour at rate, at
   that site's own wage), NYC a flat $45.00 — three different formulas, three
   different totals.
3. **"an agent claims the swap was employee-requested, but no request exists"** —
   the claim is made, no `record_worker_request` call was ever made, and the
   priced total is identical to pricing the same change with no claim at all.
4. **"an agent claims the standby carve-out in Chicago, where it does not exist"**
   — Chicago's rulebook (`us-il-chicago.json`) never lists `standby_list` among its
   carve-outs, so the claim is refused before the world is even asked whether the
   worker is on one.
5. **"covering the shift would leave nobody food-safety certified on the floor"**
   — Thursday's close at Sable Wicker is worked, as posted, by a certified
   barista; swapping in an uncertified colleague empties the floor of
   certification for the last five hours before close, and `understaffed_below_
   minimum` fires at `TRUSTED` even though the swap itself is cheap ($18.50).
6. **"the cheapest cover is a clopening, and it is the only one"** — every other
   candidate for the same close declines, leaving a closer who opened the same
   morning as the sole lawful option. It still requires consent, and a claimed
   `WORKER_REQUESTED` carve-out — even backed by real recorded evidence — still
   cannot reach a rest rule in Chicago.

## Why the two non-negotiables are law, not preference

`rest_waiver_required` and `worker_declined` are not conservative product defaults
that a future "more capable" autonomy tier could responsibly relax. Each is a
direct restatement of a legal requirement that names the worker, not the employer,
as the only party who can waive it:

- **Oregon** requires the worker's own request or consent before a rest period is
  shortened (BOLI predictive scheduling guidance,
  <https://www.oregon.gov/boli/workers/pages/predictive-scheduling.aspx>).
- **New York City** requires *written* consent for a clopening, and DCWP's own
  rules define consent as the worker's agreement given after a meaningful
  opportunity to decline — not silence, not an unanswered notification
  (<https://portal.311.nyc.gov/article/?kanumber=KA-02719>).
- **Chicago's** own guidance states plainly that the Right to Rest has no
  exceptions (OLS Fair Workweek FAQ,
  <https://www.chicago.gov/content/dam/city/depts/bacp/OSL/faqfairworkweek09252025.pdf>).

An agent that could waive a rest period or re-offer a declined shift on a worker's
behalf, at any autonomy setting, would not be a more capable product — it would be
an unlawful one. `test_non_negotiable.py` is the assertion that no code path,
present or future via `THRESHOLDS`, can reach that outcome.

## Step 4: proving the evals can fail

An eval suite that passes whatever the policy does is worse than none — it reports
what you want to hear. Each break below was applied to the working tree, the named
test was run and its result recorded, and the file was then restored from a
pre-break copy and reverified green. `git diff --stat` against `src/` at the end
of the exercise showed no changes.

| # | break | test that must go red | observed result |
|---|---|---|---|
| 1 | remove `requires_rest_waiver` from `evaluate` (`policy/rules.py`) | `test_the_only_cover_is_a_clopening_and_it_is_free` | **RED, as predicted.** All three parametrized cases (`conservative`, `balanced`, `trusted`) failed with `AssertionError: assert 'rest_waiver_required' in set()`. Reverted; green again. |
| 2 | remove `worker_declined` from `evaluate` (`policy/rules.py`) | `test_the_worker_already_said_no_once` | **RED, as predicted.** All three parametrized cases failed the same way, for `worker_declined`. Reverted; green again. |
| 3 | set `CONSERVATIVE.max_unattended_cents` to `100000` (`policy/rules.py`) | `test_escalations_never_increase_as_autonomy_rises` | **Did not go red — a real finding, recorded honestly rather than papered over.** The named test still passed: raising the conservative cost ceiling doesn't add an escalation, it *swaps* which rule fires (`cost_over_budget` → `weekly_budget_exhausted`, since `weekly_budget_cents` is still `0` and the `if/elif` in `evaluate` always falls through to it), so the escalation *count* per autonomy level is unchanged and the monotonic-count property still holds. The break was still caught — by the file's other test, `test_every_rule_that_fires_at_trusted_also_fires_at_conservative`, which went RED with `assert {'cost_over_budget'} <= {'weekly_budget_exhausted'}` for a $300 cover: at `TRUSTED` the cost trips `cost_over_budget`, but at the broken `CONSERVATIVE` the same cost no longer does, so the "trusted's rules are a subset of conservative's" guarantee breaks even though the count doesn't. `tests/evals/test_monotonic.py` as a whole still catches this break; the specific test named in the plan's table does not, in isolation, for this codebase's current `if/elif` structure. Reverted; both tests green again. |
| 4 | make `carve_out_applies` return `True` unconditionally (`domain/carve_outs.py`) | the two carve-out scenario tests | **RED, as predicted.** `test_an_agent_claims_the_swap_was_employee_requested_but_no_request_exists` failed (`claimed.carve_outs_applied` was no longer `()`); `test_an_agent_claims_the_standby_carve_out_in_chicago_where_it_does_not_exist` failed (`carve_out_applies(...) is False` became `True is False`). Reverted; both green again. |
| 5 | drop the `rest_has_carve_outs` check from `carve_out_applies` (`domain/carve_outs.py`) | "the cheapest cover is a clopening" in Chicago | **RED, as predicted.** `test_the_cheapest_cover_is_a_clopening_and_it_is_the_only_one` failed at the final assertion: with the check removed, `carve_out_applies(..., against_rest=True)` returned `True` for a `WORKER_REQUESTED` claim backed by real recorded evidence in Chicago — exactly the outcome Chicago's "no exceptions" guidance forbids. Reverted; green again. |

Final state: `git diff --stat src/` shows no changes anywhere under `src/`. The
only files this task added are the four under `tests/evals/`.

### A note on break 3

The plan's break table names `test_escalations_never_increase_as_autonomy_rises`
as the test that must go red for the conservative-ceiling break. Run against this
codebase's actual `evaluate()` — which checks `cost_over_budget` and
`weekly_budget_exhausted` as an `if`/`elif` pair — that specific test stays green,
because the broken threshold doesn't add an escalation, it substitutes one rule
name for another at the same count. The break is real and is still caught, just by
`test_every_rule_that_fires_at_trusted_also_fires_at_conservative` in the same
file rather than by the count-only test. Recording this rather than the plan's
predicted result is the point of the exercise: an eval suite is only a safety
argument if its failures are reported honestly, including when a break lands on a
different assertion than expected.
