from datetime import date

import pytest

from muster.domain.premiums import premium_for
from muster.domain.types import ChangeKind, Money, NoticeBand
from muster.rulebook.loader import for_code

ON = date(2026, 9, 1)
OR_RULES = for_code("us-or", on=ON)
CHI = for_code("us-il-chicago", on=ON)
NYC = for_code("us-ny-nyc-fastfood", on=ON)
RATE = Money.from_dollars("18.50")


def test_full_notice_costs_nothing_anywhere():
    for rules in (OR_RULES, CHI, NYC):
        owed = premium_for(ChangeKind.MOVE_NO_LOSS, NoticeBand.FULL_NOTICE, RATE, 0.0, rules)
        assert owed == Money.zero()


def test_nyc_pays_a_flat_tier_regardless_of_rate():
    owed = premium_for(ChangeKind.MOVE_NO_LOSS, NoticeBand.UNDER_24_HOURS, RATE, 0.0, NYC)
    assert owed == Money.from_dollars("75.00")
    cheaper = premium_for(ChangeKind.MOVE_NO_LOSS, NoticeBand.UNDER_24_HOURS,
                          Money.from_dollars("16.00"), 0.0, NYC)
    assert cheaper == owed


def test_oregon_pays_one_hour_at_the_workers_own_rate():
    owed = premium_for(ChangeKind.ADD_SHIFT, NoticeBand.UNDER_24_HOURS, RATE, 0.0, OR_RULES)
    assert owed == Money.from_dollars("18.50")


def test_oregon_pays_half_rate_for_every_hour_taken_away():
    owed = premium_for(ChangeKind.SUBTRACT_HOURS, NoticeBand.UNDER_7_DAYS, RATE, 3.0, OR_RULES)
    assert owed == Money.from_dollars("27.75")            # 18.50 * 0.5 * 3


def test_a_half_cent_rounds_half_up_once_not_per_hour():
    """$0.05/h for 3 lost hours at half rate is 7.5c. Rounding per hour would give 9c."""
    owed = premium_for(ChangeKind.SUBTRACT_HOURS, NoticeBand.UNDER_7_DAYS,
                       Money(cents=5), 3.0, OR_RULES)
    assert owed == Money(cents=8)


def test_chicago_cancellation_inside_24_hours_is_half_the_lost_hours():
    owed = premium_for(ChangeKind.CANCEL_SHIFT, NoticeBand.UNDER_24_HOURS, RATE, 8.0, CHI)
    assert owed == Money.from_dollars("74.00")            # 18.50 * 0.5 * 8


def test_chicago_owes_nothing_for_a_cancellation_with_more_than_24_hours_notice():
    """Chicago prices cancellations only inside 24 hours; the schedule has no other rule."""
    owed = premium_for(ChangeKind.CANCEL_SHIFT, NoticeBand.UNDER_7_DAYS, RATE, 8.0, CHI)
    assert owed == Money.zero()


def test_a_change_kind_the_jurisdiction_does_not_price_costs_nothing():
    owed = premium_for(ChangeKind.ON_CALL_NOT_CALLED, NoticeBand.UNDER_24_HOURS, RATE, 4.0, CHI)
    assert owed == Money.zero()


def test_hours_lost_must_be_supplied_when_the_rule_needs_it():
    """Unknown is never free: a fraction-of-hours rule with no hours is an error."""
    with pytest.raises(ValueError, match="hours_lost"):
        premium_for(ChangeKind.SUBTRACT_HOURS, NoticeBand.UNDER_7_DAYS, RATE, 0.0, OR_RULES)


def test_a_negative_rate_is_rejected():
    with pytest.raises(ValueError, match="rate"):
        premium_for(ChangeKind.ADD_SHIFT, NoticeBand.UNDER_24_HOURS, Money(cents=-1), 0.0, OR_RULES)
