from datetime import datetime, timezone

from muster.adapters.simulated import SableCoffee
from muster.loops.hold.tools import build_hold_tools
from muster.persistence.consent import ConsentStore
from muster.persistence.receipts import ReceiptBook

TZ = timezone.utc


def _tools(world=None):
    world = world or SableCoffee()
    ledger: list[dict] = []
    receipts, consent = ReceiptBook(), ConsentStore()
    tools = {t.tool_name: t for t in build_hold_tools(world, ledger, receipts, consent,
                                                      clock=world.now)}
    return world, ledger, receipts, consent, tools


def _open_shift(world, site="site-or"):
    schedule = world.schedule(site, datetime(2026, 7, 27, tzinfo=TZ))
    return next(s for s in schedule.shifts if s.starts_at.hour == 7)


def test_options_come_back_cheapest_first_with_a_total_and_a_clause():
    world, _, _, _, tools = _tools()
    options = tools["list_cover_options"](shift_id=_open_shift(world).shift_id)
    assert options
    totals = [o["total_cents"] for o in options]
    assert totals == sorted(totals)
    assert "clauses" in options[0]


def test_a_free_standby_option_exists_in_oregon_and_is_ranked_first():
    world, _, _, _, tools = _tools()
    shift = _open_shift(world)
    standby = next(w for w in world.workers("site-or") if w.on_standby_list)
    world.record_standby_acceptance(standby.worker_id, shift.shift_id)
    options = tools["list_cover_options"](shift_id=shift.shift_id)
    assert options[0]["total_cents"] == 0
    assert options[0]["worker_id"] == standby.worker_id


def test_assigning_a_cover_writes_the_ledger_and_a_receipt():
    world, ledger, receipts, _, tools = _tools()
    shift = _open_shift(world)
    option = tools["list_cover_options"](shift_id=shift.shift_id)[0]
    tools["assign_cover"](shift_id=shift.shift_id, worker_id=option["worker_id"],
                          option_id=option["option_id"])
    assert any(e["kind"] == "assign_cover" for e in ledger)
    assert len(receipts.all()) == 1


def test_assigning_a_hallucinated_option_id_is_refused():
    world, ledger, _, _, tools = _tools()
    shift = _open_shift(world)
    result = tools["assign_cover"](shift_id=shift.shift_id, worker_id="w-or-1",
                                   option_id="opt-does-not-exist")
    assert "error" in result
    assert ledger == []


def test_assigning_for_a_worker_who_is_not_in_the_option_is_refused():
    world, ledger, _, _, tools = _tools()
    shift = _open_shift(world)
    option = tools["list_cover_options"](shift_id=shift.shift_id)[0]
    result = tools["assign_cover"](shift_id=shift.shift_id, worker_id="w-nyc-1",
                                   option_id=option["option_id"])
    assert "error" in result
    assert ledger == []


def test_requesting_consent_tells_the_worker_the_premium_they_are_owed():
    world, _, _, consent, tools = _tools()
    shift = _open_shift(world)
    result = tools["request_consent"](worker_id="w-or-2", shift_id=shift.shift_id,
                                      kind="rest_waiver")
    assert "$" in result["what_it_means"]
    assert consent.pending()


def test_requesting_consent_from_a_worker_who_declined_is_refused():
    world, _, _, consent, tools = _tools()
    shift = _open_shift(world)
    world.record_decline("w-or-2", shift.shift_id)
    result = tools["request_consent"](worker_id="w-or-2", shift_id=shift.shift_id,
                                      kind="rest_waiver")
    assert "error" in result and "declined" in result["error"]


def test_an_unknown_shift_id_returns_an_error_rather_than_an_empty_list():
    _, _, _, _, tools = _tools()
    assert "error" in tools["list_cover_options"](shift_id="s-nope")
