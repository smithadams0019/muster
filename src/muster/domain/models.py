"""The nouns.

Deliberately dumb: these hold facts and answer questions about themselves. Every
figure that costs money is computed in the pricing modules, so that the objects
flowing through the agent cannot quietly disagree with the arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from muster.domain.types import ChangeKind, DisruptionKind, Money, Role


@dataclass(frozen=True)
class UnavailableWindow:
    starts_at: datetime
    ends_at: datetime
    reason: str


@dataclass(frozen=True)
class Worker:
    worker_id: str
    name: str
    site_id: str
    role: Role
    hourly_rate: Money
    good_faith_hours: float
    certifications: frozenset[str]
    on_standby_list: bool
    unavailable: tuple[UnavailableWindow, ...]

    def is_certified(self, certification: str) -> bool:
        return certification in self.certifications

    def is_available(self, starts_at: datetime, ends_at: datetime) -> bool:
        return not any(w.starts_at < ends_at and starts_at < w.ends_at for w in self.unavailable)


@dataclass(frozen=True)
class Site:
    site_id: str
    name: str
    jurisdiction_code: str
    opens_at_hour: int
    closes_at_hour: int
    role_minimums: dict[Role, int]
    certified_handler_minimum: int


@dataclass(frozen=True)
class Shift:
    shift_id: str
    site_id: str
    role: Role
    starts_at: datetime
    ends_at: datetime
    worker_id: str | None

    def __post_init__(self) -> None:
        if self.ends_at < self.starts_at:
            raise ValueError(f"shift {self.shift_id} ends before it starts")

    @property
    def hours(self) -> float:
        return (self.ends_at - self.starts_at).total_seconds() / 3600.0


@dataclass(frozen=True)
class Schedule:
    site_id: str
    week_starts_at: datetime
    posted_at: datetime | None
    shifts: tuple[Shift, ...]

    @property
    def is_posted(self) -> bool:
        return self.posted_at is not None

    def hours_for(self, worker_id: str) -> float:
        return sum(s.hours for s in self.shifts if s.worker_id == worker_id)

    def last_shift_ending_before(self, worker_id: str, moment: datetime) -> Shift | None:
        candidates = [s for s in self.shifts if s.worker_id == worker_id and s.ends_at <= moment]
        return max(candidates, key=lambda s: s.ends_at) if candidates else None


@dataclass(frozen=True)
class Disruption:
    disruption_id: str
    kind: DisruptionKind
    shift_id: str
    reported_at: datetime
    note: str = ""


@dataclass(frozen=True)
class CoverOption:
    """One lawful way to cover a gap, before it has been priced."""

    option_id: str
    kind: ChangeKind
    worker_id: str
    shift_id: str
    hours: float
    rest_gap_hours: float | None
    claims: tuple = field(default_factory=tuple)
    note: str = ""
