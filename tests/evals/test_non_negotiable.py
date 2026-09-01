"""No autonomy level may waive a worker's rest or ask someone who said no.

Cited, not invented: Oregon requires the worker's request or consent; NYC requires
written consent for a clopening and defines consent as agreement after a meaningful
opportunity to decline; Chicago's guidance says the Right to Rest has no exceptions.
"""

import pytest

from muster.domain.types import AutonomyLevel, Money
from muster.policy.rules import NON_NEGOTIABLE_RULES, CoverContext, evaluate


def _ctx(**overrides):
    base = dict(
        cost=Money.zero(), week_spend=Money.zero(), overtime_hours=0.0,
        shortfall_fraction=0.0, requires_rest_waiver=False, worker_declined=False,
        meets_role_minimum=True, meets_certification_minimum=True, assessable=True,
    )
    return CoverContext(**{**base, **overrides})


@pytest.mark.parametrize("level", list(AutonomyLevel))
def test_the_only_cover_is_a_clopening_and_it_is_free(level):
    """Free, available, and still not Muster's call to make."""
    hits = evaluate(_ctx(requires_rest_waiver=True, cost=Money.zero()), level)
    assert "rest_waiver_required" in {h.rule for h in hits}


@pytest.mark.parametrize("level", list(AutonomyLevel))
def test_the_worker_already_said_no_once(level):
    hits = evaluate(_ctx(worker_declined=True, cost=Money.zero()), level)
    assert "worker_declined" in {h.rule for h in hits}


def test_the_non_negotiables_are_exactly_these_two():
    assert NON_NEGOTIABLE_RULES == frozenset({"rest_waiver_required", "worker_declined"})


@pytest.mark.parametrize("rule", sorted(NON_NEGOTIABLE_RULES))
def test_no_threshold_in_the_dial_can_switch_a_non_negotiable_off(rule):
    """A dial that could reach these would make the README's claim false."""
    from muster.policy.rules import THRESHOLDS
    for limits in THRESHOLDS.values():
        assert rule not in vars(limits)
