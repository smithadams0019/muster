# tests/adapters/test_simulated.py
from datetime import datetime, timedelta, timezone

from muster.adapters.simulated import SableCoffee
from muster.domain.types import CarveOut, Role

TZ = timezone.utc


def test_three_sites_one_per_jurisdiction():
    world = SableCoffee()
    codes = {s.jurisdiction_code for s in world.sites()}
    assert codes == {"us-or", "us-il-chicago", "us-ny-nyc-fastfood"}


def test_the_clock_is_frozen_so_notice_bands_are_reproducible():
    assert SableCoffee().now() == datetime(2026, 7, 24, 6, 0, tzinfo=TZ)


def test_the_same_seed_produces_the_same_roster_twice():
    a = [w.worker_id for w in SableCoffee(seed=7).workers()]
    b = [w.worker_id for w in SableCoffee(seed=7).workers()]
    assert a == b and len(a) == 36


def test_every_site_has_at_least_one_shift_lead_and_one_certified_handler():
    world = SableCoffee()
    for site in world.sites():
        staff = world.workers(site.site_id)
        assert any(w.role is Role.SHIFT_LEAD for w in staff)
        assert any(w.is_certified("food_handler") for w in staff)


def test_only_the_oregon_site_has_workers_on_a_standby_list():
    """The standby carve-out exists in Oregon and nowhere else Muster ships."""
    world = SableCoffee()
    by_site = {s.site_id: s.jurisdiction_code for s in world.sites()}
    for worker in world.workers():
        if worker.on_standby_list:
            assert by_site[worker.site_id] == "us-or"


def test_a_decline_is_remembered_and_visible_to_the_policy():
    world = SableCoffee()
    assert world.has_declined("w-or-1", "s-1") is False
    world.record_decline("w-or-1", "s-1")
    assert world.has_declined("w-or-1", "s-1") is True


def test_standby_acceptance_is_evidence_only_after_it_is_recorded():
    world = SableCoffee()
    assert world.standby_accepted("w-or-1", "s-1") is False
    world.record_standby_acceptance("w-or-1", "s-1")
    assert world.standby_accepted("w-or-1", "s-1") is True


def test_a_declared_incident_is_readable_by_kind():
    world = SableCoffee()
    world.declare_incident("inc-1", CarveOut.UTILITY_FAILURE)
    assert world.declared_incident("inc-1") is CarveOut.UTILITY_FAILURE
    assert world.declared_incident("inc-2") is None


def test_demand_returns_an_hourly_curve_for_a_day():
    world = SableCoffee()
    curve = world.demand("site-or", datetime(2026, 7, 27, tzinfo=TZ))
    assert set(curve) <= set(range(24))
    assert all(count >= 0 for count in curve.values())
