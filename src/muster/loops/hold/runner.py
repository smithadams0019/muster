"""Assembling and running the HOLD agent.

Two interventions, in this order. PostingDependencyGuard goes first because its
Deny short-circuits: a notification for a cover that was never approved must be
refused outright and never reach the escalation policy, which would judge it on its
own merits, find nothing wrong, and let a worker be told to come in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from strands import Agent, Snapshot

from muster.adapters.base import WorldAdapter
from muster.domain.models import Disruption
from muster.domain.types import AutonomyLevel
from muster.hooks.audit import AuditTrail
from muster.loops.hold.context import build_hold_context_provider
from muster.loops.hold.tools import build_hold_tools
from muster.persistence.consent import ConsentStore
from muster.persistence.receipts import ReceiptBook
from muster.policy.dependency import PostingDependencyGuard
from muster.policy.escalation import EscalationPolicy, rules_that_paused

MODEL_ID = os.environ.get("MUSTER_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
REGION = os.environ.get("MUSTER_AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You are Muster, a shift coordinator for a small coffee group.

A shift has lost its worker. Your job is to cover it lawfully and cheaply.

Work in this order:
1. Call list_cover_options. It returns every lawful cover, already priced, cheapest
   first. The prices are computed from the governing city's ordinance; do not
   recompute them and do not estimate.
2. Take the cheapest option that does not require someone's consent. Call
   assign_cover with its option_id.
3. If the only options require consent, call request_consent and stop there. You may
   never decide on a worker's behalf that they will work inside their rest period.
4. After a cover is assigned, call notify_worker.

Never ask a worker who has already declined this shift.
Never invent an option_id, worker_id or shift_id. Use only what the tools returned.
"""


@dataclass
class HoldRunResult:
    paused: bool
    interrupt_id: str | None
    interrupt_reason: str | None
    snapshot: dict[str, Any] | None
    text: str
    rule_hits: list[dict[str, str]] = field(default_factory=list)


def build_default_policy(
    world: WorldAdapter,
    ledger: list[dict[str, Any]],
    consent: ConsentStore,
    level: AutonomyLevel,
) -> EscalationPolicy:
    return EscalationPolicy(level, build_hold_context_provider(world, ledger, consent, level))


def build_hold_agent(
    world: WorldAdapter,
    ledger: list[dict[str, Any]],
    receipts: ReceiptBook,
    consent: ConsentStore,
    policy: EscalationPolicy,
    trail: AuditTrail,
    decided_by: str = "muster",
) -> Agent:
    return Agent(
        model=MODEL_ID,
        tools=build_hold_tools(world, ledger, receipts, consent, clock=world.now,
                               decided_by=decided_by),
        interventions=[PostingDependencyGuard(ledger, trail), policy],
        hooks=[trail],
        system_prompt=SYSTEM_PROMPT,
        checkpointing=False,
        callback_handler=None,
    )


def describe_disruption(world: WorldAdapter, disruption: Disruption) -> str:
    shift = world.shift(disruption.shift_id)
    site = world.site(shift.site_id) if shift else None
    worker = world.worker(shift.worker_id) if shift and shift.worker_id else None
    return (
        f"{disruption.kind.value.replace('_', ' ').title()} at {site.name if site else 'a site'}. "
        f"{worker.name if worker else 'A worker'} cannot work shift {disruption.shift_id}, "
        f"which runs {shift.starts_at:%A %H:%M} to {shift.ends_at:%H:%M}. "
        f"Note: {disruption.note or 'none'}. Cover it."
    )


# strands 1.54 requires a preset or an explicit include list: calling
# take_snapshot() bare raises SnapshotException("No snapshot fields
# resolved"), which would 500 on every escalation - the one path that
# must never fail. "session" captures messages, state, conversation and
# interrupt state, which is exactly what a resume needs.
def _result_from(agent: Agent, raw: Any, policy: EscalationPolicy) -> HoldRunResult:
    """Build a result, reading the interrupt's real fields rather than guessing.

    `strands.interrupt.Interrupt` carries `id`, `name`, `reason` and `response`.
    An earlier version reached for `interrupt_id` and `prompt` through
    `getattr(..., default)`, which meant a wrong attribute name produced a
    cheerful `None` instead of an error - and the resume then failed hours later
    with `interrupt_id=<None> | no interrupt found`, long after the human had
    answered and the decision had been consumed. Read the attributes directly so
    a future SDK change breaks here, loudly, instead of there, silently.
    """
    interrupts = getattr(raw, "interrupts", None) or []
    if not interrupts:
        return HoldRunResult(False, None, None, None, str(raw))
    interrupt = interrupts[0]
    hits = rules_that_paused(raw, policy)
    return HoldRunResult(
        paused=True,
        interrupt_id=interrupt.id,
        interrupt_reason=hits[0].rule if hits else "unknown",
        snapshot=agent.take_snapshot(preset="session").__dict__,
        text=interrupt.reason or str(raw),
        rule_hits=[{"rule": h.rule, "detail": h.detail} for h in hits],
    )


async def run_hold(agent: Agent, prompt: str, policy: EscalationPolicy) -> HoldRunResult:
    raw = await agent.invoke_async(prompt)
    return _result_from(agent, raw, policy)


async def resume_hold(
    agent: Agent,
    snapshot: dict[str, Any],
    interrupt_id: str,
    decision_record: dict[str, Any],
    policy: EscalationPolicy,
) -> HoldRunResult:
    """Resume a paused run with a human's structured decision."""
    agent.load_snapshot(Snapshot(**snapshot))
    raw = await agent.invoke_async(
        [{"interruptResponse": {"interruptId": interrupt_id, "response": decision_record}}]
    )
    return _result_from(agent, raw, policy)
