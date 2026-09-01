from datetime import datetime, timedelta, timezone

from muster.adapters.simulated import SableCoffee
from muster.domain.options import enumerate_cover_options
from muster.domain.types import ChangeKind

TZ = timezone.utc


def _gap(world, site_id="site-or"):
    """The Monday 07:00 open at a site, with its worker removed."""
    schedule = world.schedule(site_id, datetime(2026, 7, 27, tzinfo=TZ))
    return next(s for s in schedule.shifts if s.starts_at.hour == 7)


def test_it_offers_every_free_colleague_at_the_site():
    world = SableCoffee()
    options = enumerate_cover_options(world, _gap(world), at=world.now())
    assert len(options) >= 3
    assert all(o.shift_id == _gap(world).shift_id for o in options)


def test_a_worker_who_already_declined_this_shift_is_not_offered_again():
    world = SableCoffee()
    gap = _gap(world)
    first = enumerate_cover_options(world, gap, at=world.now())
    declined = first[0].worker_id
    world.record_decline(declined, gap.shift_id)
    again = enumerate_cover_options(world, gap, at=world.now())
    assert declined not in {o.worker_id for o in again}


def test_an_unavailable_worker_is_not_offered():
    world = SableCoffee()
    gap = _gap(world)
    options = enumerate_cover_options(world, gap, at=world.now())
    for option in options:
        worker = world.worker(option.worker_id)
        assert worker.is_available(gap.starts_at, gap.ends_at)


def test_an_option_that_breaches_rest_is_still_returned_and_carries_the_gap():
    """It is expensive and needs consent. Hiding it hides a lawful choice."""
    world = SableCoffee()
    gap = _gap(world)
    options = enumerate_cover_options(world, gap, at=world.now())
    breaching = [o for o in options if o.rest_gap_hours is not None and o.rest_gap_hours < 10]
    assert breaching, "the seeded week must contain at least one closer who could open"


def test_standby_members_carry_a_standby_claim_in_oregon_only():
    from muster.domain.types import CarveOut
    world = SableCoffee()
    or_options = enumerate_cover_options(world, _gap(world, "site-or"), at=world.now())
    chi_options = enumerate_cover_options(world, _gap(world, "site-chi"), at=world.now())
    or_claims = {c.kind for o in or_options for c in o.claims}
    chi_claims = {c.kind for o in chi_options for c in o.claims}
    assert CarveOut.STANDBY_LIST in or_claims
    assert CarveOut.STANDBY_LIST not in chi_claims


def test_every_option_is_an_add_shift_change():
    world = SableCoffee()
    options = enumerate_cover_options(world, _gap(world), at=world.now())
    assert all(o.kind is ChangeKind.ADD_SHIFT for o in options)


def test_a_site_with_nobody_free_returns_an_empty_list_not_an_error():
    world = SableCoffee()
    gap = _gap(world)
    for worker in world.workers(gap.site_id):
        world.record_decline(worker.worker_id, gap.shift_id)
    assert enumerate_cover_options(world, gap, at=world.now()) == []
