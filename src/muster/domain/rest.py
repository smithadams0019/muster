"""The rest period between two shifts, and what working inside it costs.

The remedy is expressed as the *premium above ordinary wages*, not the total pay
for the shift. Chicago's 1.25x base becomes a 0.25x premium; Oregon's 1.5x becomes
0.5x. Wages for hours worked are owed either way and are not Muster's to compute -
only the additional liability the ordinance creates is.
"""

from __future__ import annotations

from datetime import datetime

from muster.domain.types import Money
from muster.rulebook.schema import Jurisdiction


def rest_gap_hours(previous_shift_end: datetime, next_shift_start: datetime) -> float:
    """Hours between the end of one shift and the start of the next.

    A negative result means the shifts overlap, which is a scheduling error rather
    than a rest violation; callers treat it as a breach and a conflict both.
    """
    return (next_shift_start - previous_shift_end).total_seconds() / 3600.0


def breaches_rest(gap_hours: float, rules: Jurisdiction) -> bool:
    """Whether this gap is shorter than the jurisdiction's protected rest period."""
    return gap_hours < rules.rest_hours


def rest_remedy_owed(
    hours_worked: float,
    overtime_hours: float,
    hourly_rate: Money,
    rules: Jurisdiction,
) -> Money:
    """The premium above ordinary wages for working inside the rest period."""
    if overtime_hours > hours_worked:
        raise ValueError(
            f"overtime hours ({overtime_hours}) exceed hours worked ({hours_worked})"
        )
    remedy = rules.rest_remedy
    if remedy.flat_amount_cents is not None:
        return Money(cents=remedy.flat_amount_cents)

    straight_hours = hours_worked - overtime_hours
    straight = hourly_rate.scaled((remedy.multiplier - 1.0) * straight_hours)
    overtime_multiplier = remedy.overtime_multiplier or remedy.multiplier
    overtime = hourly_rate.scaled((overtime_multiplier - 1.0) * overtime_hours)
    return straight + overtime
