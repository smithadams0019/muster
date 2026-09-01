from datetime import date, datetime, timedelta, timezone

import pytest

from muster.domain.rest import breaches_rest, rest_gap_hours, rest_remedy_owed
from muster.domain.types import Money
from muster.rulebook.loader import for_code

TZ = timezone.utc
ON = date(2026, 9, 1)
OR_RULES = for_code("us-or", on=ON)
CHI = for_code("us-il-chicago", on=ON)
NYC = for_code("us-ny-nyc-fastfood", on=ON)
RATE = Money.from_dollars("18.00")

CLOSE = datetime(2026, 7, 27, 23, 0, tzinfo=TZ)


def test_the_gap_is_measured_in_hours_between_shifts():
    assert rest_gap_hours(CLOSE, CLOSE + timedelta(hours=8, minutes=30)) == 8.5


def test_an_overlapping_pair_of_shifts_is_a_negative_gap_not_an_error():
    assert rest_gap_hours(CLOSE, CLOSE - timedelta(hours=1)) == -1.0


def test_ten_hours_clears_oregon_and_chicago_but_not_nyc():
    assert breaches_rest(10.0, OR_RULES) is False
    assert breaches_rest(10.0, CHI) is False
    assert breaches_rest(10.0, NYC) is True          # NYC clopening is under 11 hours


def test_just_under_the_threshold_breaches():
    assert breaches_rest(9.99, CHI) is True
    assert breaches_rest(10.99, NYC) is True


def test_chicago_pays_a_quarter_over_base_for_the_hours_worked():
    """1.25x base is a 0.25x premium on top of the wages already owed."""
    owed = rest_remedy_owed(8.0, 0.0, RATE, CHI)
    assert owed == Money.from_dollars("36.00")       # 18.00 * 0.25 * 8


def test_chicago_pays_a_half_over_base_for_the_overtime_hours():
    owed = rest_remedy_owed(8.0, 2.0, RATE, CHI)
    assert owed == Money.from_dollars("45.00")       # 6h * 4.50 + 2h * 9.00


def test_oregon_pays_a_half_over_base_throughout():
    owed = rest_remedy_owed(8.0, 0.0, RATE, OR_RULES)
    assert owed == Money.from_dollars("72.00")       # 18.00 * 0.5 * 8


def test_nyc_pays_one_hundred_dollars_flat_however_long_the_shift():
    assert rest_remedy_owed(4.0, 0.0, RATE, NYC) == Money.from_dollars("100.00")
    assert rest_remedy_owed(9.0, 2.0, RATE, NYC) == Money.from_dollars("100.00")


def test_chicago_rest_has_no_carve_outs_and_the_rulebook_says_so():
    """Cited: 'Other rights, such as Right to Rest ... have no exceptions.'"""
    assert CHI.rest_has_carve_outs is False
    assert OR_RULES.rest_has_carve_outs is True


def test_overtime_hours_cannot_exceed_hours_worked():
    with pytest.raises(ValueError, match="overtime"):
        rest_remedy_owed(4.0, 5.0, RATE, CHI)
