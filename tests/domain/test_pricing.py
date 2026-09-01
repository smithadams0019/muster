from datetime import date, datetime, timedelta, timezone

from muster.domain.carve_outs import CarveOutClaim
from muster.domain.pricing import price_change
from muster.domain.types import CarveOut, ChangeKind, ConsentKind, Money
from muster.rulebook.loader import for_code
from tests.domain.test_carve_outs import FakeEvidence

TZ = timezone.utc
ON = date(2026, 9, 1)
STARTS = datetime(2026, 7, 27, 0, 0, tzinfo=TZ)
POSTED = STARTS - timedelta(days=14)
RATE = Money.from_dollars("18.00")


def _price(code, *, kind=ChangeKind.ADD_SHIFT, changed_at=None, hours_lost=0.0,
           rest_gap=None, hours_worked=8.0, hours_before=20.0, claims=(), evidence=None):
    return price_change(
        rules=for_code(code, on=ON),
        kind=kind,
        posted_at=POSTED,
        changed_at=changed_at or STARTS - timedelta(hours=3),
        schedule_starts_at=STARTS,
        hourly_rate=RATE,
        hours_lost=hours_lost,
        hours_worked=hours_worked,
        hours_before_this_week=hours_before,
        rest_gap_hours=rest_gap,
        worker_id="w-1",
        shift_id="s-1",
        claims=claims,
        evidence=evidence or FakeEvidence(),
    )


def test_a_last_minute_add_in_nyc_is_seventy_five_dollars_and_says_which_clause():
    result = _price("us-ny-nyc-fastfood")
    assert result.total == Money.from_dollars("75.00")
    assert len(result.lines) == 1
    assert "premium" in result.lines[0].clause
    assert result.lines[0].citation.startswith("DCWP")


def test_an_evidenced_standby_acceptance_in_oregon_costs_nothing():
    result = _price(
        "us-or",
        claims=(CarveOutClaim(CarveOut.STANDBY_LIST),),
        evidence=FakeEvidence(on_standby=True, standby_accepted=True),
    )
    assert result.total == Money.zero()
    assert CarveOut.STANDBY_LIST in result.carve_outs_applied


def test_the_same_standby_claim_in_chicago_is_not_honoured():
    result = _price(
        "us-il-chicago",
        changed_at=STARTS - timedelta(days=3),   # under_7_days: Chicago prices add_shift here
        claims=(CarveOutClaim(CarveOut.STANDBY_LIST),),
        evidence=FakeEvidence(on_standby=True, standby_accepted=True),
    )
    assert result.total == Money.from_dollars("18.00")     # one hour at rate
    assert result.carve_outs_applied == ()


def test_a_cover_inside_the_rest_period_adds_the_remedy_and_demands_consent():
    result = _price("us-il-chicago", rest_gap=7.0, hours_worked=8.0)
    clauses = {line.clause for line in result.lines}
    assert any("rest" in c for c in clauses)
    assert result.requires_consent is True
    assert result.consent_kind is ConsentKind.REST_WAIVER


def test_a_cover_that_crosses_forty_hours_adds_an_overtime_line():
    result = _price("us-or", hours_before=36.0, hours_worked=8.0)
    assert any("overtime" in line.clause for line in result.lines)


def test_lines_sum_to_the_total_exactly():
    result = _price("us-il-chicago", rest_gap=7.0, hours_before=38.0)
    assert sum(line.amount.cents for line in result.lines) == result.total.cents


def test_nyc_retail_inside_seventy_two_hours_is_unlawful_not_merely_expensive():
    """The retail rule prohibits the change; a price would imply it may be bought."""
    result = _price("us-ny-nyc-retail", kind=ChangeKind.CANCEL_SHIFT, hours_lost=8.0)
    assert result.lawful is False
    assert "72 hours" in result.unlawful_reason


def test_a_negative_rate_is_refused_by_the_composed_pricer():
    import pytest
    with pytest.raises(ValueError, match="negative"):
        price_change(
            rules=for_code("us-or", on=ON), kind=ChangeKind.ADD_SHIFT,
            posted_at=POSTED, changed_at=STARTS, schedule_starts_at=STARTS,
            hourly_rate=Money(cents=-1), hours_lost=0.0, hours_worked=8.0,
            hours_before_this_week=0.0, rest_gap_hours=None,
            worker_id="w-1", shift_id="s-1", claims=(), evidence=FakeEvidence(),
        )
