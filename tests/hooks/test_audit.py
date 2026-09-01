from types import SimpleNamespace

from muster.hooks.audit import AuditTrail


def test_it_records_a_tool_call_with_its_arguments():
    trail = AuditTrail()
    trail._on_tool(SimpleNamespace(tool_use={"name": "assign_cover", "input": {"shift_id": "s-1"}}))
    entry = trail.entries()[0]
    assert entry.kind == "tool_call"
    assert entry.label == "assign_cover"
    assert entry.detail == {"shift_id": "s-1"}


def test_arguments_are_copied_so_a_later_mutation_cannot_rewrite_history():
    trail = AuditTrail()
    args = {"shift_id": "s-1"}
    trail._on_tool(SimpleNamespace(tool_use={"name": "assign_cover", "input": args}))
    args["shift_id"] = "s-999"
    assert trail.entries()[0].detail == {"shift_id": "s-1"}


def test_entries_come_back_in_the_order_they_happened():
    trail = AuditTrail()
    trail.record("offer", "first")
    trail.record("offer", "second")
    assert [e.label for e in trail.entries()] == ["first", "second"]


def test_the_caller_cannot_mutate_the_trail_through_the_list_it_gets_back():
    trail = AuditTrail()
    trail.record("offer", "first")
    trail.entries().clear()
    assert len(trail.entries()) == 1
