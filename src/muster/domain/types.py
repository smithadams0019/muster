"""Vocabulary and the money type.

Money is integer cents throughout. Predictability premiums are small and are
multiplied by fractional rates - half the regular rate, one and a quarter times
base - and float cents accumulate error across a week of them. Rounding happens
once, half-up, at the end of each individual premium calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum


@dataclass(frozen=True, order=True)
class Money:
    cents: int

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int) or isinstance(self.cents, bool):
            raise TypeError(f"Money takes whole cents, got {self.cents!r}")

    @classmethod
    def from_dollars(cls, amount: str | int) -> Money:
        quantised = (Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return cls(cents=int(quantised))

    @classmethod
    def zero(cls) -> Money:
        return cls(cents=0)

    @property
    def dollars(self) -> str:
        return f"{Decimal(self.cents) / 100:.2f}"

    def __add__(self, other: Money) -> Money:
        return Money(cents=self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        return Money(cents=self.cents - other.cents)

    def scaled(self, factor: float | Decimal) -> Money:
        """Multiply by a rate and round half-up to the cent, once."""
        product = Decimal(self.cents) * Decimal(str(factor))
        return Money(cents=int(product.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    def __str__(self) -> str:
        return f"${self.dollars}"


class ChangeKind(str, Enum):
    """What was done to a posted shift. The ordinances price these differently."""

    ADD_SHIFT = "add_shift"
    ADD_HOURS = "add_hours"
    SUBTRACT_HOURS = "subtract_hours"
    CANCEL_SHIFT = "cancel_shift"
    MOVE_NO_LOSS = "move_no_loss"
    MOVE_WITH_LOSS = "move_with_loss"
    ON_CALL_NOT_CALLED = "on_call_not_called"


class NoticeBand(str, Enum):
    """How much warning the worker got, measured against the posting time."""

    FULL_NOTICE = "full_notice"
    INSIDE_WINDOW = "inside_window"
    UNDER_7_DAYS = "under_7_days"
    UNDER_24_HOURS = "under_24_hours"


class CarveOut(str, Enum):
    WORKER_REQUESTED = "worker_requested"
    STANDBY_LIST = "standby_list"
    MUTUAL_SHIFT_TRADE = "mutual_shift_trade"
    MUTUAL_WRITTEN_AGREEMENT = "mutual_written_agreement"
    ACT_OF_NATURE = "act_of_nature"
    UTILITY_FAILURE = "utility_failure"
    THREAT_TO_SAFETY = "threat_to_safety"


class ConsentKind(str, Enum):
    REST_WAIVER = "rest_waiver"
    EXTRA_HOURS = "extra_hours"
    SHIFT_TRADE = "shift_trade"


class ConsentOutcome(str, Enum):
    GRANTED = "granted"
    DECLINED = "declined"
    EXPIRED = "expired"


class AutonomyLevel(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    TRUSTED = "trusted"


class Role(str, Enum):
    BARISTA = "barista"
    SHIFT_LEAD = "shift_lead"
    BAKER = "baker"


class DisruptionKind(str, Enum):
    SICK_CALL = "sick_call"
    NO_SHOW = "no_show"
    DEMAND_SPIKE = "demand_spike"


class DecisionOutcome(str, Enum):
    APPROVE = "approve"
    DECLINE = "decline"
