"""The rest-period rule, at the two places it is decided.

Asking is not waiving. Using someone's answer is. The policy has to tell them
apart or the product either loops forever or waives a rest period on someone's
behalf, and only one of those is merely annoying.
"""

from __future__ import annotations

from datetime import timedelta

from muster.adapters.simulated import SableCoffee, _WEEK_START
from muster.domain.options import enumerate_cover_options
from muster.domain.types import AutonomyLevel, ConsentKind, ConsentOutcome, Money
from muster.loops.hold.context import build_hold_context_provider
from muster.persistence.consent import ConsentStore
from muster.policy.rules import evaluate

#: The Saturday afternoon at Bleecker Street, where every lawful cover is a
#: sixteen-hour day. Found rather than named, so a reseed cannot make this file
#: quietly assert about some ordinary shift.
def _consent_forced_gap(world: SableCoffee):
    schedule = world.schedule("site-nyc", _WEEK_START)
    rules_rest = 11.0
    for shift in schedule.shifts:
        if shift.worker_id is None:
            continue
        options = enumerate_cover_options(world, shift, at=world.now())
        if options and all(
            o.rest_gap_hours is not None and o.rest_gap_hours < rules_rest for o in options
        ):
            return schedule, shift, options
    raise AssertionError("the seeded world must contain one gap every cover needs consent for")


def _provider(world, consent, level=AutonomyLevel.BALANCED):
    return build_hold_context_provider(world, [], consent, level)


def test_asking_for_consent_is_never_held_for_the_operator():
    """Asking is the lawful route to a cover that needs a waiver, not the waiver.
    Priced as though it were the cover, the ask tripped a rule no autonomy level
    can clear, so approving the ask produced an identical copy of itself."""
    world = SableCoffee()
    consent = ConsentStore()
    _, gap, options = _consent_forced_gap(world)

    context = _provider(world, consent)(
        "request_consent",
        {"worker_id": options[0].worker_id, "shift_id": gap.shift_id, "kind": "rest_waiver"},
    )
    assert evaluate(context, AutonomyLevel.CONSERVATIVE) == []


def test_assigning_that_same_cover_is_held_because_the_waiver_is_outstanding():
    world = SableCoffee()
    consent = ConsentStore()
    _, gap, options = _consent_forced_gap(world)

    context = _provider(world, consent)(
        "assign_cover",
        {"worker_id": options[0].worker_id, "shift_id": gap.shift_id, "option_id": "x"},
    )
    assert "rest_waiver_required" in {h.rule for h in evaluate(context, AutonomyLevel.TRUSTED)}, (
        "no autonomy level may waive someone's rest period for them"
    )


def test_once_the_worker_has_granted_it_the_waiver_is_no_longer_outstanding():
    """What satisfies a rest-period waiver is the worker's own agreement. Reading
    'this cover needs consent' without asking whether consent was given refused a
    cover for wanting the agreement it already had."""
    world = SableCoffee()
    consent = ConsentStore()
    _, gap, options = _consent_forced_gap(world)
    worker_id = options[0].worker_id

    request = consent.ask(
        worker_id=worker_id, shift_id=gap.shift_id, kind=ConsentKind.REST_WAIVER,
        premium_owed=Money.from_dollars("145.00"), what_it_means="Cover this.",
        asked_at=world.now(), expires_in=timedelta(hours=4),
    )
    consent.answer(request.request_id, ConsentOutcome.GRANTED,
                   answered_at=world.now(), channel="console")

    context = _provider(world, consent)(
        "assign_cover", {"worker_id": worker_id, "shift_id": gap.shift_id, "option_id": "x"},
    )
    rules = {h.rule for h in evaluate(context, AutonomyLevel.TRUSTED)}
    assert "rest_waiver_required" not in rules
    assert consent.has_granted(worker_id, gap.shift_id)


def test_a_decline_still_stops_the_cover_at_every_level():
    world = SableCoffee()
    consent = ConsentStore()
    _, gap, options = _consent_forced_gap(world)
    worker_id = options[0].worker_id

    request = consent.ask(
        worker_id=worker_id, shift_id=gap.shift_id, kind=ConsentKind.REST_WAIVER,
        premium_owed=Money.from_dollars("145.00"), what_it_means="Cover this.",
        asked_at=world.now(), expires_in=timedelta(hours=4),
    )
    consent.answer(request.request_id, ConsentOutcome.DECLINED,
                   answered_at=world.now(), channel="console")

    context = _provider(world, consent)(
        "assign_cover", {"worker_id": worker_id, "shift_id": gap.shift_id, "option_id": "x"},
    )
    assert "worker_declined" in {h.rule for h in evaluate(context, AutonomyLevel.TRUSTED)}
    assert consent.has_granted(worker_id, gap.shift_id) is False


def test_a_grant_for_one_shift_is_not_a_grant_for_another():
    world = SableCoffee()
    consent = ConsentStore()
    _, gap, options = _consent_forced_gap(world)
    worker_id = options[0].worker_id

    request = consent.ask(
        worker_id=worker_id, shift_id="some-other-shift", kind=ConsentKind.REST_WAIVER,
        premium_owed=Money.from_dollars("145.00"), what_it_means="Cover this.",
        asked_at=world.now(), expires_in=timedelta(hours=4),
    )
    consent.answer(request.request_id, ConsentOutcome.GRANTED,
                   answered_at=world.now(), channel="console")

    assert consent.has_granted(worker_id, gap.shift_id) is False
