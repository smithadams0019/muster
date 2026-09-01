"""The shape of a jurisdiction's rulebook.

Rules are data, not branches. A city that amends its ordinance becomes a new
record with a later `effective_from`, so a receipt written last March still
evaluates under the rules that were in force last March.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from muster.domain.types import CarveOut, ChangeKind, NoticeBand


@dataclass(frozen=True)
class PremiumRule:
    """One row of a jurisdiction's premium schedule.

    Exactly one of the three amount fields is set, because the ordinances express
    the same idea three different ways: NYC in flat dollars, Oregon in hours at the
    regular rate, Chicago in a fraction of the hours taken away.
    """

    band: NoticeBand
    kinds: frozenset[ChangeKind]
    citation: str
    amount_cents: int | None = None
    hours_at_rate: float | None = None
    fraction_of_lost_hours: float | None = None

    def __post_init__(self) -> None:
        given = [f is not None for f in
                 (self.amount_cents, self.hours_at_rate, self.fraction_of_lost_hours)]
        if sum(given) != 1:
            raise ValueError(f"a premium rule needs exactly one amount form, got {given}")


@dataclass(frozen=True)
class RestRemedy:
    """What is owed when someone works inside their rest period.

    Chicago and Oregon multiply the rate; NYC pays a flat clopening premium. A
    jurisdiction sets one or the other, never both.
    """

    multiplier: float | None = None
    overtime_multiplier: float | None = None
    flat_amount_cents: int | None = None

    def __post_init__(self) -> None:
        if (self.multiplier is None) == (self.flat_amount_cents is None):
            raise ValueError("a rest remedy is either a multiplier or a flat amount")


@dataclass(frozen=True)
class CoverageTest:
    """Who the ordinance applies to. Declared by the operator, not decided here."""

    industries: frozenset[str]
    min_employees_worldwide: int | None


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    name: str
    effective_from: date
    notice_hours: int
    premiums: tuple[PremiumRule, ...]
    rest_hours: float
    rest_remedy: RestRemedy
    rest_requires_written_consent: bool
    rest_has_carve_outs: bool
    carve_outs: frozenset[CarveOut]
    coverage: CoverageTest
    citation: str

    def premium_for_band(self, band: NoticeBand, kind: ChangeKind) -> PremiumRule | None:
        """The rule that prices this change, or None when nothing is owed.

        FULL_NOTICE returns None everywhere: a change made before the notice window
        opened is just a schedule, not a change.
        """
        if band is NoticeBand.FULL_NOTICE:
            return None
        for rule in self.premiums:
            if rule.band is band and kind in rule.kinds:
                return rule
        return None
