"""The demo world must not itself be the thing the product exists to prevent.

An earlier seed put one shift lead on all seven days - fifty-six hours without a
day off - and staffed three shifts a day against a demand curve that peaked at
nine, so the console's headline chart showed a shop permanently understaffed. A
demo of a compliance product cannot open on a compliance failure.
"""

from __future__ import annotations

from datetime import timedelta

from muster.adapters.simulated import _MAX_DAYS, _MAX_WEEKLY_HOURS, _WEEK_START, SableCoffee


def _in_week(schedule):
    return [s for s in schedule.shifts if s.starts_at >= _WEEK_START and s.worker_id]


def test_nobody_works_more_than_the_seeded_ceilings():
    world = SableCoffee()
    for site in world.sites():
        hours: dict[str, float] = {}
        days: dict[str, set] = {}
        for shift in _in_week(world.schedule(site.site_id, _WEEK_START)):
            hours[shift.worker_id] = hours.get(shift.worker_id, 0.0) + shift.hours
            days.setdefault(shift.worker_id, set()).add(shift.starts_at.date())

        for worker_id, worked in hours.items():
            assert worked <= _MAX_WEEKLY_HOURS, f"{worker_id} works {worked}h"
            assert len(days[worker_id]) <= _MAX_DAYS, f"{worker_id} works {len(days[worker_id])} days"


def test_nobody_is_rostered_on_two_shifts_at_once():
    world = SableCoffee()
    for site in world.sites():
        by_worker: dict[str, list] = {}
        for shift in _in_week(world.schedule(site.site_id, _WEEK_START)):
            by_worker.setdefault(shift.worker_id, []).append(shift)
        for worker_id, shifts in by_worker.items():
            shifts.sort(key=lambda s: s.starts_at)
            for a, b in zip(shifts, shifts[1:]):
                assert a.ends_at <= b.starts_at, f"{worker_id} is in two places at once"


def test_nobody_is_rostered_while_on_leave():
    world = SableCoffee()
    for site in world.sites():
        for shift in _in_week(world.schedule(site.site_id, _WEEK_START)):
            worker = world.worker(shift.worker_id)
            assert worker.is_available(shift.starts_at, shift.ends_at), (
                f"{worker.name} is rostered on {shift.shift_id} while on leave"
            )


def test_the_posted_week_meets_its_own_demand_curve_at_two_of_three_sites():
    """Bleecker Street is short on the Saturday, and that is the point: five of
    its fourteen are on leave, which is what leaves one block open and makes
    every cover for that afternoon a sixteen-hour day. The other two sites staff
    their curve exactly, so the console's headline chart is not a picture of a
    shop that cannot cover any day of its week."""
    world = SableCoffee()
    short_by_site: dict[str, int] = {}
    for site in world.sites():
        schedule = world.schedule(site.site_id, _WEEK_START)
        short = 0
        for offset in range(7):
            day = _WEEK_START + timedelta(days=offset)
            demand = world.demand(site.site_id, day)
            covered: dict[int, int] = {}
            for shift in _in_week(schedule):
                if shift.starts_at.date() != day.date():
                    continue
                for hour in range(shift.starts_at.hour, shift.ends_at.hour):
                    covered[hour] = covered.get(hour, 0) + 1
            short += sum(1 for hour, need in demand.items() if covered.get(hour, 0) < need)
        short_by_site[site.site_id] = short

    assert short_by_site["site-or"] == 0, short_by_site
    assert short_by_site["site-chi"] == 0, short_by_site
    assert short_by_site["site-nyc"] <= 4, short_by_site


def test_exactly_one_deliberate_rest_breach_bridges_into_the_week():
    """The Sunday-before close into Monday's open, and nothing else."""
    world = SableCoffee()
    for site in world.sites():
        schedule = world.schedule(site.site_id, _WEEK_START)
        rest = {"us-or": 10.0, "us-il-chicago": 10.0, "us-ny-nyc-fastfood": 11.0}[
            site.jurisdiction_code
        ]
        by_worker: dict[str, list] = {}
        for shift in schedule.shifts:
            if shift.worker_id:
                by_worker.setdefault(shift.worker_id, []).append(shift)

        breaches = []
        for shifts in by_worker.values():
            shifts.sort(key=lambda s: s.starts_at)
            for a, b in zip(shifts, shifts[1:]):
                gap = (b.starts_at - a.ends_at).total_seconds() / 3600
                if gap < rest:
                    breaches.append((a.shift_id, b.shift_id))
        assert len(breaches) == 1, breaches
        assert "bridge" in breaches[0][0]
