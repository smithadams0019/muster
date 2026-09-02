"""Assembling and running the DRAFT agent.

Mirrors `loops/hold/runner.py`: the same two interventions, in the same order,
`checkpointing=False`, and a resume mechanism that loads a snapshot and feeds an
`interruptResponse` back in. PostingDependencyGuard still goes first even though
the DRAFT loop only exposes `post_schedule` as a dependency target - a refused
call must never reach a policy that would judge it on its own merits and find
nothing wrong.

Only `post_schedule` is guarded here. Proposing shifts and checking the draft are
free to iterate on, the way a human scheduler drafts and re-drafts before posting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from strands import Agent, Snapshot

from muster.adapters.base import WorldAdapter
from muster.domain.models import Shift
from muster.domain.types import AutonomyLevel
from muster.hooks.audit import AuditTrail
from muster.loops.draft.context import build_draft_context_provider
from muster.loops.draft.tools import build_draft_tools
from muster.policy.dependency import PostingDependencyGuard
from muster.policy.escalation import (
    EscalationPolicy,
    proposal_that_paused,
    rules_that_paused,
)

MODEL_ID = os.environ.get("MUSTER_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
REGION = os.environ.get("MUSTER_AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You are Muster, drafting next week's rota for a small coffee group.

Work in this order:
1. Call demand_for_week to see the hourly cover requirement for every day.
2. Call list_workers to see who is available, at what rate, with what
   certifications and good-faith hours.
3. Propose shifts with propose_shift until you believe the week is covered.
4. Call check_draft. It reports every problem still in the draft: uncovered
   hours, rest-period breaches, availability conflicts, workers left below their
   good-faith hours, and missing certified-handler or role-minimum coverage.
5. Fix every problem check_draft reports, then call check_draft again. Repeat
   until it returns an empty list.

   To fix a problem you may add a shift with propose_shift, or take one back out
   with remove_shift. Use list_draft to see what is currently in the draft and to
   find the shift_id you need. A rest breach or an overlap is almost always fixed
   by removing a shift rather than adding another one - if you proposed something
   you did not mean, remove it and propose the shift you did mean. The draft is
   not posted, so removing from it costs nothing and changes nobody's week.

   Never ask the operator to edit the draft for you. There is no admin panel;
   remove_shift is how a draft is corrected.
6. Call post_schedule.

Never invent a worker_id, a day, or an hour. Use only what demand_for_week and
list_workers returned. Do not guess at a rest breach or whether a certification
requirement is met - check_draft computes all of that from the real records.
"""


@dataclass
class DraftRunResult:
    paused: bool
    interrupt_id: str | None
    interrupt_reason: str | None
    snapshot: dict[str, Any] | None
    text: str
    rule_hits: list[dict[str, str]] = field(default_factory=list)
    #: The tool call the operator is being asked about, arguments and all,
    #: so the question can name who it is about.
    proposal: dict[str, Any] = field(default_factory=dict)


def build_default_policy(
    world: WorldAdapter,
    draft_state: dict[str, list[Shift]],
    week_starts_at: datetime,
    level: AutonomyLevel,
) -> EscalationPolicy:
    return EscalationPolicy(level, build_draft_context_provider(world, draft_state, week_starts_at))


def build_draft_agent(
    world: WorldAdapter,
    ledger: list[dict[str, Any]],
    week_starts_at: datetime,
    clock: Any,
    policy: EscalationPolicy,
    trail: AuditTrail,
    draft_state: dict[str, list[Shift]] | None = None,
) -> Agent:
    draft_state = {} if draft_state is None else draft_state
    return Agent(
        model=MODEL_ID,
        tools=build_draft_tools(world, ledger, week_starts_at, clock, draft_state=draft_state),
        interventions=[PostingDependencyGuard(ledger, trail), policy],
        hooks=[trail],
        system_prompt=SYSTEM_PROMPT,
        checkpointing=False,
        callback_handler=None,
    )


# strands 1.54 requires a preset or an explicit include list: calling
# take_snapshot() bare raises SnapshotException("No snapshot fields
# resolved"), which would 500 on every escalation - the one path that
# must never fail. "session" captures messages, state, conversation and
# interrupt state, which is exactly what a resume needs.
def _result_from(agent: Agent, raw: Any, policy: EscalationPolicy) -> DraftRunResult:
    interrupts = getattr(raw, "interrupts", None) or []
    if not interrupts:
        return DraftRunResult(False, None, None, None, str(raw))
    interrupt = interrupts[0]
    hits = rules_that_paused(raw, policy)
    return DraftRunResult(
        paused=True,
        interrupt_id=interrupt.id,
        interrupt_reason=hits[0].rule if hits else "unknown",
        snapshot=agent.take_snapshot(preset="session").__dict__,
        text=interrupt.reason or str(raw),
        rule_hits=[{"rule": h.rule, "detail": h.detail} for h in hits],
        proposal=proposal_that_paused(raw, policy),
    )


async def run_draft(agent: Agent, prompt: str, policy: EscalationPolicy) -> DraftRunResult:
    raw = await agent.invoke_async(prompt)
    return _result_from(agent, raw, policy)


async def resume_draft(
    agent: Agent,
    snapshot: dict[str, Any],
    interrupt_id: str,
    decision_record: dict[str, Any],
    policy: EscalationPolicy,
) -> DraftRunResult:
    """Resume a paused run with a human's structured decision."""
    agent.load_snapshot(Snapshot(**snapshot))
    raw = await agent.invoke_async(
        [{"interruptResponse": {"interruptId": interrupt_id, "response": decision_record}}]
    )
    return _result_from(agent, raw, policy)
