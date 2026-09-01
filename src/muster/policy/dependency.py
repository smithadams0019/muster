"""Nothing acts on a cover that was never approved.

The escalation policy judges each tool call on its own merits, which is right, and
insufficient: a held cover followed by a notification is two calls, each defensible
alone, that together tell a worker to come in for a shift nobody approved. This
guard consults the ledger - the record of what actually happened - rather than the
agent's account of what it did.

Ordered before the escalation policy in the interventions list, because its Deny
short-circuits: a refused call must never reach a policy that would find nothing
wrong with it in isolation.
"""

from __future__ import annotations

from typing import Any

from strands import InterventionHandler
from strands.interventions.actions import Deny, Proceed

_NEEDS_APPROVED_COVER = frozenset({"notify_worker"})
_NEEDS_POSTED_SCHEDULE = frozenset({"assign_cover", "cancel_shift"})


class PostingDependencyGuard(InterventionHandler):
    name = "muster-dependency"

    def __init__(self, ledger: list[dict[str, Any]], trail: Any) -> None:
        self.ledger = ledger
        self.trail = trail

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        tool_name = event.tool_use["name"]
        args = event.tool_use.get("input", {})

        if tool_name in _NEEDS_APPROVED_COVER:
            if not self._cover_approved(args.get("shift_id"), args.get("worker_id")):
                return self._deny(
                    tool_name,
                    f"no approved cover for shift {args.get('shift_id')!r} and worker "
                    f"{args.get('worker_id')!r}; nobody may be told to come in.",
                )

        if tool_name in _NEEDS_POSTED_SCHEDULE:
            if not self._schedule_posted(args.get("shift_id")):
                return self._deny(
                    tool_name,
                    f"shift {args.get('shift_id')!r} belongs to a schedule that was "
                    "never posted, so there is nothing to change.",
                )

        return Proceed(reason="its prerequisite is in the ledger")

    def _cover_approved(self, shift_id: str | None, worker_id: str | None) -> bool:
        return any(
            e.get("kind") == "assign_cover"
            and e.get("shift_id") == shift_id
            and e.get("worker_id") == worker_id
            for e in self.ledger
        )

    def _schedule_posted(self, shift_id: str | None) -> bool:
        return any(
            e.get("kind") == "post_schedule" and shift_id in (e.get("shift_ids") or [])
            for e in self.ledger
        )

    def _deny(self, tool_name: str, reason: str) -> Deny:
        self.trail.record("refusal", f"refused {tool_name}", {"reason": reason})
        return Deny(reason=reason)
