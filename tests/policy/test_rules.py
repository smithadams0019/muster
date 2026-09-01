import pytest

from muster.domain.types import AutonomyLevel, Money
from muster.policy.rules import (
    NON_NEGOTIABLE_RULES, THRESHOLDS, CoverContext, evaluate,
)


def _ctx(**overrides):
    base = dict(
        cost=Money.zero(), week_spend=Money.zero(), overtime_hours=0.0,
        shortfall_fraction=0.0, requires_rest_waiver=False, worker_declined=False,
        meets_role_minimum=True, meets_certification_minimum=True, assessable=True,
    )
    return CoverContext(**{**base, **overrides})


def test_a_free_cover_passes_at_every_level():
    for level in AutonomyLevel:
        assert evaluate(_ctx(), level) == []


def test_conservative_will_not_spend_a_cent_alone():
    hits = evaluate(_ctx(cost=Money(cents=1)), AutonomyLevel.CONSERVATIVE)
    assert [h.rule for h in hits] == ["cost_over_budget"]


def test_balanced_absorbs_seventy_five_dollars_but_not_seventy_five_oh_one():
    assert evaluate(_ctx(cost=Money.from_dollars("75.00")), AutonomyLevel.BALANCED) == []
    hits = evaluate(_ctx(cost=Money.from_dollars("75.01")), AutonomyLevel.BALANCED)
    assert [h.rule for h in hits] == ["cost_over_budget"]


def test_the_weekly_budget_stops_a_cover_that_is_individually_affordable():
    hits = evaluate(
        _ctx(cost=Money.from_dollars("50.00"), week_spend=Money.from_dollars("380.00")),
        AutonomyLevel.BALANCED,
    )
    assert "weekly_budget_exhausted" in {h.rule for h in hits}


def test_a_rest_waiver_escalates_at_every_level_including_trusted():
    for level in AutonomyLevel:
        hits = evaluate(_ctx(requires_rest_waiver=True), level)
        assert "rest_waiver_required" in {h.rule for h in hits}, level


def test_a_prior_decline_escalates_at_every_level_including_trusted():
    for level in AutonomyLevel:
        hits = evaluate(_ctx(worker_declined=True), level)
        assert "worker_declined" in {h.rule for h in hits}, level


def test_the_two_non_negotiables_are_named_and_only_those_two():
    assert NON_NEGOTIABLE_RULES == frozenset({"rest_waiver_required", "worker_declined"})


def test_understaffing_escalates_however_cheap_the_cover_is():
    hits = evaluate(_ctx(meets_certification_minimum=False), AutonomyLevel.TRUSTED)
    assert "understaffed_below_minimum" in {h.rule for h in hits}


def test_an_unassessable_cover_escalates_rather_than_passing():
    hits = evaluate(_ctx(assessable=False), AutonomyLevel.TRUSTED)
    assert [h.rule for h in hits] == ["unassessable"]


def test_raising_autonomy_never_increases_the_number_of_escalations():
    contexts = [
        _ctx(cost=Money.from_dollars("40.00")),
        _ctx(overtime_hours=3.0),
        _ctx(shortfall_fraction=0.15),
        _ctx(requires_rest_waiver=True),
    ]
    for context in contexts:
        counts = [len(evaluate(context, level)) for level in
                  (AutonomyLevel.CONSERVATIVE, AutonomyLevel.BALANCED, AutonomyLevel.TRUSTED)]
        assert counts == sorted(counts, reverse=True), context


def test_every_hit_explains_itself_in_money_or_hours_not_a_rule_code():
    hits = evaluate(_ctx(cost=Money.from_dollars("120.00")), AutonomyLevel.BALANCED)
    assert "$120.00" in hits[0].detail and "$75.00" in hits[0].detail
