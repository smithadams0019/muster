from types import SimpleNamespace

import pytest
from strands.interventions.actions import Confirm, Proceed

from muster.domain.types import AutonomyLevel, Money
from muster.policy.escalation import GUARDED_TOOLS, EscalationPolicy
from muster.policy.rules import CoverContext


def _event(tool_name, **args):
    return SimpleNamespace(tool_use={"name": tool_name, "input": args, "toolUseId": "tu-1"})


def _ctx(**overrides):
    base = dict(
        cost=Money.zero(), week_spend=Money.zero(), overtime_hours=0.0,
        shortfall_fraction=0.0, requires_rest_waiver=False, worker_declined=False,
        meets_role_minimum=True, meets_certification_minimum=True, assessable=True,
    )
    return CoverContext(**{**base, **overrides})


def test_an_unguarded_tool_always_proceeds():
    policy = EscalationPolicy(AutonomyLevel.CONSERVATIVE, lambda name, args: _ctx())
    assert isinstance(policy.before_tool_call(_event("list_workers")), Proceed)


def test_the_guarded_tools_are_the_ones_that_change_someones_week():
    assert GUARDED_TOOLS == frozenset({
        "post_schedule", "assign_cover", "cancel_shift", "request_consent", "notify_worker",
    })


def test_a_free_cover_proceeds():
    policy = EscalationPolicy(AutonomyLevel.BALANCED, lambda name, args: _ctx())
    assert isinstance(policy.before_tool_call(_event("assign_cover")), Proceed)


def test_an_expensive_cover_confirms_and_names_the_rule_in_plain_english():
    policy = EscalationPolicy(
        AutonomyLevel.BALANCED, lambda name, args: _ctx(cost=Money.from_dollars("120.00"))
    )
    action = policy.before_tool_call(_event("assign_cover"))
    assert isinstance(action, Confirm)
    assert "$120.00" in action.prompt
    assert [h.rule for h in policy.last_hits] == ["cost_over_budget"]


def test_a_context_the_provider_cannot_build_confirms_rather_than_proceeding():
    policy = EscalationPolicy(AutonomyLevel.TRUSTED, lambda name, args: None)
    action = policy.before_tool_call(_event("assign_cover"))
    assert isinstance(action, Confirm)
    assert policy.last_hits[0].rule == "unassessable"


def test_hits_are_kept_per_tool_use_so_a_later_call_cannot_overwrite_the_pause():
    policy = EscalationPolicy(
        AutonomyLevel.BALANCED, lambda name, args: _ctx(cost=Money.from_dollars("99.00"))
    )
    policy.before_tool_call(_event("assign_cover"))
    assert "tu-1" in policy.escalations
    assert policy.escalations["tu-1"][0].rule == "cost_over_budget"


def test_a_clean_call_clears_the_last_hits():
    contexts = iter([_ctx(cost=Money.from_dollars("99.00")), _ctx()])
    policy = EscalationPolicy(AutonomyLevel.BALANCED, lambda name, args: next(contexts))
    policy.before_tool_call(_event("assign_cover"))
    policy.before_tool_call(_event("assign_cover"))
    assert policy.last_hits == []


def test_before_tool_call_is_defined_on_the_class_not_the_instance():
    """Strands inspects the class; an instance attribute silently disables the guard."""
    assert "before_tool_call" in EscalationPolicy.__dict__


def test_a_structured_decision_record_counts_as_approval():
    """Strands' default evaluator accepts only True or "yes".

    Muster answers with a record - outcome, who, role, note - because all four
    end up on the receipt. Before this, that record read as "not approved": the
    operator pressed Approve, the run resumed, the same call was refused again,
    and the policy asked an identical question. Approving cloned the question.
    """
    from muster.policy.escalation import approves

    assert approves({"outcome": "approve", "by": "Roger K", "role": "operator"}) is True
    assert approves({"outcome": "decline", "by": "Roger K"}) is False
    assert approves({"decision": "approve", "by": "Roger K", "role": "operator"}) is True
    assert approves({"decision": "APPROVE "}) is True
    assert approves({"decision": "decline", "by": "Roger K"}) is False
    assert approves({"by": "Roger K"}) is False          # no outcome is not approval
    assert approves(True) is True
    assert approves("yes") is True
    assert approves("no") is False
    assert approves(None) is False


def test_the_confirm_carries_musters_evaluator_not_the_sdk_default():
    from muster.policy.escalation import approves

    policy = EscalationPolicy(
        AutonomyLevel.BALANCED, lambda name, args: _ctx(cost=Money.from_dollars("120.00"))
    )
    action = policy.before_tool_call(_event("assign_cover"))
    assert action.evaluate is approves


def _tagged(tool_name, tool_use_id, **args):
    return SimpleNamespace(
        tool_use={"name": tool_name, "input": args, "toolUseId": tool_use_id},
    )


def test_the_policy_records_the_call_it_stopped_not_only_the_reason():
    """So the question put to the operator can name who it is about."""
    from muster.policy.escalation import proposal_that_paused

    policy = EscalationPolicy(
        AutonomyLevel.CONSERVATIVE, lambda name, args: _ctx(cost=Money.from_dollars("17.50")),
    )
    policy.before_tool_call(
        _tagged("assign_cover", "tu-9", worker_id="w-or-4", shift_id="s-1", option_id="opt-1"),
    )

    result = SimpleNamespace(interrupts=[SimpleNamespace(id="v1:before_tool_call:tu-9:abc")])
    proposal = proposal_that_paused(result, policy)
    assert proposal["tool"] == "assign_cover"
    assert proposal["worker_id"] == "w-or-4"


def test_a_run_that_cleared_one_guard_and_paused_on_another_reports_the_second():
    """`last_hits` would by then describe the wrong call, and so would its args."""
    from muster.policy.escalation import proposal_that_paused

    answers = iter([_ctx(), _ctx(cost=Money.from_dollars("17.50"))])
    policy = EscalationPolicy(AutonomyLevel.CONSERVATIVE, lambda name, args: next(answers))
    policy.before_tool_call(_tagged("assign_cover", "tu-1", worker_id="w-or-1"))
    policy.before_tool_call(_tagged("assign_cover", "tu-2", worker_id="w-or-2"))

    result = SimpleNamespace(interrupts=[SimpleNamespace(id="v1:before_tool_call:tu-2:abc")])
    assert proposal_that_paused(result, policy)["worker_id"] == "w-or-2"
