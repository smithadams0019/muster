from datetime import date, datetime, timedelta, timezone

from muster.domain.notice import notice_band
from muster.domain.types import NoticeBand
from muster.rulebook.loader import for_code

TZ = timezone.utc
STARTS = datetime(2026, 7, 27, 0, 0, tzinfo=TZ)      # Monday, first day on the schedule
NYC = for_code("us-ny-nyc-fastfood", on=date(2026, 9, 1))
RETAIL = for_code("us-ny-nyc-retail", on=date(2026, 9, 1))


def _band(changed_at, rules=NYC):
    posted = STARTS - timedelta(days=14)
    return notice_band(posted, changed_at, STARTS, rules)


def test_a_change_before_the_window_opens_is_full_notice():
    assert _band(STARTS - timedelta(days=20)) is NoticeBand.FULL_NOTICE


def test_a_change_exactly_at_the_window_edge_is_full_notice():
    """At the boundary the employer gave the notice the law asks for."""
    assert _band(STARTS - timedelta(hours=336)) is NoticeBand.FULL_NOTICE


def test_a_change_inside_the_window_but_over_seven_days_out():
    assert _band(STARTS - timedelta(days=12, hours=12)) is NoticeBand.INSIDE_WINDOW


def test_the_dcwp_worked_example_of_151_hours_is_under_seven_days():
    """DCWP: 'posted 151 hours (6.2 days) before ... premium of $45'."""
    assert _band(STARTS - timedelta(hours=151)) is NoticeBand.UNDER_7_DAYS


def test_exactly_seven_days_is_not_yet_under_seven_days():
    assert _band(STARTS - timedelta(days=7)) is NoticeBand.INSIDE_WINDOW


def test_fifteen_hours_before_the_schedule_begins_is_under_24_hours():
    """DCWP: 'posted and emailed 15 hours before ... premium of $75'."""
    assert _band(STARTS - timedelta(hours=15)) is NoticeBand.UNDER_24_HOURS


def test_exactly_24_hours_is_not_yet_under_24_hours():
    assert _band(STARTS - timedelta(hours=24)) is NoticeBand.UNDER_7_DAYS


def test_a_change_after_the_schedule_has_begun_is_still_under_24_hours():
    assert _band(STARTS + timedelta(days=2)) is NoticeBand.UNDER_24_HOURS


def test_a_shorter_notice_window_moves_the_full_notice_edge():
    """NYC retail requires 72 hours, so 100 hours out is full notice there."""
    posted = STARTS - timedelta(days=14)
    assert notice_band(posted, STARTS - timedelta(hours=100), STARTS, RETAIL) is NoticeBand.FULL_NOTICE
    assert notice_band(posted, STARTS - timedelta(hours=50), STARTS, RETAIL) is NoticeBand.UNDER_7_DAYS


def test_a_naive_timestamp_is_rejected_rather_than_assumed_utc():
    import pytest
    naive = datetime(2026, 7, 20, 12, 0)
    with pytest.raises(ValueError, match="timezone"):
        notice_band(naive, naive, STARTS, NYC)
