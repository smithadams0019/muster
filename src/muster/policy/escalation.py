"""The autonomy boundary, as a Strands intervention.

Runs before every consequential tool call and returns Proceed or Confirm. A Confirm
breaks the agent out of its loop so the run can be parked until a human answers.

Build one instance per run. `last_hits` and `escalations` are per-instance mutable
state that callers read after the run returns; two runs sharing a policy would
attribute one disruption's escalation reason to the other.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from strands import InterventionHandler
from strands.interventions.actions import Confirm, Proceed

from muster.domain.types import AutonomyLevel
from muster.policy.rules import CoverContext, RuleHit, evaluate

#: Tools that change somebody's week. Everything else is reading.
GUARDED_TOOLS: frozenset[str] = frozenset({
    "post_schedule", "assign_cover", "cancel_shift", "request_consent", "notify_worker",
})

UNASSESSABLE = "unassessable"

#: Responses that mean the operator said yes, as free text.
_APPROVING_WORDS = frozenset({"approve", "approved", "yes", "y", "true"})


def approves(response: Any) -> bool:
    """Whether a human's answer to a Confirm means "go ahead".

    Strands' `default_evaluate` accepts only `True` or the string "yes". Muster
    answers with a structured record instead - the outcome, who decided, their
    role and their note - because every one of those fields ends up on the
    receipt an investigator would read.

    Without this, that record evaluated as "not approved": the operator pressed
    Approve, the run resumed, the same tool call was refused again, the agent
    retried, and the policy raised an identical question. Approving produced a
    fresh copy of the question it was answering.
    """
    if isinstance(response, dict):
        # The API answers with "outcome"; the SDK's own examples use "decision".
        # Accept either rather than depending on which of the two a caller sends,
        # because getting it wrong does not fail loudly - it silently reads as a
        # refusal, and the operator's Approve turns into another identical
        # question. Only these two keys count: an unrecognised shape is a no.
        for key in ("outcome", "decision"):
            if key in response:
                return str(response[key]).strip().lower() in _APPROVING_WORDS
        return False
    if response is True:
        return True
    if isinstance(response, str):
        return response.strip().lower() in _APPROVING_WORDS
    return False


class EscalationPolicy(InterventionHandler):
    name = "muster-escalation"

    def __init__(
        self,
        level: AutonomyLevel,
        context_provider: Callable[[str, dict[str, Any]], CoverContext | None],
    ) -> None:
        self.level = level
        self.context_provider = context_provider
        self.last_hits: list[RuleHit] = []
        self.escalations: dict[str, list[RuleHit]] = {}

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        tool_name = event.tool_use["name"]
        if tool_name not in GUARDED_TOOLS:
            return Proceed(reason="tool changes nobody's week")

        context = self.context_provider(tool_name, event.tool_use.get("input", {}))
        if context is None:
            hits = [RuleHit(
                UNASSESSABLE,
                f"Muster cannot judge the effect of a {tool_name.replace('_', ' ')} "
                "here, so it will not make one unattended.",
            )]
        else:
            hits = evaluate(context, self.level)

        if not hits:
            self.last_hits = []
            return Proceed(reason=f"within the {self.level.value} limits")

        self.last_hits = hits
        self.escalations[event.tool_use.get("toolUseId", "")] = hits
        return Confirm(
            prompt=" ".join(hit.detail for hit in hits) + " Approve this?",
            reason=hits[0].rule,
            evaluate=approves,
        )


def rules_that_paused(result: Any, policy: EscalationPolicy) -> list[RuleHit]:
    """The hits belonging to the interrupt that actually stopped this run.

    Read from `escalations` by tool-use id rather than from `last_hits`, because a
    run can clear a guard on one call and pause on a later one, and `last_hits`
    would by then describe the wrong call.
    """
    interrupts = getattr(result, "interrupts", None) or []
    for interrupt in interrupts:
        # Interrupt.id looks like
        #   "v1:before_tool_call:tooluse_R0kIpR...:b174861a-..."
        # so the tool-use id the policy keyed on is embedded rather than exposed
        # as its own attribute. Match on containment rather than equality, and
        # never invent an attribute name the SDK does not have.
        for tool_use_id, hits in policy.escalations.items():
            if tool_use_id and tool_use_id in str(interrupt.id):
                return hits
    return policy.last_hits
