"""What the escalation policy judges when the DRAFT loop calls `post_schedule`.

Every other DRAFT tool is unguarded: proposing a shift and checking a draft change
nothing outside the agent's own scratch space. Only `post_schedule` moves
something into the world, and posting inside the notice window is free - it is the
changes made to a posted schedule afterwards that the ordinances price, not the
first posting of it. What the policy needs to judge instead is whether the draft
itself is fit to post: whether it leaves a shift without a certified handler or
below a role minimum. That comes from the same `check_draft_problems` the agent
already saw through the `check_draft` tool, so the two can never disagree.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from muster.adapters.base import WorldAdapter
from muster.domain.models import Shift
from muster.domain.types import Money
from muster.loops.draft.tools import check_draft_problems
from muster.policy.escalation import GUARDED_TOOLS
from muster.policy.rules import CoverContext


def build_draft_context_provider(
    world: WorldAdapter,
    draft_state: dict[str, list[Shift]],
    week_starts_at: datetime,
) -> Callable[[str, dict[str, Any]], CoverContext | None]:
    """Build the DRAFT loop's `context_provider` for `EscalationPolicy`.

    Returns `None` for every tool but `post_schedule` - there is nothing else in
    the DRAFT loop for the policy to judge - and `None` again when `post_schedule`
    names a site that does not exist. `None` always means "unassessable", which
    the policy turns into an escalation; it never means "fine".
    """

    def provide(tool_name: str, args: dict[str, Any]) -> CoverContext | None:
        if tool_name not in GUARDED_TOOLS or tool_name != "post_schedule":
            return None

        site_id = args.get("site_id")
        site = world.site(site_id) if site_id else None
        if site is None:
            return None

        problems = check_draft_problems(world, draft_state, site_id, week_starts_at)
        meets_certification_minimum = not any(
            p["kind"] == "no_certified_handler" for p in problems
        )
        meets_role_minimum = not any(p["kind"] == "role_minimum" for p in problems)

        return CoverContext(
            cost=Money.zero(),
            week_spend=Money.zero(),
            overtime_hours=0.0,
            shortfall_fraction=0.0,
            requires_rest_waiver=False,
            worker_declined=False,
            meets_role_minimum=meets_role_minimum,
            meets_certification_minimum=meets_certification_minimum,
            assessable=True,
        )

    return provide
