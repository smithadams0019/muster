"""Sable Coffee: the seeded demo world.

Three sites, one per jurisdiction Muster ships, so the same question — "who can
cover this gap, and what does it cost?" — gets three different, lawful answers.
The clock is frozen at 2026-07-24T06:00Z, the Friday before the week beginning
Monday 27 July, so notice bands are stable and every run is reproducible. The
roster is drawn from ``random.Random(seed)`` in a fixed order, so the same seed
always produces the same 24 workers.

The standby carve-out is Oregon-only in the rulebook, so it is Oregon-only here:
two Oregon baristas sit on the standby list and nobody else does. Evidence for
every other carve-out (`WORKER_REQUESTED`, `MUTUAL_WRITTEN_AGREEMENT`, the incident
kinds) starts empty; a `record_*` call is what makes a claim true, never an agent's
say-so.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from muster.domain.models import Schedule, Shift, Site, Worker
from muster.domain.types import CarveOut, Money, Role

_TZ = timezone.utc
_FROZEN_NOW = datetime(2026, 7, 24, 6, 0, tzinfo=_TZ)
_WEEK_START = datetime(2026, 7, 27, tzinfo=_TZ)  # Monday

_RATES = ["17.50", "18.00", "18.50", "19.25", "20.00"]
_GOOD_FAITH_HOURS = [20.0, 24.0, 30.0, 32.0]
_NAMES = ["Jordan", "Riley", "Sam", "Taylor", "Morgan", "Casey", "Drew", "Reese"]

# (site_id, name, jurisdiction_code, opens_at_hour, closes_at_hour)
_SITE_DEFS = (
    ("site-or", "Sable Pearl", "us-or", 6, 20),
    ("site-chi", "Sable Wicker", "us-il-chicago", 6, 21),
    ("site-nyc", "Sable Bleecker", "us-ny-nyc-fastfood", 6, 22),
)

_DEMAND_SCALE = {"site-or": 1.0, "site-chi": 1.3, "site-nyc": 1.6}
_BASE_DEMAND = {
    7: 3, 8: 4, 9: 3, 10: 2, 11: 1, 12: 1, 13: 1, 14: 1,
    15: 2, 16: 3, 17: 2, 18: 1, 19: 1, 20: 1, 21: 1,
}


def _suffix(site_id: str) -> str:
    return site_id.removeprefix("site-")


def _at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


class SableCoffee:
    """The demo `WorldAdapter`: three sites, twenty-four workers, a frozen clock."""

    def __init__(self, seed: int = 7, now: datetime | None = None) -> None:
        self._now = now if now is not None else _FROZEN_NOW

        self._sites: dict[str, Site] = {}
        for site_id, name, jurisdiction_code, opens, closes in _SITE_DEFS:
            self._sites[site_id] = Site(
                site_id=site_id,
                name=name,
                jurisdiction_code=jurisdiction_code,
                opens_at_hour=opens,
                closes_at_hour=closes,
                role_minimums={Role.SHIFT_LEAD: 1, Role.BARISTA: 2},
                certified_handler_minimum=1,
            )

        rng = random.Random(seed)
        self._workers: dict[str, Worker] = {}
        self._workers_by_site: dict[str, list[Worker]] = {}
        for site_id, *_rest in _SITE_DEFS:
            suffix = _suffix(site_id)
            site_roster: list[Worker] = []
            for i in range(1, 9):
                if i == 1:
                    role = Role.SHIFT_LEAD
                elif i == 2:
                    role = Role.BAKER
                else:
                    role = Role.BARISTA

                rate = Money.from_dollars(rng.choice(_RATES))
                good_faith = rng.choice(_GOOD_FAITH_HOURS)
                certified = i in (1, 3, 4)  # the lead and two baristas hold food_handler
                on_standby = site_id == "site-or" and i in (5, 6)

                worker = Worker(
                    worker_id=f"w-{suffix}-{i}",
                    name=f"{_NAMES[i - 1]} ({suffix.upper()})",
                    site_id=site_id,
                    role=role,
                    hourly_rate=rate,
                    good_faith_hours=good_faith,
                    certifications=frozenset({"food_handler"}) if certified else frozenset(),
                    on_standby_list=on_standby,
                    unavailable=(),
                )
                self._workers[worker.worker_id] = worker
                site_roster.append(worker)
            self._workers_by_site[site_id] = site_roster

        self._schedules: dict[tuple[str, datetime], Schedule] = {}
        self._shifts: dict[str, Shift] = {}
        for site_id, *_rest in _SITE_DEFS:
            schedule = self._build_week_schedule(self._sites[site_id])
            self._schedules[(schedule.site_id, schedule.week_starts_at)] = schedule
            for shift in schedule.shifts:
                self._shifts[shift.shift_id] = shift

        # Evidence registries. Empty until a `record_*` call earns them.
        self._declines: set[tuple[str, str]] = set()
        self._standby_accepts: set[tuple[str, str]] = set()
        self._requests: set[tuple[str, str]] = set()
        self._agreements: set[str] = set()
        self._incidents: dict[str, CarveOut] = {}

    # -- construction -----------------------------------------------------

    def _build_week_schedule(self, site: Site) -> Schedule:
        """A posted week for `site`, Monday 2026-07-27 through Sunday 2026-08-02.

        Includes one bridge shift on the Sunday before the week starts: a barista
        closes late (1.5 hours past the site's normal close) and then opens the
        following Monday at 07:00. The gap between the two is under ten hours at
        every site, so a later task can find a rest-period breach without having
        to invent one of its own.
        """
        baristas = self._workers_by_site[site.site_id][2:]  # six baristas
        lead = self._workers_by_site[site.site_id][0]
        baker = self._workers_by_site[site.site_id][1]
        bridge_worker = baristas[0]
        suffix = _suffix(site.site_id)

        sunday_before = _WEEK_START - timedelta(days=1)
        shifts: list[Shift] = [
            Shift(
                shift_id=f"s-{suffix}-{sunday_before:%Y%m%d}-bridge-close",
                site_id=site.site_id,
                role=Role.BARISTA,
                starts_at=_at(sunday_before, site.closes_at_hour - 7),
                ends_at=_at(sunday_before, site.closes_at_hour + 1, 30),
                worker_id=bridge_worker.worker_id,
            )
        ]

        for day_index in range(7):
            day = _WEEK_START + timedelta(days=day_index)
            opener = baristas[day_index % len(baristas)]
            closer = baristas[(day_index + 3) % len(baristas)]

            shifts.append(
                Shift(
                    shift_id=f"s-{suffix}-{day:%Y%m%d}-open",
                    site_id=site.site_id,
                    role=Role.BARISTA,
                    starts_at=_at(day, 7),
                    ends_at=_at(day, 15),
                    worker_id=opener.worker_id,
                )
            )
            shifts.append(
                Shift(
                    shift_id=f"s-{suffix}-{day:%Y%m%d}-lead",
                    site_id=site.site_id,
                    role=Role.SHIFT_LEAD,
                    starts_at=_at(day, 8),
                    ends_at=_at(day, 16),
                    worker_id=lead.worker_id,
                )
            )
            shifts.append(
                Shift(
                    shift_id=f"s-{suffix}-{day:%Y%m%d}-bake",
                    site_id=site.site_id,
                    role=Role.BAKER,
                    starts_at=_at(day, 5),
                    ends_at=_at(day, 11),
                    worker_id=baker.worker_id,
                )
            )
            shifts.append(
                Shift(
                    shift_id=f"s-{suffix}-{day:%Y%m%d}-close",
                    site_id=site.site_id,
                    role=Role.BARISTA,
                    starts_at=_at(day, site.closes_at_hour - 8),
                    ends_at=_at(day, site.closes_at_hour),
                    worker_id=closer.worker_id,
                )
            )

        shifts.sort(key=lambda s: s.starts_at)
        return Schedule(
            site_id=site.site_id,
            week_starts_at=_WEEK_START,
            posted_at=self._now,
            shifts=tuple(shifts),
        )

    # -- WorldAdapter -------------------------------------------------------

    def now(self) -> datetime:
        return self._now

    def sites(self) -> list[Site]:
        return list(self._sites.values())

    def site(self, site_id: str) -> Site | None:
        return self._sites.get(site_id)

    def workers(self, site_id: str | None = None) -> list[Worker]:
        if site_id is None:
            return list(self._workers.values())
        return list(self._workers_by_site.get(site_id, []))

    def worker(self, worker_id: str) -> Worker | None:
        return self._workers.get(worker_id)

    def schedule(self, site_id: str, week_starts_at: datetime) -> Schedule | None:
        return self._schedules.get((site_id, week_starts_at))

    def shift(self, shift_id: str) -> Shift | None:
        return self._shifts.get(shift_id)

    def demand(self, site_id: str, day: datetime) -> dict[int, int]:
        site = self._sites.get(site_id)
        if site is None:
            return {}
        scale = _DEMAND_SCALE.get(site_id, 1.0)
        curve: dict[int, int] = {}
        for hour in range(site.opens_at_hour, site.closes_at_hour):
            base = _BASE_DEMAND.get(hour, 1)
            curve[hour] = max(0, round(base * scale))
        return curve

    # -- carve-out evidence ---------------------------------------------

    def worker_requested(self, worker_id: str, shift_id: str) -> bool:
        return (worker_id, shift_id) in self._requests

    def on_standby_list(self, worker_id: str) -> bool:
        worker = self._workers.get(worker_id)
        return worker is not None and worker.on_standby_list

    def standby_accepted(self, worker_id: str, shift_id: str) -> bool:
        return (worker_id, shift_id) in self._standby_accepts

    def trade_accepted_by_both(self, shift_id: str, from_worker: str, to_worker: str) -> bool:
        # Sable Coffee doesn't seed shift-trade evidence: MUTUAL_SHIFT_TRADE
        # claims never carve out here until a later task wires the registry.
        return False

    def written_agreement(self, evidence_id: str | None) -> bool:
        return evidence_id is not None and evidence_id in self._agreements

    def declared_incident(self, evidence_id: str | None) -> CarveOut | None:
        if evidence_id is None:
            return None
        return self._incidents.get(evidence_id)

    # -- consent history --------------------------------------------------

    def has_declined(self, worker_id: str, shift_id: str) -> bool:
        return (worker_id, shift_id) in self._declines

    # -- writers: what turns a claim into evidence -------------------------

    def record_decline(self, worker_id: str, shift_id: str) -> None:
        self._declines.add((worker_id, shift_id))

    def record_standby_acceptance(self, worker_id: str, shift_id: str) -> None:
        self._standby_accepts.add((worker_id, shift_id))

    def record_worker_request(self, worker_id: str, shift_id: str) -> None:
        self._requests.add((worker_id, shift_id))

    def record_written_agreement(self, evidence_id: str) -> None:
        self._agreements.add(evidence_id)

    def declare_incident(self, evidence_id: str, kind: CarveOut) -> None:
        self._incidents[evidence_id] = kind

    # -- schedule writes ----------------------------------------------------

    def store_schedule(self, schedule: Schedule) -> None:
        self._schedules[(schedule.site_id, schedule.week_starts_at)] = schedule
        for shift in schedule.shifts:
            self._shifts[shift.shift_id] = shift
