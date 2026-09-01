import pytest

from muster.domain.types import AutonomyLevel, ChangeKind, Money, NoticeBand


def test_money_is_cents_and_never_a_float():
    assert Money.from_dollars("10.00").cents == 1000
    assert Money(cents=1075).dollars == "10.75"


def test_money_arithmetic_stays_exact():
    total = Money(cents=1000) + Money(cents=575)
    assert total.cents == 1575
    assert (total - Money(cents=75)).cents == 1500


def test_money_scaling_rounds_half_up_once():
    assert Money.from_dollars("13.75").scaled(1.5).cents == 2063
    assert Money.from_dollars("0.05").scaled(0.5).cents == 3


def test_money_is_ordered_so_options_can_be_ranked():
    assert Money(cents=0) < Money(cents=1)
    assert min([Money(cents=500), Money(cents=0), Money(cents=75)]) == Money(cents=0)


def test_money_rejects_a_float_constructor():
    with pytest.raises(TypeError):
        Money(cents=10.5)


def test_the_enums_carry_the_vocabulary_the_ordinances_use():
    assert ChangeKind.SUBTRACT_HOURS.value == "subtract_hours"
    assert NoticeBand.UNDER_24_HOURS.value == "under_24_hours"
    assert [level.value for level in AutonomyLevel] == ["conservative", "balanced", "trusted"]
