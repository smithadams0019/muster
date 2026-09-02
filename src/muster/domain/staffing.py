"""Whether the floor still holds up once a cover is swapped in.

Two site minimums matter to the policy: how many of each role must be on, and how
many food-safety certified people must be on. Both were previously answered `True`
at the point of judgement - `meets_role_minimum=True` was a literal, and the
certification test asked only whether the site employed a certified person
anywhere, which is true of every site in every world. So `understaffed_below_minimum`,
a rule the Autonomy screen lists among the eight that can stop the agent, could not
actually fire.

Two things this is careful about.

It walks the hours rather than the shifts, because that is how being short actually
happens: the lead goes home at four, the close runs to ten, and the minimum is
broken for the six hours in between while every individual shift looks fine.

And it compares the floor *with* the cover against the floor as posted, rather than
against the minimum in the abstract. A cover is answerable for a shortfall it
creates, not for one it inherited. Judged absolutely, a shift that was already the
only body on the floor at closing time would refuse every possible cover including
the person who was rostered on it, which is not a safety rule - it is a deadlock.
"""

from __future__ import annotations

from datetime import timedelta

from muster.domain.models import Schedule, Shift, Site, Worker


def _short_hours(
    site: Site,
    schedule: Schedule,
    gap: Shift,
    worker_id: str | None,
    workers: dict[str, Worker],
) -> tuple[int, int]:
    """Hours of the gap that fall below the role and certification minimums."""
    role_short = 0
    cert_short = 0

    moment = gap.starts_at
    while moment < gap.ends_at:
        on: list[Worker] = []
        for shift in schedule.shifts:
            if not (shift.starts_at <= moment < shift.ends_at):
                continue
            who = worker_id if shift.shift_id == gap.shift_id else shift.worker_id
            worker = workers.get(who) if who else None
            if worker is not None:
                on.append(worker)

        if any(
            sum(1 for w in on if w.role is role) < minimum
            for role, minimum in site.role_minimums.items()
        ):
            role_short += 1
        if sum(1 for w in on if w.is_certified("food_handler")) < site.certified_handler_minimum:
            cert_short += 1

        moment += timedelta(hours=1)

    return role_short, cert_short


def meets_minimums(
    site: Site,
    schedule: Schedule,
    gap: Shift,
    cover: Worker,
    workers: dict[str, Worker],
) -> tuple[bool, bool]:
    """`(meets_role_minimum, meets_certification_minimum)` if `cover` takes `gap`.

    Each is True when the cover leaves the floor no worse than the posted week
    already had it.
    """
    as_posted = _short_hours(site, schedule, gap, gap.worker_id, workers)
    with_cover = _short_hours(site, schedule, gap, cover.worker_id, workers)
    return with_cover[0] <= as_posted[0], with_cover[1] <= as_posted[1]
