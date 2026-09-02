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


def test_a_fresh_tools_instance_still_honours_an_option_the_previous_one_offered():
    """A resumed run is a new agent with a new closure, so its cache is empty.

    The operator approves an option the *previous* instance priced; without
    re-deriving, assign_cover refused it as unknown, the model tried a different
    worker, and that escalated again — approving cloned the question instead of
    answering it.
    """
    world = SableCoffee()
    shift = _open_shift(world)

    _, _, _, _, first = _tools(world)
    offered = first["list_cover_options"](shift_id=shift.shift_id)[0]

    # A brand-new tools closure over the same world, as the resumer builds.
    _, ledger, receipts, _, second = _tools(world)
    result = second["assign_cover"](
        shift_id=shift.shift_id, worker_id=offered["worker_id"],
        option_id=offered["option_id"],
    )
    assert "error" not in result
    assert any(e["kind"] == "assign_cover" for e in ledger)
    assert len(receipts.all()) == 1


def test_an_invented_option_id_is_still_refused_after_re_deriving():
    world = SableCoffee()
    shift = _open_shift(world)
    _, ledger, _, _, tools = _tools(world)
    result = tools["assign_cover"](
        shift_id=shift.shift_id, worker_id="w-nyc-6", option_id="opt-made-up",
    )
    assert "error" in result
    assert ledger == []


def test_an_unknown_consent_kind_is_refused_with_the_ones_that_would_work():
    """A refusal that names only the rejected value is a dead end. A live run
    spent four calls guessing at this and left the shift uncovered."""
    from muster.domain.types import ConsentKind

    world, _, _, _, tools = _tools()
    schedule = world.schedule("site-nyc", datetime(2026, 7, 27, tzinfo=TZ))
    gap = next(s for s in schedule.shifts if s.worker_id and s.starts_at >= datetime(2026, 7, 27, tzinfo=TZ))
    other = next(w for w in world.workers("site-nyc") if w.worker_id != gap.worker_id)

    result = tools["request_consent"](
        worker_id=other.worker_id, shift_id=gap.shift_id, kind="rest_period_premium",
    )
    assert "error" in result
    for kind in ConsentKind:
        assert kind.value in result["error"]


def test_an_option_that_needs_consent_says_which_consent():
    """So request_consent is never a guess."""
    world, _, _, _, tools = _tools()
    schedule = world.schedule("site-nyc", datetime(2026, 7, 27, tzinfo=TZ))

    seen_consent = False
    for shift in schedule.shifts:
        if shift.worker_id is None:
            continue
        offers = tools["list_cover_options"](shift_id=shift.shift_id)
        if isinstance(offers, dict):  # the bridge shift's week is not posted
            continue
        for offer in offers:
            if offer["requires_consent"]:
                assert offer["consent_kind"] == "rest_waiver"
                seen_consent = True
            else:
                assert offer["consent_kind"] is None
    assert seen_consent, "the seeded week must contain a cover that needs consent"


def test_a_cover_that_needed_consent_carries_it_onto_the_receipt():
    """The receipt is what an investigator reads, and 'who consented and when' is
    among the first things they look for. It used to be written as None."""
    from datetime import timedelta

    from muster.domain.types import ConsentKind, ConsentOutcome, Money

    world, _, receipts, consent, tools = _tools()
    schedule = world.schedule("site-nyc", datetime(2026, 7, 27, tzinfo=TZ))
    gap = next(
        s for s in schedule.shifts
        if s.worker_id and s.starts_at >= datetime(2026, 7, 27, tzinfo=TZ)
    )
    offers = tools["list_cover_options"](shift_id=gap.shift_id)
    chosen = offers[0]

    request = consent.ask(
        worker_id=chosen["worker_id"], shift_id=gap.shift_id, kind=ConsentKind.REST_WAIVER,
        premium_owed=Money.from_dollars("145.00"), what_it_means="Cover this.",
        asked_at=world.now(), expires_in=timedelta(hours=4),
    )
    consent.answer(request.request_id, ConsentOutcome.GRANTED,
                   answered_at=world.now(), channel="sms")

    tools["assign_cover"](shift_id=gap.shift_id, worker_id=chosen["worker_id"],
                          option_id=chosen["option_id"])

    written = receipts.all()[-1]
    assert written.consent is not None
    assert written.consent.outcome is ConsentOutcome.GRANTED
    assert written.consent.channel == "sms"


def test_a_cover_nobody_was_asked_about_carries_no_consent():
    world, _, receipts, _, tools = _tools()
    schedule = world.schedule("site-or", datetime(2026, 7, 27, tzinfo=TZ))
    gap = next(
        s for s in schedule.shifts
        if s.worker_id and s.starts_at >= datetime(2026, 7, 27, tzinfo=TZ)
    )
    offers = tools["list_cover_options"](shift_id=gap.shift_id)
    tools["assign_cover"](shift_id=gap.shift_id, worker_id=offers[0]["worker_id"],
                          option_id=offers[0]["option_id"])
    assert receipts.all()[-1].consent is None
