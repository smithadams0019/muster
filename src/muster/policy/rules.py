"""Where Muster's authority ends, as executable code.

The dial moves four numbers. Two rules ignore it entirely, and that is the law's
structure rather than a product opinion: Oregon requires the worker's request or
consent before a rest period is shortened, NYC requires written consent for a
clopening, and Chicago's own guidance says the Right to Rest has no exceptions. An
agent that could waive a rest period on a worker's behalf would not be a more
capable product; it would be an unlawful one.

Thresholds compare with strict inequality, so a value exactly at a limit is
autonomous-safe: $75.00 goes through at balanced, $75.01 does not.
"""

from __future__ import annotations

from dataclasses import dataclass

from muster.domain.types import AutonomyLevel, Money


@dataclass(frozen=True)
class Thresholds:
    max_unattended_cents: int
    weekly_budget_cents: int
    max_overtime_hours: float
    max_shortfall_fraction: float


THRESHOLDS: dict[AutonomyLevel, Thresholds] = {
    AutonomyLevel.CONSERVATIVE: Thresholds(0, 0, 0.0, 0.0),
    AutonomyLevel.BALANCED: Thresholds(7_500, 40_000, 2.0, 0.10),
    AutonomyLevel.TRUSTED: Thresholds(25_000, 150_000, 6.0, 0.20),
}

#: Fire at every level. No setting loosens either.
NON_NEGOTIABLE_RULES: frozenset[str] = frozenset({"rest_waiver_required", "worker_declined"})


@dataclass(frozen=True)
class RuleHit:
    rule: str
    detail: str


@dataclass(frozen=True)
class CoverContext:
    """Everything the policy needs to judge one proposed cover."""

    cost: Money
    week_spend: Money
    overtime_hours: float
    shortfall_fraction: float
    requires_rest_waiver: bool
    worker_declined: bool
    meets_role_minimum: bool
    meets_certification_minimum: bool
    assessable: bool


def evaluate(context: CoverContext, level: AutonomyLevel) -> list[RuleHit]:
    """Every rule this cover trips at this autonomy level."""
    if not context.assessable:
        return [RuleHit("unassessable",
                        "Muster cannot resolve the rulebook, rate or worker for this "
                        "cover, so it will not make one unattended.")]

    limits = THRESHOLDS[level]
    hits: list[RuleHit] = []

    if context.requires_rest_waiver:
        hits.append(RuleHit(
            "rest_waiver_required",
            "This cover starts inside the worker's protected rest period. Only the "
            "worker can agree to that, and no autonomy level changes it.",
        ))
    if context.worker_declined:
        hits.append(RuleHit(
            "worker_declined",
            "This worker has already declined this shift. Muster does not ask twice.",
        ))
    if context.cost.cents > limits.max_unattended_cents:
        hits.append(RuleHit(
            "cost_over_budget",
            f"{context.cost} exceeds the {level.value} per-incident limit of "
            f"{Money(cents=limits.max_unattended_cents)}.",
        ))
    if (context.week_spend + context.cost).cents > limits.weekly_budget_cents:
        hits.append(RuleHit(
            "weekly_budget_exhausted",
            f"{context.week_spend + context.cost} of premium this week exceeds the "
            f"{level.value} weekly limit of {Money(cents=limits.weekly_budget_cents)}.",
        ))
    if context.overtime_hours > limits.max_overtime_hours:
        hits.append(RuleHit(
            "overtime_threshold",
            f"Adds {context.overtime_hours:.1f}h of overtime; {level.value} allows "
            f"{limits.max_overtime_hours:.1f}h.",
        ))
    if context.shortfall_fraction > limits.max_shortfall_fraction:
        hits.append(RuleHit(
            "hours_shortfall",
            f"Leaves a worker {context.shortfall_fraction:.0%} below their good-faith "
            f"hours; {level.value} allows {limits.max_shortfall_fraction:.0%}.",
        ))
    if not context.meets_role_minimum or not context.meets_certification_minimum:
        hits.append(RuleHit(
            "understaffed_below_minimum",
            "The shift would run below the site's role or certification minimum.",
        ))
    return hits
