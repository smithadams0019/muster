"""A cover option must not put one person in two places at once."""

from __future__ import annotations

from muster.adapters.simulated import SableCoffee, _WEEK_START
from muster.domain.options import enumerate_cover_options


def _overlaps(a, b) -> bool:
    return a.starts_at < b.ends_at and b.starts_at < a.ends_at


def test_nobody_already_rostered_on_an_overlapping_shift_is_offered_as_cover():
    world = SableCoffee()
    for site in world.sites():
        schedule = world.schedule(site.site_id, _WEEK_START)
        for gap in schedule.shifts:
            if gap.worker_id is None:
                continue
            offered = {o.worker_id for o in enumerate_cover_options(world, gap, at=world.now())}
            busy = {
                s.worker_id for s in schedule.shifts
                if s.worker_id is not None and s.shift_id != gap.shift_id and _overlaps(s, gap)
            }
            assert not (offered & busy), (
                f"{sorted(offered & busy)} are already working during {gap.shift_id}"
            )


def test_someone_free_at_that_hour_is_still_offered():
    """The exclusion must not be so broad that it empties the list."""
    world = SableCoffee()
    schedule = world.schedule("site-or", _WEEK_START)
    gap = next(s for s in schedule.shifts if s.worker_id is not None)
    assert enumerate_cover_options(world, gap, at=world.now())


def test_a_worker_on_leave_that_day_is_not_offered():
    world = SableCoffee()
    schedule = world.schedule("site-nyc", _WEEK_START)
    on_leave = [w for w in world.workers("site-nyc") if w.unavailable]
    assert on_leave, "the seeded roster must carry some time off"

    for worker in on_leave:
        window = worker.unavailable[0]
        during = [
            s for s in schedule.shifts
            if s.starts_at >= window.starts_at and s.ends_at <= window.ends_at
            and s.worker_id != worker.worker_id
        ]
        for gap in during:
            offered = {o.worker_id for o in enumerate_cover_options(world, gap, at=world.now())}
            assert worker.worker_id not in offered
