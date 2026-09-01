from datetime import datetime, timezone

import pytest
from strands import Agent

from muster.adapters.simulated import SableCoffee
from muster.domain.types import AutonomyLevel
from muster.loops.hold.runner import (
    build_default_policy, build_hold_agent, describe_disruption,
)
from muster.persistence.consent import ConsentStore
from muster.persistence.receipts import ReceiptBook
from muster.hooks.audit import AuditTrail


def _agent():
    world = SableCoffee()
    ledger: list[dict] = []
    policy = build_default_policy(world, ledger, ConsentStore(), AutonomyLevel.BALANCED)
    trail = AuditTrail()
    return build_hold_agent(world, ledger, ReceiptBook(), ConsentStore(), policy, trail)


def test_the_agent_is_built_with_checkpointing_off():
    """checkpointing=True stops the run before the tool call and returns no interrupts.

    strands-agents==1.54.0 keeps this on a private field; there is no public
    ``Agent.checkpointing`` to read.
    """
    agent = _agent()
    assert agent._checkpointing is False


def test_the_dependency_guard_runs_before_the_escalation_policy():
    """A Deny must short-circuit; a policy that sees the call first would allow it.

    strands-agents==1.54.0 exposes registered handlers through
    ``Agent._intervention_registry.handlers``, not a public ``Agent.interventions``.
    """
    agent = _agent()
    names = [type(i).__name__ for i in agent._intervention_registry.handlers]
    assert names.index("PostingDependencyGuard") < names.index("EscalationPolicy")


def test_the_prompt_describes_the_disruption_in_the_operators_language():
    world = SableCoffee()
    from muster.domain.models import Disruption
    from muster.domain.types import DisruptionKind
    disruption = Disruption(disruption_id="d-1", kind=DisruptionKind.SICK_CALL,
                            shift_id=next(iter(world.schedule("site-or",
                                datetime(2026, 7, 27, tzinfo=timezone.utc)).shifts)).shift_id,
                            reported_at=world.now(), note="flu")
    prompt = describe_disruption(world, disruption)
    assert "sick" in prompt.lower()
    assert "site" in prompt.lower() or "Sable" in prompt


@pytest.mark.integration
async def test_a_free_standby_cover_is_taken_without_a_human():
    """Billed. Proves the whole loop end to end against live Bedrock."""
    from muster.loops.hold.runner import run_hold
    world = SableCoffee()
    ledger: list[dict] = []
    consent = ConsentStore()
    policy = build_default_policy(world, ledger, consent, AutonomyLevel.BALANCED)
    agent = build_hold_agent(world, ledger, ReceiptBook(), consent, policy, AuditTrail())
    shift = next(s for s in world.schedule(
                     "site-or", datetime(2026, 7, 27, tzinfo=timezone.utc)).shifts
                 if s.starts_at.hour == 7)
    standby = next(w for w in world.workers("site-or") if w.on_standby_list)
    world.record_standby_acceptance(standby.worker_id, shift.shift_id)
    result = await run_hold(agent, f"{standby.name} is on standby. Cover shift {shift.shift_id}.",
                            policy)
    assert result.paused is False
    assert any(e["kind"] == "assign_cover" for e in ledger)
