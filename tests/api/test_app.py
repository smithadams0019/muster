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
