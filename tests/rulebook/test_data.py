from datetime import date

from muster.domain.types import CarveOut, ChangeKind, NoticeBand
from muster.rulebook.loader import for_code

ON = date(2026, 9, 1)


def test_oregon_pays_one_hour_for_a_move_with_no_loss_of_hours():
    rules = for_code("us-or", on=ON)
    rule = rules.premium_for_band(NoticeBand.INSIDE_WINDOW, ChangeKind.MOVE_NO_LOSS)
    assert rule.hours_at_rate == 1.0
    assert rule.amount_cents is None


def test_oregon_pays_half_rate_per_hour_lost():
    rules = for_code("us-or", on=ON)
    rule = rules.premium_for_band(NoticeBand.INSIDE_WINDOW, ChangeKind.SUBTRACT_HOURS)
    assert rule.fraction_of_lost_hours == 0.5


def test_oregon_offers_the_standby_carve_out_and_chicago_does_not():
    assert CarveOut.STANDBY_LIST in for_code("us-or", on=ON).carve_outs
    assert CarveOut.STANDBY_LIST not in for_code("us-il-chicago", on=ON).carve_outs


def test_chicago_rest_is_1_25_times_base_and_has_no_carve_outs():
    """The Chicago FAQ is explicit: 'Right to Rest ... have no exceptions.'"""
    rules = for_code("us-il-chicago", on=ON)
    assert rules.rest_hours == 10.0
    assert rules.rest_remedy.multiplier == 1.25
    assert rules.rest_remedy.overtime_multiplier == 1.5
    assert rules.rest_has_carve_outs is False
    assert rules.rest_requires_written_consent is True


def test_chicago_pays_half_of_hours_cancelled_inside_24_hours():
    rules = for_code("us-il-chicago", on=ON)
    rule = rules.premium_for_band(NoticeBand.UNDER_24_HOURS, ChangeKind.CANCEL_SHIFT)
    assert rule.fraction_of_lost_hours == 0.5


def test_nyc_fast_food_premium_tiers():
    rules = for_code("us-ny-nyc-fastfood", on=ON)
    tiers = {
        (NoticeBand.INSIDE_WINDOW, ChangeKind.MOVE_NO_LOSS): 1000,
        (NoticeBand.INSIDE_WINDOW, ChangeKind.SUBTRACT_HOURS): 2000,
        (NoticeBand.UNDER_7_DAYS, ChangeKind.MOVE_NO_LOSS): 4500,
        (NoticeBand.UNDER_7_DAYS, ChangeKind.SUBTRACT_HOURS): 4500,
        (NoticeBand.UNDER_24_HOURS, ChangeKind.MOVE_NO_LOSS): 7500,
        (NoticeBand.UNDER_24_HOURS, ChangeKind.SUBTRACT_HOURS): 7500,
    }
    for (band, kind), cents in tiers.items():
        assert rules.premium_for_band(band, kind).amount_cents == cents, (band, kind)


def test_nyc_clopening_is_eleven_hours_and_one_hundred_dollars():
    """NYC defines a clopening at fewer than 11 hours, not the 10 used elsewhere."""
    rules = for_code("us-ny-nyc-fastfood", on=ON)
    assert rules.rest_hours == 11.0
    assert rules.rest_remedy.flat_amount_cents == 10000
    assert rules.rest_requires_written_consent is True


def test_nyc_retail_notice_is_seventy_two_hours_not_fourteen_days():
    assert for_code("us-ny-nyc-retail", on=ON).notice_hours == 72


def test_full_notice_never_owes_a_premium_anywhere():
    for code in ("us-or", "us-il-chicago", "us-ny-nyc-fastfood", "us-ny-nyc-retail"):
        rules = for_code(code, on=ON)
        assert rules.premium_for_band(NoticeBand.FULL_NOTICE, ChangeKind.MOVE_NO_LOSS) is None
