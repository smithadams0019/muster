# tests/loops/test_draft.py
from datetime import datetime, timezone

from muster.adapters.simulated import SableCoffee
from muster.loops.draft.tools import build_draft_tools

TZ = timezone.utc
WEEK = datetime(2026, 8, 3, tzinfo=TZ)          # the week after the seeded one


def _tools():
    world = SableCoffee()
    ledger: list[dict] = []
    tools = {t.tool_name: t for t in build_draft_tools(world, ledger, week_starts_at=WEEK,
                                                       clock=world.now)}
    return world, ledger, tools


def test_an_empty_draft_reports_every_uncovered_hour():
    _, _, tools = _tools()
    problems = tools["check_draft"](site_id="site-or")
    assert any(p["kind"] == "uncovered" for p in problems)


def test_proposing_a_shift_reduces_the_uncovered_problems():
    _, _, tools = _tools()
    before = len([p for p in tools["check_draft"](site_id="site-or") if p["kind"] == "uncovered"])
    tools["propose_shift"](site_id="site-or", worker_id="w-or-1", day="2026-08-03",
                           start_hour=6, end_hour=14, role="barista")
    after = len([p for p in tools["check_draft"](site_id="site-or") if p["kind"] == "uncovered"])
    assert after < before


def test_a_draft_that_breaks_a_rest_period_is_reported_not_silently_accepted():
    _, _, tools = _tools()
    tools["propose_shift"](site_id="site-or", worker_id="w-or-1", day="2026-08-03",
                           start_hour=14, end_hour=22, role="barista")
    tools["propose_shift"](site_id="site-or", worker_id="w-or-1", day="2026-08-04",
                           start_hour=6, end_hour=14, role="barista")
    problems = tools["check_draft"](site_id="site-or")
    assert any(p["kind"] == "rest_breach" for p in problems)


def test_a_shift_outside_a_workers_stated_availability_is_reported():
    world, _, tools = _tools()
    worker = world.workers("site-or")[0]
    window = worker.unavailable[0] if worker.unavailable else None
    if window is None:
        return
    tools["propose_shift"](site_id="site-or", worker_id=worker.worker_id,
                           day=window.starts_at.date().isoformat(),
                           start_hour=window.starts_at.hour, end_hour=window.starts_at.hour + 4,
                           role="barista")
    assert any(p["kind"] == "unavailable" for p in tools["check_draft"](site_id="site-or"))


def test_a_worker_left_below_their_good_faith_hours_is_reported():
    _, _, tools = _tools()
    tools["propose_shift"](site_id="site-or", worker_id="w-or-1", day="2026-08-03",
                           start_hour=6, end_hour=10, role="barista")
    problems = tools["check_draft"](site_id="site-or")
    assert any(p["kind"] == "hours_shortfall" and p["worker_id"] == "w-or-1" for p in problems)


def test_posting_writes_the_schedule_and_starts_the_notice_clock():
    world, ledger, tools = _tools()
    tools["propose_shift"](site_id="site-or", worker_id="w-or-1", day="2026-08-03",
                           start_hour=6, end_hour=14, role="barista")
    result = tools["post_schedule"](site_id="site-or")
    assert result["posted_at"]
    posted = world.schedule("site-or", WEEK)
    assert posted.is_posted
    assert any(e["kind"] == "post_schedule" for e in ledger)


def test_posting_an_empty_draft_is_refused():
    _, _, tools = _tools()
    assert "error" in tools["post_schedule"](site_id="site-or")


def test_proposing_for_a_worker_at_another_site_is_refused():
    _, _, tools = _tools()
    result = tools["propose_shift"](site_id="site-or", worker_id="w-nyc-1", day="2026-08-03",
                                    start_hour=6, end_hour=14, role="barista")
    assert "error" in result
