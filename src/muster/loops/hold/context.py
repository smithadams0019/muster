"""What the policy judges, built from the world rather than the agent's arguments.

The agent supplies which shift and which worker; everything that carries
consequence - the premium, the rest gap, whether that worker already said no, what
the week has already cost - is read from the records. An agent that understates a
premium or omits a prior decline is therefore judged on the truth, and the
guarantee in the README survives contact with a model that gets it wrong.

Returning None means "unassessable", which the policy turns into an escalation. It
never means "fine".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from muster.adapters.base import WorldAdapter
from muster.domain.options import enumerate_cover_options
from muster.domain.pricing import price_change
from muster.domain.staffing import meets_minimums
from muster.domain.types import AutonomyLevel, ChangeKind, Money
from muster.persistence.consent import ConsentStore
from muster.policy.escalation import GUARDED_TOOLS
from muster.policy.rules import CoverContext
from muster.rulebook.loader import for_code


#: Guarded because they reach a person, but they create no new money and commit
#: nothing. `notify_worker` tells someone about a cover that is already in the
#: ledger; the cost was approved when it was assigned, and charging it again at
#: notification time would ask the operator to approve one decision twice.
#:
#: `request_consent` is here for a stronger reason. Asking a worker whether they
#: will waive their rest period is not waiving it - it is the one lawful route to
#: a cover that needs one, and the opposite of deciding on their behalf. Judged as
#: though it were the cover itself, the ask tripped `rest_waiver_required`, which
#: no autonomy level can clear, so the operator approved the ask, the run resumed,
#: and the policy raised the same question about the same ask. The rule belongs on
#: `assign_cover`, where a waiver would actually be relied on, and it is enforced
#: there. Asking twice is prevented too, but by the ConsentStore, which raises.
_CREATES_NO_LIABILITY = frozenset({"notify_worker", "request_consent"})


def build_hold_context_provider(
    world: WorldAdapter,
    ledger: list[dict[str, Any]],
    consent: ConsentStore,
    level: AutonomyLevel,
) -> Callable[[str, dict[str, Any]], CoverContext | None]:
    def provide(tool_name: str, args: dict[str, Any]) -> CoverContext | None:
        if tool_name not in GUARDED_TOOLS:
            return None

        if tool_name in _CREATES_NO_LIABILITY:
            # Telling a worker about a change that is already committed creates
            # no new liability, so pricing it charges the operator twice for one
            # decision: they approved a $45 cover, and then notifying the worker
            # asked them to approve the same $45 again. The dependency guard has
            # already refused any notification without an approved cover behind
            # it, so there is nothing left here for the policy to protect.
            return CoverContext(
                cost=Money.zero(), week_spend=Money.zero(), overtime_hours=0.0,
                shortfall_fraction=0.0, requires_rest_waiver=False,
                worker_declined=False, meets_role_minimum=True,
                meets_certification_minimum=True, assessable=True,
            )

        shift = world.shift(args.get("shift_id", ""))
        worker = world.worker(args.get("worker_id", ""))
        if shift is None or worker is None:
            return None
        site = world.site(shift.site_id)
        if site is None:
            return None

        try:
            rules = for_code(site.jurisdiction_code, on=world.now().date())
        except (KeyError, LookupError):
            return None

        week_start = shift.starts_at - timedelta(days=shift.starts_at.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        schedule = world.schedule(site.site_id, week_start)
        if schedule is None or schedule.posted_at is None:
            return None

        option = next(
            (o for o in enumerate_cover_options(world, shift, at=world.now())
             if o.worker_id == worker.worker_id),
            None,
        )
        rest_gap = option.rest_gap_hours if option else None
        claims = option.claims if option else ()

        breakdown = price_change(
            rules=rules, kind=ChangeKind.ADD_SHIFT,
            posted_at=schedule.posted_at, changed_at=world.now(),
            schedule_starts_at=week_start, hourly_rate=worker.hourly_rate,
            hours_lost=0.0, hours_worked=shift.hours,
            hours_before_this_week=schedule.hours_for(worker.worker_id),
            rest_gap_hours=rest_gap, worker_id=worker.worker_id,
            shift_id=shift.shift_id, claims=claims, evidence=world,
        )

        # Both minimums used to be answered without looking: the role one was a
        # literal True, and the certification one asked whether the site employed
        # a certified person *anywhere*, which is true of every site here. So the
        # rule the Autonomy screen advertises could never fire. Ask the floor.
        role_ok, cert_ok = meets_minimums(
            site, schedule, shift, worker,
            {w.worker_id: w for w in world.workers(site.site_id)},
        )

        week_spend = Money(cents=sum(
            int(e.get("total_cents", 0)) for e in ledger
            if e.get("kind") in ("assign_cover", "cancel_shift")
            and e.get("site_id") == site.site_id
        ))
        hours_after = schedule.hours_for(worker.worker_id) + shift.hours
        shortfall = max(0.0, (worker.good_faith_hours - hours_after) / worker.good_faith_hours) \
            if worker.good_faith_hours else 0.0

        return CoverContext(
            cost=breakdown.total,
            week_spend=week_spend,
            overtime_hours=max(0.0, hours_after - 40.0),
            shortfall_fraction=shortfall,
            # A waiver that the worker has already granted is not an outstanding
            # waiver. Reading `requires_consent` alone meant a cover the worker
            # had agreed to in writing was still refused for wanting the
            # agreement it already had.
            requires_rest_waiver=(
                breakdown.requires_consent
                and not consent.has_granted(worker.worker_id, shift.shift_id)
            ),
            worker_declined=world.has_declined(worker.worker_id, shift.shift_id)
            or consent.has_declined(worker.worker_id, shift.shift_id),
            meets_role_minimum=role_ok,
            meets_certification_minimum=cert_ok,
            assessable=breakdown.lawful,
        )

    return provide
