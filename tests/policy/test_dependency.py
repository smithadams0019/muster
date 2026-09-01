from types import SimpleNamespace

from strands.interventions.actions import Deny, Proceed

from muster.policy.dependency import PostingDependencyGuard


class FakeTrail:
    def __init__(self):
        self.records = []

    def record(self, kind, label, detail):
        self.records.append((kind, label, detail))


def _event(name, **args):
    return SimpleNamespace(tool_use={"name": name, "input": args, "toolUseId": "tu-1"})


def test_notifying_a_worker_about_an_unapproved_cover_is_denied():
    guard = PostingDependencyGuard(ledger=[], trail=FakeTrail())
    action = guard.before_tool_call(_event("notify_worker", shift_id="s-1", worker_id="w-1"))
    assert isinstance(action, Deny)
    assert "no approved cover" in action.reason


def test_notifying_is_allowed_once_the_ledger_records_the_cover():
    ledger = [{"kind": "assign_cover", "shift_id": "s-1", "worker_id": "w-1"}]
    guard = PostingDependencyGuard(ledger=ledger, trail=FakeTrail())
    action = guard.before_tool_call(_event("notify_worker", shift_id="s-1", worker_id="w-1"))
    assert isinstance(action, Proceed)


def test_a_cover_recorded_for_a_different_worker_does_not_authorise_this_one():
    ledger = [{"kind": "assign_cover", "shift_id": "s-1", "worker_id": "w-9"}]
    guard = PostingDependencyGuard(ledger=ledger, trail=FakeTrail())
    assert isinstance(guard.before_tool_call(
        _event("notify_worker", shift_id="s-1", worker_id="w-1")), Deny)


def test_assigning_a_cover_on_an_unposted_schedule_is_denied():
    guard = PostingDependencyGuard(ledger=[], trail=FakeTrail())
    action = guard.before_tool_call(_event("assign_cover", shift_id="s-1", worker_id="w-1"))
    assert isinstance(action, Deny)
    assert "never posted" in action.reason


def test_assigning_is_allowed_once_the_schedule_is_posted():
    ledger = [{"kind": "post_schedule", "site_id": "site-or", "shift_ids": ["s-1"]}]
    guard = PostingDependencyGuard(ledger=ledger, trail=FakeTrail())
    assert isinstance(guard.before_tool_call(
        _event("assign_cover", shift_id="s-1", worker_id="w-1")), Proceed)


def test_posting_itself_is_never_blocked_by_this_guard():
    guard = PostingDependencyGuard(ledger=[], trail=FakeTrail())
    assert isinstance(guard.before_tool_call(_event("post_schedule", site_id="site-or")), Proceed)


def test_a_denial_is_written_to_the_trail_so_the_refusal_is_explainable():
    trail = FakeTrail()
    guard = PostingDependencyGuard(ledger=[], trail=trail)
    guard.before_tool_call(_event("notify_worker", shift_id="s-1", worker_id="w-1"))
    assert trail.records and trail.records[0][0] == "refusal"
