"""The floor minimums, which used to be answered without being asked."""

from __future__ import annotations

from dataclasses import replace

from muster.adapters.simulated import SableCoffee, _WEEK_START
from muster.domain.staffing import meets_minimums


def _site_bits(world: SableCoffee, site_id: str):
    return (
        world.site(site_id),
        world.schedule(site_id, _WEEK_START),
        {w.worker_id: w for w in world.workers(site_id)},
    )


def test_an_uncertified_cover_for_the_last_certified_person_on_the_floor_is_a_breach():
    world = SableCoffee()
    site, schedule, workers = _site_bits(world, "site-chi")
    gap = max((s for s in schedule.shifts if s.worker_id), key=lambda s: s.ends_at)
    assert workers[gap.worker_id].is_certified("food_handler"), (
        "the seeded week must close with a certified handler for this to be the question"
    )

    uncertified = next(w for w in workers.values() if not w.is_certified("food_handler"))
    _, cert_ok = meets_minimums(site, schedule, gap, uncertified, workers)
    assert cert_ok is False


def test_a_certified_cover_for_the_same_shift_is_not():
    world = SableCoffee()
    site, schedule, workers = _site_bits(world, "site-chi")
    gap = max((s for s in schedule.shifts if s.worker_id), key=lambda s: s.ends_at)

    certified = next(
        w for w in workers.values()
        if w.is_certified("food_handler") and w.worker_id != gap.worker_id
    )
    _, cert_ok = meets_minimums(site, schedule, gap, certified, workers)
    assert cert_ok is True


def test_a_cover_is_not_blamed_for_a_shortfall_the_posted_week_already_had():
    """Judged against the minimum in the abstract rather than against the posted
    week, a shift that is already the only body on the floor would refuse every
    cover including the person rostered on it. That is a deadlock, not a rule."""
    world = SableCoffee()
    site, schedule, workers = _site_bits(world, "site-nyc")
    gap = max((s for s in schedule.shifts if s.worker_id), key=lambda s: s.ends_at)

    incumbent = workers[gap.worker_id]
    role_ok, cert_ok = meets_minimums(site, schedule, gap, incumbent, workers)
    assert (role_ok, cert_ok) == (True, True), (
        "the worker already on the shift can always be 'covered' by themselves"
    )


def test_the_check_walks_hours_not_shifts():
    """A cover that is fine for the first hour and short for the last is short."""
    world = SableCoffee()
    site, schedule, workers = _site_bits(world, "site-or")
    gap = max((s for s in schedule.shifts if s.worker_id), key=lambda s: s.ends_at)

    # Strip certification from everyone else on the floor during the tail of the
    # gap, so only the gap's own worker can satisfy the minimum.
    stripped = {
        wid: replace(w, certifications=frozenset()) if wid != gap.worker_id else w
        for wid, w in workers.items()
    }
    uncertified = next(w for w in stripped.values() if not w.is_certified("food_handler"))
    _, cert_ok = meets_minimums(site, schedule, gap, uncertified, stripped)
    assert cert_ok is False
