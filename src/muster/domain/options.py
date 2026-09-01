"""Every lawful way to cover a gap.

Enumerates; does not judge. Options that cost money or need someone's consent come
back with the rest, because the escalation this feeds exists precisely to put those
choices in front of a person. A cheaper enumeration that quietly dropped the
expensive options would leave the operator choosing from a menu they cannot see.

Two exclusions only, and both are about the worker rather than the money: someone
unavailable in that window, and someone who has already said no to this shift.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from muster.adapters.base import WorldAdapter
from muster.domain.carve_outs import CarveOutClaim
from muster.domain.models import CoverOption, Shift
from muster.domain.rest import rest_gap_hours
from muster.domain.types import CarveOut, ChangeKind
from muster.rulebook.loader import for_code


def enumerate_cover_options(
    world: WorldAdapter, gap: Shift, at: datetime
) -> list[CoverOption]:
    """Everyone at the site who could lawfully take this shift."""
    site = world.site(gap.site_id)
    if site is None:
        raise LookupError(f"unknown site {gap.site_id!r}")
    rules = for_code(site.jurisdiction_code, on=at.date())
    schedule = world.schedule(gap.site_id, _week_start(gap.starts_at))

    options: list[CoverOption] = []
    for worker in world.workers(gap.site_id):
        if worker.worker_id == gap.worker_id:
            continue
        if not worker.is_available(gap.starts_at, gap.ends_at):
            continue
        if world.has_declined(worker.worker_id, gap.shift_id):
            continue

        previous = schedule.last_shift_ending_before(worker.worker_id, gap.starts_at) \
            if schedule else None
        gap_hours = rest_gap_hours(previous.ends_at, gap.starts_at) if previous else None

        claims: tuple[CarveOutClaim, ...] = ()
        if worker.on_standby_list and CarveOut.STANDBY_LIST in rules.carve_outs:
            claims = (CarveOutClaim(CarveOut.STANDBY_LIST),)

        options.append(CoverOption(
            option_id=f"opt-{gap.shift_id}-{worker.worker_id}",
            kind=ChangeKind.ADD_SHIFT,
            worker_id=worker.worker_id,
            shift_id=gap.shift_id,
            hours=gap.hours,
            rest_gap_hours=gap_hours,
            claims=claims,
            note="on the standby list" if claims else "",
        ))
    return options


def _week_start(moment: datetime) -> datetime:
    monday = moment - timedelta(days=moment.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)
