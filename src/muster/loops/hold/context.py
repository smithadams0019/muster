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
from muster.domain.types import AutonomyLevel, ChangeKind, Money
from muster.persistence.consent import ConsentStore
from muster.policy.escalation import GUARDED_TOOLS
from muster.policy.rules import CoverContext
from muster.rulebook.loader import for_code


#: Guarded because they reach a person, but they create no new money. The cost
#: was approved when the cover was assigned; charging it again at notification
#: time would ask the operator to approve one decision twice.
_CREATES_NO_LIABILITY = frozenset({"notify_worker"})


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
            requires_rest_waiver=breakdown.requires_consent,
            worker_declined=world.has_declined(worker.worker_id, shift.shift_id)
            or consent.has_declined(worker.worker_id, shift.shift_id),
            meets_role_minimum=True,
            meets_certification_minimum=(
                site.certified_handler_minimum == 0 or worker.is_certified("food_handler")
                or any(w.is_certified("food_handler") for w in world.workers(site.site_id)
                       if w.worker_id != shift.worker_id)
            ),
            assessable=breakdown.lawful,
        )

    return provide
