import pytest

from muster.domain.types import DecisionOutcome
from muster.persistence.inbox import Decision, DecisionInbox


def _decision(decision_id="dec-1"):
    return Decision(decision_id=decision_id, offer_id="off-1",
                    rule="cost_over_budget", prompt="Approve?")


def test_an_opened_decision_is_pending_with_its_snapshot():
    inbox = DecisionInbox()
    inbox.open(_decision(), interrupt_id="int-1", snapshot={"scope": "agent"}, rule_hits=[])
    assert inbox.get("dec-1").interrupt_id == "int-1"
    assert inbox.get("dec-1").snapshot == {"scope": "agent"}


def test_the_snapshot_is_copied_so_a_later_mutation_cannot_corrupt_it():
    inbox = DecisionInbox()
    snapshot = {"scope": "agent"}
    inbox.open(_decision(), interrupt_id="int-1", snapshot=snapshot, rule_hits=[])
    snapshot["scope"] = "tampered"
    assert inbox.get("dec-1").snapshot == {"scope": "agent"}


def test_reopening_a_pending_id_raises_rather_than_discarding_the_snapshot():
    inbox = DecisionInbox()
    inbox.open(_decision(), interrupt_id="int-1", snapshot={}, rule_hits=[])
    with pytest.raises(KeyError, match="already pending"):
        inbox.open(_decision(), interrupt_id="int-2", snapshot={}, rule_hits=[])


def test_answering_records_the_human_and_clears_the_queue():
    inbox = DecisionInbox()
    inbox.open(_decision(), interrupt_id="int-1", snapshot={}, rule_hits=[])
    answered = inbox.answer("dec-1", DecisionOutcome.APPROVE, by="Roger K", role="manager")
    assert answered.decision.outcome is DecisionOutcome.APPROVE
    assert answered.decision.by == "Roger K"
    assert answered.decision.at is not None
    assert inbox.pending() == []
    assert len(inbox.answered()) == 1


def test_answering_an_unknown_decision_raises():
    with pytest.raises(KeyError, match="nope"):
        DecisionInbox().answer("nope", DecisionOutcome.APPROVE, by="a", role="b")


def test_an_answered_id_can_be_reopened_as_a_fresh_escalation():
    """A resumed run that pauses again is a new escalation, not a corruption."""
    inbox = DecisionInbox()
    inbox.open(_decision(), interrupt_id="int-1", snapshot={}, rule_hits=[])
    inbox.answer("dec-1", DecisionOutcome.APPROVE, by="a", role="b")
    inbox.open(_decision(), interrupt_id="int-2", snapshot={}, rule_hits=[])
    assert inbox.get("dec-1").interrupt_id == "int-2"
