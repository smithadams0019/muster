import pytest

from muster.domain.overtime import overtime_delta
from muster.domain.types import Money

RATE = Money.from_dollars("20.00")


def test_hours_well_under_the_threshold_add_no_overtime():
    cost, ot_hours = overtime_delta(20.0, 6.0, RATE)
    assert cost == Money.zero()
    assert ot_hours == 0.0


def test_hours_that_cross_the_threshold_split():
    """36 + 6 = 42. Four hours are straight time, two are overtime."""
    cost, ot_hours = overtime_delta(36.0, 6.0, RATE)
    assert ot_hours == 2.0
    assert cost == Money.from_dollars("20.00")        # 2h * half-rate premium


def test_a_worker_already_over_the_threshold_pays_the_premium_on_everything_added():
    cost, ot_hours = overtime_delta(44.0, 3.0, RATE)
    assert ot_hours == 3.0
    assert cost == Money.from_dollars("30.00")


def test_landing_exactly_on_the_threshold_is_not_overtime():
    cost, ot_hours = overtime_delta(36.0, 4.0, RATE)
    assert ot_hours == 0.0
    assert cost == Money.zero()


def test_the_threshold_is_configurable_for_states_that_differ():
    cost, ot_hours = overtime_delta(8.0, 4.0, RATE, weekly_threshold=8.0)
    assert ot_hours == 4.0
    assert cost == Money.from_dollars("40.00")


def test_negative_hours_are_rejected():
    with pytest.raises(ValueError, match="negative"):
        overtime_delta(-1.0, 4.0, RATE)
