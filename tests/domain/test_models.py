# tests/domain/test_models.py
from datetime import datetime, timedelta, timezone

import pytest

from muster.domain.models import Schedule, Shift, Site, Worker
from muster.domain.types import Money, Role

TZ = timezone.utc
MON = datetime(2026, 7, 27, 0, 0, tzinfo=TZ)


def _shift(worker="w-1", start_hour=7, hours=8, shift_id="s-1"):
    return Shift(
        shift_id=shift_id, site_id="site-1", role=Role.BARISTA,
        starts_at=MON + timedelta(hours=start_hour),
        ends_at=MON + timedelta(hours=start_hour + hours),
        worker_id=worker,
    )


def test_a_shift_knows_its_length_in_hours():
    assert _shift(hours=8).hours == 8.0
    assert _shift(hours=0).hours == 0.0


def test_a_shift_ending_before_it_starts_is_rejected():
    with pytest.raises(ValueError, match="ends before"):
        Shift(shift_id="s", site_id="site-1", role=Role.BARISTA,
              starts_at=MON + timedelta(hours=9), ends_at=MON, worker_id="w-1")


def test_a_worker_reports_hours_already_scheduled_in_a_week():
    schedule = Schedule(site_id="site-1", week_starts_at=MON, posted_at=None,
                        shifts=(_shift(hours=8, shift_id="a"),
                                _shift(hours=6, shift_id="b", start_hour=20)))
    assert schedule.hours_for("w-1") == 14.0
    assert schedule.hours_for("w-2") == 0.0


def test_an_unposted_schedule_is_not_yet_governed_by_the_notice_clock():
    schedule = Schedule(site_id="site-1", week_starts_at=MON, posted_at=None, shifts=())
    assert schedule.is_posted is False


def test_the_previous_shift_for_a_worker_is_the_one_that_ended_last():
    early = _shift(shift_id="a", start_hour=6, hours=6)
    late = _shift(shift_id="b", start_hour=15, hours=8)
    schedule = Schedule(site_id="site-1", week_starts_at=MON, posted_at=MON, shifts=(early, late))
    found = schedule.last_shift_ending_before("w-1", MON + timedelta(days=1, hours=7))
    assert found.shift_id == "b"


def test_a_site_declares_its_jurisdiction_and_minimums():
    site = Site(site_id="site-1", name="Sable Pearl", jurisdiction_code="us-or",
                opens_at_hour=6, closes_at_hour=20,
                role_minimums={Role.SHIFT_LEAD: 1, Role.BARISTA: 2},
                certified_handler_minimum=1)
    assert site.jurisdiction_code == "us-or"
    assert site.role_minimums[Role.SHIFT_LEAD] == 1


def test_a_worker_carries_the_rate_and_the_good_faith_estimate():
    worker = Worker(worker_id="w-1", name="Ada", site_id="site-1", role=Role.BARISTA,
                    hourly_rate=Money.from_dollars("18.50"), good_faith_hours=30.0,
                    certifications=frozenset({"food_handler"}), on_standby_list=True,
                    unavailable=())
    assert worker.hourly_rate.cents == 1850
    assert worker.is_certified("food_handler") is True
    assert worker.is_certified("first_aid") is False
