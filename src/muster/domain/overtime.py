"""The overtime liability that covering a shift creates.

Returns the *premium above ordinary wages* - the half-rate uplift - not the total
cost of the hours, for the same reason the rest remedy does: the wages were going
to be paid to somebody. What matters when comparing cover options is the extra
liability each one creates.

Daily overtime rules (California's eight-hour day, for instance) are not modelled.
The three jurisdictions Muster ships with are weekly, and inventing a daily rule
for a state whose statute has not been read would be exactly the kind of confident
guess this project exists to avoid.
"""

from __future__ import annotations

from muster.domain.types import Money

_OVERTIME_UPLIFT = 0.5


def overtime_delta(
    hours_before: float,
    hours_added: float,
    hourly_rate: Money,
    weekly_threshold: float = 40.0,
) -> tuple[Money, float]:
    """Extra liability from adding hours, and how many of them are overtime."""
    if hours_before < 0 or hours_added < 0:
        raise ValueError(f"hours cannot be negative: {hours_before}, {hours_added}")

    hours_after = hours_before + hours_added
    overtime_hours = max(0.0, hours_after - max(weekly_threshold, hours_before))
    if overtime_hours == 0.0:
        return Money.zero(), 0.0
    return hourly_rate.scaled(_OVERTIME_UPLIFT * overtime_hours), overtime_hours
