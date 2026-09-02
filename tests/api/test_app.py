from fastapi.testclient import TestClient

from muster.api.app import create_app
from muster.persistence.inbox import Decision  # see note below
from muster.loops.hold.runner import HoldRunResult


def _client(hold_runner=None, resumer=None, draft_runner=None):
    async def noop_hold(state, disruption):
        return HoldRunResult(False, None, None, None, "covered")

    async def noop_resume(state, pending):
        return HoldRunResult(False, None, None, None, "resumed")

    async def noop_draft(state, site_id):
        return HoldRunResult(False, None, None, None, "drafted")

    app = create_app(
        hold_runner=hold_runner or noop_hold,
        draft_runner=draft_runner or noop_draft,
        decision_resumer=resumer or noop_resume,
    )
    return TestClient(app), app.state.muster


DISRUPTION = {"kind": "sick_call", "shift_id": "s-1", "note": "flu"}


def test_health():
    client, _ = _client()
    assert client.get("/health").json() == {"status": "ok"}


def test_the_world_exposes_its_frozen_clock_so_the_console_can_use_it():
    """The console stamps offers from this, never from the browser."""
    client, _ = _client()
    body = client.get("/api/world").json()
    assert body["now"].startswith("2026-07-24T06:00")
    assert len(body["sites"]) == 3


def test_the_world_reports_which_rulebook_governs_each_site():
    client, _ = _client()
    codes = {s["jurisdiction_code"] for s in client.get("/api/world").json()["sites"]}
    assert codes == {"us-or", "us-il-chicago", "us-ny-nyc-fastfood"}


def test_a_covered_disruption_reports_covered_and_leaves_no_decision():
    """Covered means the ledger says somebody was assigned - nothing weaker."""
    async def assigns(state, disruption):
        state.ledger.append({
            "kind": "assign_cover", "shift_id": disruption.shift_id,
            "worker_id": "w-1", "total_cents": 0,
        })
        return HoldRunResult(False, None, None, None, "assigned")

    client, _ = _client(hold_runner=assigns)
    body = client.post("/api/disruptions", json=DISRUPTION).json()
    assert body["status"] == "covered"
    assert client.get("/api/decisions").json() == []


def test_a_run_that_assigned_nobody_is_never_reported_as_covered():
    """The regression: a fallback searched the agent's closing message for the
    word "cover", so a run whose message was "I could not cover this shift"
    reported success while the ledger was empty."""
    async def covers_nobody(state, disruption):
        return HoldRunResult(False, None, None, None, "I could not cover this shift")

    client, _ = _client(hold_runner=covers_nobody)
    assert client.post("/api/disruptions", json=DISRUPTION).json()["status"] == "uncovered"


def test_a_held_disruption_lands_in_the_inbox_with_its_rules_named():
    async def holds(state, disruption):
        return HoldRunResult(
            True, "int-1", "cost_over_budget", {"scope": "agent"}, "needs a person",
            rule_hits=[{"rule": "cost_over_budget", "detail": "$120.00 exceeds $75.00."}],
        )

    client, _ = _client(hold_runner=holds)
    body = client.post("/api/disruptions", json=DISRUPTION).json()
    assert body["status"] == "awaiting_decision"
    pending = client.get("/api/decisions").json()
    assert pending[0]["rule"] == "cost_over_budget"
    assert "$120.00" in pending[0]["rule_hits"][0]["detail"]


def test_a_status_that_is_not_covered_is_never_reported_as_covered():
    """Three outcomes, not two. A run that covered nothing must say so."""
    async def does_nothing(state, disruption):
        return HoldRunResult(False, None, None, None, "nobody could take it")

    client, _ = _client(hold_runner=does_nothing)
    body = client.post("/api/disruptions", json=DISRUPTION).json()
    assert body["status"] == "uncovered"


def test_answering_a_decision_resumes_the_paused_run():
    """The exact regression: recording the human without resuming committed nothing."""
    seen = {}

    async def resumer(state, pending):
        seen["interrupt_id"] = pending.interrupt_id
        seen["snapshot"] = pending.snapshot
        state.ledger.append({"kind": "assign_cover", "shift_id": "s-1",
                             "worker_id": "w-1", "total_cents": 7500})
        return HoldRunResult(False, None, None, None, "assigned after approval")

    async def holds(state, disruption):
        return HoldRunResult(True, "int-9", "cost_over_budget", {"scope": "agent"}, "?",
                             rule_hits=[{"rule": "cost_over_budget", "detail": "d"}])

    client, state = _client(hold_runner=holds, resumer=resumer)
    decision_id = client.post("/api/disruptions", json=DISRUPTION).json()["decision_id"]
    client.post(f"/api/decisions/{decision_id}/answer",
                json={"outcome": "approve", "by": "Roger K", "role": "manager", "note": ""})

    assert seen == {"interrupt_id": "int-9", "snapshot": {"scope": "agent"}}
    assert any(e["kind"] == "assign_cover" for e in state.ledger)
    assert client.get("/api/decisions").json() == []


def test_a_resumed_run_that_pauses_again_goes_back_into_the_inbox():
    async def holds(state, disruption):
        return HoldRunResult(True, "int-9", "cost_over_budget", {"scope": "a"}, "?",
                             rule_hits=[{"rule": "cost_over_budget", "detail": "d"}])

    async def pauses_again(state, pending):
        return HoldRunResult(True, "int-10", "rest_waiver_required", {"scope": "a"}, "?",
                             rule_hits=[{"rule": "rest_waiver_required", "detail": "d"}])

    client, _ = _client(hold_runner=holds, resumer=pauses_again)
    decision_id = client.post("/api/disruptions", json=DISRUPTION).json()["decision_id"]
    client.post(f"/api/decisions/{decision_id}/answer",
                json={"outcome": "approve", "by": "R", "role": "manager", "note": ""})
    pending = client.get("/api/decisions").json()
    assert len(pending) == 1
    assert pending[0]["rule"] == "rest_waiver_required"


def test_answering_an_unknown_decision_is_404():
    client, _ = _client()
    response = client.post("/api/decisions/nope/answer",
                           json={"outcome": "approve", "by": "R", "role": "m", "note": ""})
    assert response.status_code == 404


def test_receipts_export_as_csv_with_a_content_type_a_browser_will_download():
    client, _ = _client()
    response = client.get("/api/receipts.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_the_autonomy_dial_can_be_read_and_changed():
    client, _ = _client()
    assert client.get("/api/autonomy").json()["level"] == "balanced"
    assert client.put("/api/autonomy", json={"level": "trusted"}).status_code == 200
    assert client.get("/api/autonomy").json()["thresholds"]["max_unattended_cents"] == 25000


def test_an_invalid_autonomy_level_is_rejected():
    client, _ = _client()
    assert client.put("/api/autonomy", json={"level": "reckless"}).status_code == 422


def test_demand_is_served_per_day_so_the_console_can_draw_coverage():
    """Scheduled-versus-required is only honest if both sides come from the
    same place the DRAFT loop reads, rather than being recomputed in a browser."""
    client, _ = _client()
    body = client.get("/api/demand/site-or").json()
    assert body["site_id"] == "site-or"
    assert len(body["days"]) == 7
    first = body["days"][0]
    assert first["required_shift_hours"] > 0
    assert all(body["opens_at_hour"] <= int(h) < body["closes_at_hour"] for h in first["hours"])


def test_demand_for_an_unknown_site_is_404():
    client, _ = _client()
    assert client.get("/api/demand/site-nope").status_code == 404


def test_a_schedule_can_be_asked_for_by_week():
    """DRAFT writes a different week from the seeded one. Without this the
    console could only ever show the rota the demo started with, and a drafted
    week would be invisible in the screen built to display it."""
    client, state = _client()
    posted = state.world.posted_weeks("site-or")[0]
    body = client.get(f"/api/schedule/site-or?week={posted.isoformat()}").json()
    assert body["week_starts_at"] == posted.isoformat()
    assert body["shifts"]


def test_a_week_with_no_schedule_is_404_naming_the_week():
    client, _ = _client()
    response = client.get("/api/schedule/site-or?week=2030-01-07T00:00:00+00:00")
    assert response.status_code == 404
    assert "2030-01-07" in response.json()["detail"]


def _hold(rule="cost_over_budget", detail="$45.00 exceeds $0.00."):
    async def runner(state, disruption):
        return HoldRunResult(True, "int-1", rule, {"scope": "a"}, "?",
                             rule_hits=[{"rule": rule, "detail": detail}])
    return runner


def test_a_cover_decision_names_the_shift_it_is_about():
    """HOLD stops on covering one shift and has priced options behind it."""
    client, state = _client(hold_runner=_hold())
    shift = state.world.schedule("site-nyc", state.world.posted_weeks("site-nyc")[0]).shifts[0]
    client.post("/api/disruptions",
                json={"kind": "sick_call", "shift_id": shift.shift_id, "note": ""})
    pending = client.get("/api/decisions").json()[0]
    assert pending["kind"] == "cover"
    assert pending["subject"]["shift_id"] == shift.shift_id
    assert pending["subject"]["site_name"]


def test_a_posting_decision_is_not_dressed_up_as_a_cover():
    """DRAFT stops on posting a whole week: no worker, no per-option cost.

    Rendered through the cover-options table it showed an em dash for the worker,
    the rule's sentence in the money column, and "no consent needed" beside it -
    three claims about a cover that does not exist.
    """
    async def drafts(state, site_id):
        return HoldRunResult(True, "int-2", "understaffed_below_minimum", {"scope": "a"}, "?",
                             rule_hits=[{"rule": "understaffed_below_minimum",
                                         "detail": "The shift would run below the minimum."}])

    client, _ = _client(draft_runner=drafts)
    client.post("/api/draft/site-or")
    pending = client.get("/api/decisions").json()[0]
    assert pending["kind"] == "posting"
    assert pending["subject"]["site_id"] == "site-or"
    assert pending["subject"]["site_name"] == "Sable Pearl"
    assert "shift_id" not in pending["subject"]


def test_the_world_sends_certifications_and_standby_membership():
    """The People screen has columns for both, and the standby list is
    load-bearing: it is the Oregon-only carve-out that makes a cover free there
    and costs money everywhere else. Without these the page showed an em dash
    for every worker while claiming the carve-out exists."""
    client, _ = _client()
    workers = client.get("/api/world").json()["workers"]
    assert any(w["certifications"] for w in workers), "nobody is certified"
    on_standby = [w for w in workers if w["on_standby_list"]]
    assert on_standby, "nobody is on a standby list"
    assert all(w["site_id"] == "site-or" for w in on_standby), \
        "the standby carve-out exists only in Oregon"


# -- consent ----------------------------------------------------------------


def _ask(state, worker_id="w-or-1", shift_id="s-1"):
    from datetime import timedelta

    from muster.domain.types import ConsentKind, Money

    return state.consent.ask(
        worker_id=worker_id, shift_id=shift_id, kind=ConsentKind.REST_WAIVER,
        premium_owed=Money.from_dollars("100.00"),
        what_it_means="Muster is asking you to cover this.",
        asked_at=state.world.now(), expires_in=timedelta(hours=4),
    )


def test_an_answered_consent_ask_stays_on_the_list_with_what_was_said():
    """A decline is what stops Muster asking again, so it must remain visible.
    Serving only the outstanding asks lost the answer the moment it arrived."""
    client, state = _client()
    request = _ask(state)
    assert [c["request_id"] for c in client.get("/api/consent").json()] == [request.request_id]

    client.post(f"/api/consent/{request.request_id}/answer",
                json={"outcome": "declined", "channel": "console"})

    body = client.get("/api/consent").json()
    assert [c["request_id"] for c in body] == [request.request_id]
    assert body[0]["outcome"] == "declined"
    assert body[0]["answered_at"] is not None


def test_granting_consent_sends_muster_back_to_finish_the_cover():
    """The run that asked stopped at the ask. Once the worker has said yes, the
    cover it was asking about is the thing that still needs doing."""
    runs = []

    async def assigns(state, disruption):
        runs.append(disruption.shift_id)
        state.ledger.append({
            "kind": "assign_cover", "shift_id": disruption.shift_id,
            "worker_id": "w-or-1", "total_cents": 10_000,
        })
        return HoldRunResult(False, None, None, None, "assigned")

    client, state = _client(hold_runner=assigns)
    request = _ask(state, shift_id="s-99")

    body = client.post(f"/api/consent/{request.request_id}/answer",
                       json={"outcome": "granted", "channel": "console"}).json()
    assert runs == ["s-99"]
    assert body["status"] == "covered"


def test_declining_starts_nothing():
    runs = []

    async def assigns(state, disruption):
        runs.append(disruption.shift_id)
        return HoldRunResult(False, None, None, None, "assigned")

    client, state = _client(hold_runner=assigns)
    request = _ask(state, shift_id="s-99")

    body = client.post(f"/api/consent/{request.request_id}/answer",
                       json={"outcome": "declined", "channel": "console"}).json()
    assert runs == []
    assert body["status"] == "declined"


def test_a_grant_whose_run_pauses_again_lands_back_in_the_inbox():
    async def pauses(state, disruption):
        return HoldRunResult(
            True, "int-1", "$145.00 exceeds the conservative per-incident limit of $0.00.",
            {"messages": []}, "held",
            [{"rule": "cost_over_budget", "detail": "over budget"}],
        )

    client, state = _client(hold_runner=pauses)
    request = _ask(state, shift_id="s-99")

    body = client.post(f"/api/consent/{request.request_id}/answer",
                       json={"outcome": "granted", "channel": "console"}).json()
    assert body["status"] == "awaiting_decision"
    assert client.get("/api/decisions").json()[0]["decision_id"] == body["decision_id"]


def test_a_held_decision_names_the_worker_it_is_about():
    """The policy stops one call about one person. Until that was carried through,
    the console asked the operator to approve "$17.50" with an em dash where the
    name belongs — the rule and the money, and no answer to "for whom"."""
    async def pauses(state, disruption):
        return HoldRunResult(
            True, "int-1", "cost_over_budget",
            {"messages": []}, "held",
            [{"rule": "cost_over_budget", "detail": "$17.50 exceeds the limit of $0.00."}],
            {"tool": "assign_cover", "worker_id": "w-or-4", "shift_id": disruption.shift_id},
        )

    client, state = _client(hold_runner=pauses)
    client.post("/api/disruptions", json=DISRUPTION)

    held = client.get("/api/decisions").json()[0]
    assert held["proposal"]["worker_id"] == "w-or-4"
    assert held["proposal"]["worker_name"] == state.world.worker("w-or-4").name
    assert held["proposal"]["tool"] == "assign_cover"


def test_a_decision_with_no_proposal_behind_it_says_so_rather_than_guessing():
    async def pauses(state, disruption):
        return HoldRunResult(
            True, "int-1", "unassessable", {"messages": []}, "held",
            [{"rule": "unassessable", "detail": "cannot be judged"}],
        )

    client, _ = _client(hold_runner=pauses)
    client.post("/api/disruptions", json=DISRUPTION)
    assert client.get("/api/decisions").json()[0]["proposal"] is None


def test_declining_a_decision_never_reaches_the_agent():
    """Against the deployed service, a decline resumed the run and the SDK's own
    evaluate callback did not hold it: the cover was assigned, the worker was
    notified, and the receipt named the operator who had refused. A decline is
    enforced here now, not delegated."""
    resumed = []

    async def resumes(state, pending):
        resumed.append(pending.decision.decision_id)
        state.ledger.append({
            "kind": "assign_cover", "shift_id": pending.decision.offer_id,
            "worker_id": "w-or-1", "total_cents": 1750,
        })
        return HoldRunResult(False, None, None, None, "assigned")

    async def pauses(state, disruption):
        return HoldRunResult(
            True, "int-1", "cost_over_budget", {"messages": []}, "held",
            [{"rule": "cost_over_budget", "detail": "$17.50 exceeds the limit of $0.00."}],
            {"tool": "assign_cover", "worker_id": "w-or-1", "shift_id": disruption.shift_id},
        )

    client, state = _client(hold_runner=pauses, resumer=resumes)
    client.post("/api/disruptions", json=DISRUPTION)
    decision_id = client.get("/api/decisions").json()[0]["decision_id"]

    body = client.post(f"/api/decisions/{decision_id}/answer", json={
        "outcome": "decline", "by": "Smith", "role": "Operations manager",
        "note": "Not at that price.",
    }).json()

    assert body["status"] == "declined"
    assert resumed == [], "a declined decision must never be handed back to the agent"
    assert not [e for e in state.ledger if e["kind"] == "assign_cover"], "nothing may be assigned"
    assert state.receipts.all() == [], "and nothing may be receipted"
    assert client.get("/api/decisions").json() == []


def test_approving_a_decision_does_reach_the_agent():
    resumed = []

    async def resumes(state, pending):
        resumed.append(pending.decision.outcome.value)
        state.ledger.append({
            "kind": "assign_cover", "shift_id": pending.decision.offer_id,
            "worker_id": "w-or-1", "total_cents": 1750,
        })
        return HoldRunResult(False, None, None, None, "assigned")

    async def pauses(state, disruption):
        return HoldRunResult(
            True, "int-1", "cost_over_budget", {"messages": []}, "held",
            [{"rule": "cost_over_budget", "detail": "over"}],
        )

    client, _ = _client(hold_runner=pauses, resumer=resumes)
    client.post("/api/disruptions", json=DISRUPTION)
    decision_id = client.get("/api/decisions").json()[0]["decision_id"]

    body = client.post(f"/api/decisions/{decision_id}/answer", json={
        "outcome": "approve", "by": "Smith", "role": "Operations manager", "note": "",
    }).json()

    assert resumed == ["approve"]
    assert body["status"] == "covered"


def test_a_worker_who_declined_is_no_longer_offered_as_cover():
    """The policy consulted the consent store as well as the world, so the cover
    was blocked — but the enumerator reads only the world, so the person who had
    just refused went on being offered and priced for the shift they refused."""
    from datetime import datetime, timezone

    from muster.domain.options import enumerate_cover_options

    week = datetime(2026, 7, 27, tzinfo=timezone.utc)
    client, state = _client()
    schedule = state.world.schedule("site-nyc", week)
    gap = next(s for s in schedule.shifts if s.worker_id and s.starts_at >= week)
    offered = enumerate_cover_options(state.world, gap, at=state.world.now())
    subject = offered[0].worker_id

    request = _ask(state, worker_id=subject, shift_id=gap.shift_id)
    client.post(f"/api/consent/{request.request_id}/answer",
                json={"outcome": "declined", "channel": "console"})

    after = {o.worker_id for o in enumerate_cover_options(state.world, gap, at=state.world.now())}
    assert subject not in after
    assert state.world.has_declined(subject, gap.shift_id)


def test_a_reset_puts_the_world_back_without_a_redeploy():
    """Every run leaves marks — receipts, answered consent, a decision inbox. The
    only way to get a clean console back was to redeploy and wait, which is not
    something anyone can do between two takes of a recording."""
    async def assigns(state, disruption):
        state.ledger.append({
            "kind": "assign_cover", "shift_id": disruption.shift_id,
            "worker_id": "w-or-1", "total_cents": 1750, "site_id": "site-or",
        })
        return HoldRunResult(False, None, None, None, "assigned")

    client, state = _client(hold_runner=assigns)
    client.put("/api/autonomy", json={"level": "trusted"})
    client.post("/api/disruptions", json=DISRUPTION)
    _ask(client.app.state.muster)
    assert client.get("/api/consent").json()

    body = client.post("/api/demo/reset").json()
    assert body["status"] == "reset"
    assert client.get("/api/consent").json() == []
    assert client.get("/api/decisions").json() == []
    assert client.get("/api/receipts").json() == []
    # The dial is a presenter's setting, not run state: a reset keeps it.
    assert client.get("/api/autonomy").json()["level"] == "trusted"


def test_a_reset_leaves_the_seeded_postings_in_place():
    """A shift may only be touched if its week is posted, and the guard reads the
    ledger. A reset that forgot them would produce a console where nothing works."""
    client, _ = _client()
    client.post("/api/demo/reset")
    ledger = client.app.state.muster.ledger
    assert [e for e in ledger if e["kind"] == "post_schedule"]
