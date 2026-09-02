"""Where a paused run waits for a human.

When the escalation policy stops a run, the snapshot and interrupt id are parked
here alongside the question. A human answers; the orchestrator uses the stored
snapshot to resume the very same run.

In memory, deliberately: this build has no durable store, and pretending otherwise
would be worse than saying so. Restart the process and every pending decision, and
the snapshot needed to resume its run, is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from muster.domain.types import DecisionOutcome


@dataclass(frozen=True)
class Decision:
    decision_id: str
    offer_id: str
    rule: str
    prompt: str
    outcome: DecisionOutcome | None = None
    by: str = ""
    role: str = ""
    note: str = ""
    at: datetime | None = None

    def answer(self, outcome: DecisionOutcome, *, by: str, role: str, note: str = "") -> Decision:
        return Decision(
            decision_id=self.decision_id, offer_id=self.offer_id, rule=self.rule,
            prompt=self.prompt, outcome=outcome, by=by, role=role, note=note,
            at=datetime.now(timezone.utc),
        )


@dataclass
class PendingDecision:
    decision: Decision
    interrupt_id: str
    snapshot: dict[str, Any]
    rule_hits: list[dict[str, str]] = field(default_factory=list)
    #: The guarded call this run stopped on: which tool, and its arguments.
    proposal: dict[str, Any] = field(default_factory=dict)


class DecisionInbox:
    def __init__(self) -> None:
        self._pending: dict[str, PendingDecision] = {}
        self._answered: list[PendingDecision] = []

    def open(
        self,
        decision: Decision,
        *,
        interrupt_id: str,
        snapshot: dict[str, Any],
        rule_hits: list[dict[str, str]],
        proposal: dict[str, Any] | None = None,
    ) -> str:
        """Park an escalation and return its id.

        `snapshot` and `rule_hits` are copied on the way in, so a caller that mutates
        its own dict afterwards cannot silently corrupt the parked state. Re-opening
        an id that is still pending raises: it would discard the earlier snapshot and
        interrupt id, which is exactly the failure this inbox exists to prevent.
        """
        if decision.decision_id in self._pending:
            raise KeyError(f"decision {decision.decision_id!r} is already pending")
        self._pending[decision.decision_id] = PendingDecision(
            decision=decision,
            interrupt_id=interrupt_id,
            snapshot=dict(snapshot),
            rule_hits=[dict(h) for h in rule_hits],
            proposal=dict(proposal or {}),
        )
        return decision.decision_id

    def pending(self) -> list[PendingDecision]:
        return list(self._pending.values())

    def answered(self) -> list[PendingDecision]:
        return list(self._answered)

    def get(self, decision_id: str) -> PendingDecision | None:
        return self._pending.get(decision_id)

    def answer(
        self, decision_id: str, outcome: DecisionOutcome, *, by: str, role: str, note: str = ""
    ) -> PendingDecision:
        if decision_id not in self._pending:
            raise KeyError(f"no pending decision {decision_id!r}")
        pending = self._pending.pop(decision_id)
        pending.decision = pending.decision.answer(outcome, by=by, role=role, note=note)
        self._answered.append(pending)
        return pending
