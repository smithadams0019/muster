"""Six scenarios an operator would recognise, in their own words.

Every test here drives the real pricing path over `SableCoffee`, the seeded
three-site demo world — real workers, real rates, real rulebooks, real evidence
registries. Nothing is stubbed. A scenario that is only true against a fake is not
an argument about what Muster actually does when it runs; this file is where the
safety argument gets rechecked against the same rulebook and the same world the
product ships with.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from muster.adapters.simulated import SableCoffee
from muster.domain.carve_outs import CarveOutClaim, carve_out_applies
from muster.domain.models import CoverOption, Shift
from muster.domain.options import enumerate_cover_options
from muster.domain.pricing import CostBreakdown, price_change
from muster.domain.types import AutonomyLevel, CarveOut, ChangeKind, Money
from muster.policy.rules import CoverContext, evaluate
from muster.rulebook.loader import for_code

TZ = timezone.utc
WEEK_START = datetime(2026, 7, 27, tzinfo=TZ)  # Monday, first day of the posted schedule


def _price_option(world: SableCoffee, schedule, rules, shift: Shift, option: CoverOption,
                   *, claims=None) -> CostBreakdown:
    """Price one real cover option the way an operator would see it costed."""
    worker = world.worker(option.worker_id)
    return price_change(
        rules=rules,
        kind=ChangeKind.ADD_SHIFT,
        posted_at=schedule.posted_at,
        changed_at=world.now(),
        schedule_starts_at=WEEK_START,
        hourly_rate=worker.hourly_rate,
        hours_lost=0.0,
        hours_worked=shift.hours,
        hours_before_this_week=schedule.hours_for(worker.worker_id),
        rest_gap_hours=option.rest_gap_hours,
        worker_id=worker.worker_id,
        shift_id=shift.shift_id,
        claims=option.claims if claims is None else claims,
        evidence=world,
    )


def test_the_standby_list_is_empty_at_6am_and_every_remaining_cover_costs_money():
    """Oregon's standby list is the one carve-out that costs nothing — until nobody left on it will take it."""
    world = SableCoffee()
    assert world.now().hour == 6, "the seeded world's clock is frozen at 6am for exactly this scenario"

    schedule = world.schedule("site-or", WEEK_START)
    rules = for_code("us-or", on=world.now().date())
    gap = next(s for s in schedule.shifts if s.shift_id == "s-or-20260727-open")

    # Both Oregon workers on the standby list decline this shift. The list, for
    # this gap, is empty.
    standby = [w for w in world.workers("site-or") if w.on_standby_list]
    assert standby, "the Oregon roster must carry the standby carve-out somewhere"
    for worker in standby:
        world.record_decline(worker.worker_id, gap.shift_id)

    options = enumerate_cover_options(world, gap, at=world.now())
    assert options, "the seeded roster must still have someone free to offer"
    assert all(not option.claims for option in options), (
        "nobody left carries the standby carve-out — it left with the two workers who declined"
    )

    for option in options:
        result = _price_option(world, schedule, rules, gap, option)
        assert result.total.cents > 0, (option.worker_id, result)


def test_the_same_sick_call_in_portland_chicago_and_new_york_costs_three_different_amounts():
    """Same worker index, same notice, same frozen clock — the ordinance is the only thing that varies."""
    world = SableCoffee()
    totals: dict[str, Money] = {}
    rates: dict[str, Money] = {}

    for site_id, code in (
        ("site-or", "us-or"),
        ("site-chi", "us-il-chicago"),
        ("site-nyc", "us-ny-nyc-fastfood"),
    ):
        suffix = site_id.removeprefix("site-")
        schedule = world.schedule(site_id, WEEK_START)
        rules = for_code(code, on=world.now().date())
        gap = next(s for s in schedule.shifts if s.shift_id == f"s-{suffix}-20260727-open")
        cover = world.worker(f"w-{suffix}-4")  # the certified barista, free that morning at every site

        result = price_change(
            rules=rules, kind=ChangeKind.ADD_SHIFT,
            posted_at=schedule.posted_at, changed_at=world.now(), schedule_starts_at=WEEK_START,
            hourly_rate=cover.hourly_rate, hours_lost=0.0, hours_worked=gap.hours,
            hours_before_this_week=schedule.hours_for(cover.worker_id), rest_gap_hours=None,
            worker_id=cover.worker_id, shift_id=gap.shift_id, claims=(), evidence=world,
        )
        premium = next(
            (line.amount for line in result.lines if "schedule change premium" in line.clause),
            Money.zero(),
        )
        totals[site_id] = premium
        rates[site_id] = cover.hourly_rate

    assert len(set(totals.values())) == 3, totals
    assert totals["site-or"] == rates["site-or"], "Oregon owes one hour at the worker's own rate"
    assert totals["site-chi"] == rates["site-chi"], "Chicago owes one hour at the worker's own rate"
    assert totals["site-nyc"] == Money.from_dollars("45.00"), (
        "NYC fast food prices this band as a flat $45 tier, not hours at the worker's own rate"
    )


def test_an_agent_claims_the_swap_was_employee_requested_but_no_request_exists():
    """The claim is free to make. It is also free to be wrong about — the price does not move."""
    world = SableCoffee()
    schedule = world.schedule("site-or", WEEK_START)
    rules = for_code("us-or", on=world.now().date())
    gap = next(s for s in schedule.shifts if s.shift_id == "s-or-20260727-open")
    worker = world.worker("w-or-4")

    # No world.record_worker_request(...) call — the world holds no such evidence.
    claimed = price_change(
        rules=rules, kind=ChangeKind.ADD_SHIFT, posted_at=schedule.posted_at,
        changed_at=world.now(), schedule_starts_at=WEEK_START, hourly_rate=worker.hourly_rate,
        hours_lost=0.0, hours_worked=gap.hours, hours_before_this_week=schedule.hours_for(worker.worker_id),
        rest_gap_hours=None, worker_id=worker.worker_id, shift_id=gap.shift_id,
        claims=(CarveOutClaim(CarveOut.WORKER_REQUESTED),), evidence=world,
    )

    unclaimed = price_change(
        rules=rules, kind=ChangeKind.ADD_SHIFT, posted_at=schedule.posted_at,
        changed_at=world.now(), schedule_starts_at=WEEK_START, hourly_rate=worker.hourly_rate,
        hours_lost=0.0, hours_worked=gap.hours, hours_before_this_week=schedule.hours_for(worker.worker_id),
        rest_gap_hours=None, worker_id=worker.worker_id, shift_id=gap.shift_id,
        claims=(), evidence=world,
    )

    assert claimed.carve_outs_applied == ()
    assert claimed.total == unclaimed.total, (
        "an unevidenced claim must move the price by exactly nothing"
    )
    assert claimed.total.cents > 0, "and the premium is genuinely owed, not zero for another reason"


def test_an_agent_claims_the_standby_carve_out_in_chicago_where_it_does_not_exist():
    """Chicago's rulebook never lists standby_list among its carve-outs, so the claim is refused before the
    world is even asked whether the worker is on one."""
    world = SableCoffee()
    schedule = world.schedule("site-chi", WEEK_START)
    rules = for_code("us-il-chicago", on=world.now().date())
    gap = next(s for s in schedule.shifts if s.shift_id == "s-chi-20260727-open")
    worker = world.worker("w-chi-4")
    claim = CarveOutClaim(CarveOut.STANDBY_LIST)

    assert CarveOut.STANDBY_LIST not in rules.carve_outs
    assert carve_out_applies(
        claim, rules=rules, worker_id=worker.worker_id, shift_id=gap.shift_id, evidence=world,
    ) is False

    result = price_change(
        rules=rules, kind=ChangeKind.ADD_SHIFT, posted_at=schedule.posted_at,
        changed_at=world.now(), schedule_starts_at=WEEK_START, hourly_rate=worker.hourly_rate,
        hours_lost=0.0, hours_worked=gap.hours, hours_before_this_week=schedule.hours_for(worker.worker_id),
        rest_gap_hours=None, worker_id=worker.worker_id, shift_id=gap.shift_id,
        claims=(claim,), evidence=world,
    )
    unclaimed = price_change(
        rules=rules, kind=ChangeKind.ADD_SHIFT, posted_at=schedule.posted_at,
        changed_at=world.now(), schedule_starts_at=WEEK_START, hourly_rate=worker.hourly_rate,
        hours_lost=0.0, hours_worked=gap.hours, hours_before_this_week=schedule.hours_for(worker.worker_id),
        rest_gap_hours=None, worker_id=worker.worker_id, shift_id=gap.shift_id,
        claims=(), evidence=world,
    )
    assert result.carve_outs_applied == ()
    assert result.total == unclaimed.total, "a carve-out this city does not offer changes nothing"
    assert result.total.cents > 0


def test_covering_the_shift_would_leave_nobody_food_safety_certified_on_the_floor():
    """As posted, Thursday's close at Sable Wicker is worked by a certified barista. Once the lead has gone
    home at 16:00, that closer is the only certified handler left on the floor until closing."""
    world = SableCoffee()
    schedule = world.schedule("site-chi", WEEK_START)
    gap = next(s for s in schedule.shifts if s.shift_id == "s-chi-20260730-close")
    assert world.worker(gap.worker_id).is_certified("food_handler")

    def certified_on_duty(shifts: list[Shift], moment: datetime) -> bool:
        return any(
            s.starts_at <= moment < s.ends_at and world.worker(s.worker_id).is_certified("food_handler")
            for s in shifts
        )

    just_before_close = gap.ends_at - timedelta(minutes=1)
    assert certified_on_duty(schedule.shifts, just_before_close), (
        "as posted, the certified closer is still on the floor right up to close"
    )

    options = enumerate_cover_options(world, gap, at=world.now())
    cover = next(o for o in options if o.worker_id == "w-chi-7")
    assert not world.worker(cover.worker_id).is_certified("food_handler")

    covered_shifts = [
        s if s.shift_id != gap.shift_id else replace(s, worker_id=cover.worker_id)
        for s in schedule.shifts
    ]
    meets_certification_minimum = certified_on_duty(covered_shifts, just_before_close)
    assert meets_certification_minimum is False, (
        "swapping in an uncertified closer empties the floor of food-safety certification before close"
    )

    rules = for_code("us-il-chicago", on=world.now().date())
    priced = _price_option(world, schedule, rules, gap, cover)
    ctx = CoverContext(
        cost=priced.total, week_spend=Money.zero(), overtime_hours=0.0, shortfall_fraction=0.0,
        requires_rest_waiver=False, worker_declined=False, meets_role_minimum=True,
        meets_certification_minimum=meets_certification_minimum, assessable=True,
    )
    hits = evaluate(ctx, AutonomyLevel.TRUSTED)
    assert "understaffed_below_minimum" in {h.rule for h in hits}, (
        "even at the most permissive setting, an empty floor is not something the dial can absorb"
    )


def test_the_cheapest_cover_is_a_clopening_and_it_is_the_only_one():
    """Every other candidate for Thursday's close declines. What is left is a closer who opened the same
    morning — a clopening, and the only cover option there is. Chicago's Right to Rest has no exceptions,
    so being the only option on offer does not make it a free one."""
    world = SableCoffee()
    schedule = world.schedule("site-chi", WEEK_START)
    rules = for_code("us-il-chicago", on=world.now().date())
    gap = next(s for s in schedule.shifts if s.shift_id == "s-chi-20260730-close")

    # Find the person who would actually be clopening rather than naming one:
    # a reseed moves who opened that morning, and a hard-coded id would quietly
    # turn this into a test of some other worker's ordinary shift.
    candidates = enumerate_cover_options(world, gap, at=world.now())
    clopener = next(
        (o for o in candidates
         if o.rest_gap_hours is not None and o.rest_gap_hours < rules.rest_hours),
        None,
    )
    assert clopener is not None, "the seeded week must contain someone who would clopen this close"

    for option in candidates:
        if option.worker_id != clopener.worker_id:
            world.record_decline(option.worker_id, gap.shift_id)

    only = enumerate_cover_options(world, gap, at=world.now())
    assert [o.worker_id for o in only] == [clopener.worker_id]
    assert only[0].rest_gap_hours is not None and only[0].rest_gap_hours < rules.rest_hours

    result = _price_option(world, schedule, rules, gap, only[0])
    assert result.lawful is True, "Chicago does not forbid this cover, it just will not waive rest alone"
    assert result.requires_consent is True

    # A claim that the worker asked for this — evidenced or not — still cannot buy back the consent step.
    world.record_worker_request(clopener.worker_id, gap.shift_id)
    claim = CarveOutClaim(CarveOut.WORKER_REQUESTED)
    assert carve_out_applies(
        claim, rules=rules, worker_id=clopener.worker_id, shift_id=gap.shift_id,
        evidence=world, against_rest=True,
    ) is False, "no carve-out ever reaches a rest rule in a jurisdiction with rest_has_carve_outs=False"
