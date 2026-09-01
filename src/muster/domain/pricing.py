"""What one cover option really costs, itemised by the clause that produced it.

This is the object every decision is made from and every receipt is rendered from.
Deliberately the same object: a receipt assembled separately is a second account of
what happened, and two accounts eventually disagree.

Lawfulness is separate from cost. NYC retail does not price a cancellation inside
72 hours - it forbids one. Returning a cheap price for a prohibited change would
invite an agent to buy its way through a prohibition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from muster.domain.carve_outs import CarveOutClaim, CarveOutEvidence, carve_out_applies
from muster.domain.notice import notice_band
from muster.domain.overtime import overtime_delta
from muster.domain.premiums import premium_for
from muster.domain.rest import breaches_rest, rest_remedy_owed
from muster.domain.types import CarveOut, ChangeKind, ConsentKind, Money, NoticeBand
from muster.rulebook.schema import Jurisdiction

_PROHIBITED_INSIDE_WINDOW = frozenset({"us-ny-nyc-retail"})


@dataclass(frozen=True)
class LineItem:
    clause: str
    citation: str
    amount: Money


@dataclass(frozen=True)
class CostBreakdown:
    lines: tuple[LineItem, ...]
    total: Money
    carve_outs_applied: tuple[CarveOut, ...]
    requires_consent: bool
    consent_kind: ConsentKind | None
    lawful: bool
    unlawful_reason: str | None


def price_change(
    *,
    rules: Jurisdiction,
    kind: ChangeKind,
    posted_at: datetime,
    changed_at: datetime,
    schedule_starts_at: datetime,
    hourly_rate: Money,
    hours_lost: float,
    hours_worked: float,
    hours_before_this_week: float,
    rest_gap_hours: float | None,
    worker_id: str,
    shift_id: str,
    claims: tuple[CarveOutClaim, ...],
    evidence: CarveOutEvidence,
) -> CostBreakdown:
    """Price one change to a posted schedule, itemised."""
    if hourly_rate.cents < 0:
        raise ValueError(f"hourly rate cannot be negative: {hourly_rate}")

    band = notice_band(posted_at, changed_at, schedule_starts_at, rules)
    lines: list[LineItem] = []
    applied: list[CarveOut] = []

    if band is not NoticeBand.FULL_NOTICE and rules.code in _PROHIBITED_INSIDE_WINDOW:
        return CostBreakdown(
            lines=(), total=Money.zero(), carve_outs_applied=(),
            requires_consent=True, consent_kind=ConsentKind.EXTRA_HOURS,
            lawful=False,
            unlawful_reason=(
                f"{rules.name} prohibits this change inside {rules.notice_hours} hours "
                "without the worker's written consent; it is not something to be priced."
            ),
        )

    exempt = False
    for claim in claims:
        if carve_out_applies(claim, rules=rules, worker_id=worker_id,
                             shift_id=shift_id, evidence=evidence):
            applied.append(claim.kind)
            exempt = True

    if not exempt:
        owed = premium_for(kind, band, hourly_rate, hours_lost, rules)
        if owed.cents:
            rule = rules.premium_for_band(band, kind)
            lines.append(LineItem(
                clause=f"schedule change premium ({band.value})",
                citation=rule.citation if rule else rules.citation,
                amount=owed,
            ))

    requires_consent = False
    consent_kind: ConsentKind | None = None
    if rest_gap_hours is not None and breaches_rest(rest_gap_hours, rules):
        ot_cost, ot_hours = overtime_delta(hours_before_this_week, hours_worked, hourly_rate)
        remedy = rest_remedy_owed(hours_worked, ot_hours, hourly_rate, rules)
        lines.append(LineItem(
            clause=f"rest period premium ({rest_gap_hours:.1f}h gap, "
                   f"{rules.rest_hours:.0f}h protected)",
            citation=rules.citation,
            amount=remedy,
        ))
        requires_consent = True
        consent_kind = ConsentKind.REST_WAIVER

    ot_cost, ot_hours = overtime_delta(hours_before_this_week, hours_worked, hourly_rate)
    if ot_cost.cents:
        lines.append(LineItem(
            clause=f"overtime premium ({ot_hours:.1f}h beyond 40)",
            citation="FLSA weekly overtime",
            amount=ot_cost,
        ))

    total = Money(cents=sum(line.amount.cents for line in lines))
    return CostBreakdown(
        lines=tuple(lines),
        total=total,
        carve_outs_applied=tuple(applied),
        requires_consent=requires_consent,
        consent_kind=consent_kind,
        lawful=True,
        unlawful_reason=None,
    )
