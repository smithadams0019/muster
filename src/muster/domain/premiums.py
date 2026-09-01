"""What one change to a posted schedule owes.

Three jurisdictions express the same idea three ways - New York in flat dollars
per changed shift, Oregon in hours at the worker's own rate, Chicago in a fraction
of the hours taken away - so the rulebook stores all three forms and this function
resolves whichever one the matched rule uses.
"""

from __future__ import annotations

from muster.domain.types import ChangeKind, Money, NoticeBand
from muster.rulebook.schema import Jurisdiction


def premium_for(
    kind: ChangeKind,
    band: NoticeBand,
    hourly_rate: Money,
    hours_lost: float,
    rules: Jurisdiction,
) -> Money:
    """The premium owed for one changed shift.

    Returns zero when the jurisdiction's schedule has no rule for this combination.
    That is a genuine "nothing is owed", not a fallback: the absence of a row means
    the ordinance does not price that change, and the citation for every row that
    does exist is in the data file.
    """
    if hourly_rate.cents < 0:
        raise ValueError(f"hourly rate cannot be negative: {hourly_rate}")

    rule = rules.premium_for_band(band, kind)
    if rule is None:
        return Money.zero()

    if rule.amount_cents is not None:
        return Money(cents=rule.amount_cents)

    if rule.hours_at_rate is not None:
        return hourly_rate.scaled(rule.hours_at_rate)

    if hours_lost <= 0:
        raise ValueError(
            f"{rules.code} prices {kind.value} as a fraction of lost hours, "
            f"but hours_lost was {hours_lost}"
        )
    return hourly_rate.scaled(rule.fraction_of_lost_hours * hours_lost)
