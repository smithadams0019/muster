"""Sable Coffee: the seeded demo world.

Three sites, one per jurisdiction Muster ships, so the same question — "who can
cover this gap, and what does it cost?" — gets three different, lawful answers.
The clock is frozen at 2026-07-24T06:00Z, the Friday before the week beginning
Monday 27 July, so notice bands are stable and every run is reproducible. Rates,
good-faith hours and certifications are drawn from ``random.Random(seed)`` in a
fixed order, so the same seed always produces the same 36 workers.

Sites are sized to their own demand, and the week is built to it: shifts come
from each day's cover curve rather than from a fixed three-a-day template, and
workers are fitted to those shifts under the constraints the rulebooks care
about — the jurisdiction's rest period, a weekly hours ceiling and a maximum
number of days. A demo of a compliance product whose own seeded week broke the
rules would be arguing against itself.

The standby carve-out is Oregon-only in the rulebook, so it is Oregon-only here:
two Oregon baristas sit on the standby list and nobody else does. Evidence for
every other carve-out (`WORKER_REQUESTED`, `MUTUAL_WRITTEN_AGREEMENT`, the incident
kinds) starts empty; a `record_*` call is what makes a claim true, never an agent's
say-so.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from muster.domain.models import Schedule, Shift, Site, UnavailableWindow, Worker
from muster.domain.types import CarveOut, Money, Role

_TZ = timezone.utc
_FROZEN_NOW = datetime(2026, 7, 24, 6, 0, tzinfo=_TZ)
_WEEK_START = datetime(2026, 7, 27, tzinfo=_TZ)  # Monday

_RATES = ["17.50", "18.00", "18.50", "19.25", "20.00"]
_GOOD_FAITH_HOURS = [20.0, 24.0, 30.0, 32.0]
# A distinct roster per site. The same eight names repeated at all three read as
# a placeholder, and made "Jordan (OR)" versus "Jordan (CHI)" hard to hold apart
# on screen. The sites are different sizes because their demand is: a Bleecker
# Street store serves more people at 8am than a Portland one, and a roster that
# ignored that could not staff its own demand curve.
_NAMES_BY_SITE = {
    "site-or": [
        "Marisol", "Tobias", "Priya", "Declan", "Noor", "Emeka", "Sadie", "Wren",
        "Ines", "Cosmo",
    ],
    "site-chi": [
        "Antoine", "Hana", "Boris", "Lucia", "Kwame", "Fiona", "Rashid", "Junie",
        "Odalys", "Peter", "Simone", "Ade",
    ],
    "site-nyc": [
        "Ximena", "Owen", "Nadia", "Malik", "Beatriz", "Sung-ho", "Alina", "Tavio",
        "Grigor", "Imani", "Rafa", "Yusuf", "Dilara", "Marcus",
    ],
}

#: Two shift leads and one baker per site; everyone else is a barista. With a
#: single lead the seeded week put the same person on all seven days - fifty-six
#: hours without a day off, in a product whose entire subject is protecting
#: people from exactly that.
_ROLE_BY_INDEX = {1: Role.SHIFT_LEAD, 2: Role.SHIFT_LEAD, 3: Role.BAKER}

# (site_id, name, jurisdiction_code, opens_at_hour, closes_at_hour)
_SITE_DEFS = (
    ("site-or", "Sable Pearl", "us-or", 6, 20),
    ("site-chi", "Sable Wicker", "us-il-chicago", 6, 21),
    ("site-nyc", "Sable Bleecker", "us-ny-nyc-fastfood", 6, 22),
)

_DEMAND_SCALE = {"site-or": 1.0, "site-chi": 1.2, "site-nyc": 1.4}

#: Monday through Sunday. A coffee shop is not equally busy every day, and a
#: chart that drew the same silhouette seven times told a viewer nothing.
_DAY_SCALE = (0.9, 0.85, 1.0, 1.05, 1.25, 1.45, 1.2)
_BASE_DEMAND = {
    7: 2, 8: 3, 9: 3, 10: 2, 11: 1, 12: 1, 13: 1, 14: 1,
    15: 2, 16: 2, 17: 2, 18: 1, 19: 1, 20: 1, 21: 1,
}

#: Nobody works more than this in the seeded week, or more days than this. Both
#: sit well inside every threshold the rulebooks impose, because a demo world
#: that opens on a labour violation of its own is not a demo of compliance.
_MAX_WEEKLY_HOURS = 34.0
_MAX_DAYS = 5

#: Shifts are built to the demand curve, so they are neither all eight hours nor
#: all the same. These bound them: nothing shorter than a half-shift, nothing
#: longer than a full one.
_MIN_SHIFT_HOURS = 4
_MAX_SHIFT_HOURS = 8

#: The rest period each jurisdiction protects, mirrored from the rulebooks so
#: the seeded week does not have to load them to build itself.
_REST_HOURS = {"us-or": 10.0, "us-il-chicago": 10.0, "us-ny-nyc-fastfood": 11.0}

#: Time off, per site, as (worker index, day offset from Monday, reason).
#:
#: Two purposes. It gives the roster's "unavailable" count something to count
#: rather than sitting at zero all week, and it is what makes one day genuinely
#: hard. Five of the fourteen at Bleecker Street are off on Saturday 1 August -
#: the busiest day at the busiest site - so everyone still on the roster is
#: already working the morning. Cover for that afternoon therefore means a
#: sixteen-hour day, which under NYC's eleven-hour rule is not Muster's to
#: authorise: it has to ask, and it is the only place in the demo world where
#: every lawful option needs someone's consent.
_TIME_OFF = {
    "site-or": ((5, 2, "medical appointment"), (7, 5, "annual leave")),
    "site-chi": ((4, 1, "medical appointment"), (8, 5, "annual leave"),
                 (9, 6, "annual leave")),
    "site-nyc": ((3, 5, "annual leave"), (7, 5, "annual leave"),
                 (9, 5, "family leave"), (10, 5, "jury service"),
                 (11, 5, "annual leave")),
}

def _suffix(site_id: str) -> str:
    return site_id.removeprefix("site-")


def _at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


class SableCoffee:
    """The demo `WorldAdapter`: three sites, thirty-six workers, a frozen clock."""

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
            names = _NAMES_BY_SITE[site_id]
            time_off = {i: [] for i in range(1, len(names) + 1)}
            for index, day_offset, reason in _TIME_OFF.get(site_id, ()):
                day = _WEEK_START + timedelta(days=day_offset)
                time_off[index].append(UnavailableWindow(
                    starts_at=_at(day, 0),
                    ends_at=_at(day, 0) + timedelta(days=1),
                    reason=reason,
                ))

            site_roster: list[Worker] = []
            for i in range(1, len(names) + 1):
                role = _ROLE_BY_INDEX.get(i, Role.BARISTA)

                rate = Money.from_dollars(rng.choice(_RATES))
                good_faith = rng.choice(_GOOD_FAITH_HOURS)
                # Roughly half the roster is food-safety certified, both leads
                # among them, so a cover can genuinely fall below the site's
                # minimum without the roster being contrived to make it happen.
                certified = i % 2 == 1 or i == 2
                on_standby = site_id == "site-or" and i in (6, 7)

                worker = Worker(
                    worker_id=f"w-{suffix}-{i}",
                    name=names[i - 1],
                    site_id=site_id,
                    role=role,
                    hourly_rate=rate,
                    good_faith_hours=good_faith,
                    certifications=frozenset({"food_handler"}) if certified else frozenset(),
                    on_standby_list=on_standby,
                    unavailable=tuple(time_off[i]),
                )
                self._workers[worker.worker_id] = worker
                site_roster.append(worker)
            self._workers_by_site[site_id] = site_roster

        self._uncovered_blocks: dict[str, int] = {}
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

    def _shift_blocks(self, site: Site, day: datetime) -> list[tuple[int, int]]:
        """Start and end hours for one day, built to that day's demand curve.

        A sweep, not a template. Walk the opening hours; wherever the cover
        already laid down falls short of what the hour needs, open another shift
        there and run it while the shortfall lasts, bounded by
        `_MIN_SHIFT_HOURS` and `_MAX_SHIFT_HOURS`.

        The previous seed put the same three shifts on every day regardless, so
        the console's headline chart - scheduled cover against required cover -
        showed the line under the area on all seven days at all three sites. The
        demo's opening image was a shop that is permanently understaffed.
        """
        demand = self.demand(site.site_id, day)
        covered: dict[int, int] = {}
        blocks: list[tuple[int, int]] = []
        for hour in range(site.opens_at_hour, site.closes_at_hour):
            while covered.get(hour, 0) < demand.get(hour, 0):
                end = hour
                while (
                    end < site.closes_at_hour
                    and end - hour < _MAX_SHIFT_HOURS
                    and demand.get(end, 0) > covered.get(end, 0)
                ):
                    end += 1
                end = min(site.closes_at_hour, max(end, hour + _MIN_SHIFT_HOURS))
                for h in range(hour, end):
                    covered[h] = covered.get(h, 0) + 1
                blocks.append((hour, end))
        return blocks

    def _build_week_schedule(self, site: Site) -> Schedule:
        """A posted week for `site`, Monday 2026-07-27 through Sunday 2026-08-02.

        Shifts come from `_shift_blocks`, so the week staffs its own demand
        curve. Workers are then fitted to those shifts under the same
        constraints the rulebooks care about: the jurisdiction's rest period
        between one shift and the next, no more than `_MAX_WEEKLY_HOURS`, no
        more than `_MAX_DAYS` days, and never while on leave.

        One breach is deliberate and is the only one: a barista closes on the
        Sunday *before* the week and opens the following Monday, a gap under ten
        hours at every site, so the DRAFT loop has a real rest-period problem to
        find rather than an invented one.
        """
        roster = self._workers_by_site[site.site_id]
        leads = [w for w in roster if w.role is Role.SHIFT_LEAD]
        baker = next(w for w in roster if w.role is Role.BAKER)
        baristas = [w for w in roster if w.role is Role.BARISTA]
        rest_hours = _REST_HOURS.get(site.jurisdiction_code, 10.0)
        suffix = _suffix(site.site_id)

        hours: dict[str, float] = {}
        days: dict[str, set[int]] = {}
        last_end: dict[str, datetime] = {}

        def take(worker: Worker, starts_at: datetime, ends_at: datetime,
                 day_index: int, *, enforce_rest: bool = True) -> bool:
            length = (ends_at - starts_at).total_seconds() / 3600
            if day_index in days.get(worker.worker_id, set()):
                return False
            if hours.get(worker.worker_id, 0.0) + length > _MAX_WEEKLY_HOURS:
                return False
            if len(days.get(worker.worker_id, set())) >= _MAX_DAYS:
                return False
            if not worker.is_available(starts_at, ends_at):
                return False
            previous = last_end.get(worker.worker_id)
            if enforce_rest and previous is not None:
                gap = (starts_at - previous).total_seconds() / 3600
                if gap < rest_hours:
                    return False
            hours[worker.worker_id] = hours.get(worker.worker_id, 0.0) + length
            days.setdefault(worker.worker_id, set()).add(day_index)
            last_end[worker.worker_id] = ends_at
            return True

        def fewest_hours_first(pool: list[Worker], *, certified_first: bool = False) -> list[Worker]:
            """Spread the week rather than exhausting the first name on the list.

            `certified_first` is used for the block that closes the day. Once the
            lead has gone home the closer is often the only person left on the
            floor, and a site with a certified-handler minimum cannot end its day
            without one. Left to hours alone the seed produced a Chicago week
            where not one of the seven closes had a certified handler on it.
            """
            return sorted(pool, key=lambda w: (
                not w.is_certified("food_handler") if certified_first else False,
                hours.get(w.worker_id, 0.0),
                w.worker_id,
            ))

        # The deliberate bridge: Sunday-before close into Monday open.
        sunday_before = _WEEK_START - timedelta(days=1)
        bridge_worker = baristas[0]
        bridge_end = _at(sunday_before, site.closes_at_hour + 1, 30)
        shifts: list[Shift] = [
            Shift(
                shift_id=f"s-{suffix}-{sunday_before:%Y%m%d}-bridge-close",
                site_id=site.site_id,
                role=Role.BARISTA,
                starts_at=_at(sunday_before, site.closes_at_hour - 7),
                ends_at=bridge_end,
                worker_id=bridge_worker.worker_id,
            )
        ]
        last_end[bridge_worker.worker_id] = bridge_end
        hours[bridge_worker.worker_id] = (bridge_end - shifts[0].starts_at).total_seconds() / 3600
        days[bridge_worker.worker_id] = {-1}

        uncovered = 0
        for day_index in range(7):
            day = _WEEK_START + timedelta(days=day_index)
            blocks = self._shift_blocks(site, day)

            # The longest block of the day is the lead's; it is the one that
            # spans the peak, which is where a site most needs someone in charge.
            # By index, not by value: two blocks on a busy morning can have the
            # same start and end hour, and comparing tuples made both of them the
            # lead's shift - which put two leads on one block and left the next
            # day without one.
            lead_index = (
                max(range(len(blocks)), key=lambda i: (blocks[i][1] - blocks[i][0], -blocks[i][0]))
                if blocks else None
            )
            closing_index = (
                max(range(len(blocks)), key=lambda i: blocks[i][1]) if blocks else None
            )

            if day_index < 5:  # the baker works Monday to Friday, and rests
                bake_start, bake_end = _at(day, 5), _at(day, 11)
                if take(baker, bake_start, bake_end, day_index):
                    shifts.append(Shift(
                        shift_id=f"s-{suffix}-{day:%Y%m%d}-bake",
                        site_id=site.site_id, role=Role.BAKER,
                        starts_at=bake_start, ends_at=bake_end,
                        worker_id=baker.worker_id,
                    ))

            for n, (start_hour, end_hour) in enumerate(blocks):
                starts_at, ends_at = _at(day, start_hour), _at(day, end_hour)
                is_lead = n == lead_index
                pool = leads if is_lead else baristas
                # Monday's first barista block is the bridge worker's, and only
                # there is the rest period allowed to be short.
                bridge = day_index == 0 and not is_lead and not any(
                    sh.worker_id == bridge_worker.worker_id
                    and sh.starts_at.date() == day.date()
                    for sh in shifts
                )

                # The bridge worker is put on Monday's first barista block on
                # purpose, rest period and all. Leaving it to the ordinary
                # ordering meant whoever had fewest hours took it and the seeded
                # week contained no rest breach at all - so the DRAFT loop had
                # nothing real to find.
                chosen = None
                if bridge and bridge_worker in pool:
                    if take(bridge_worker, starts_at, ends_at, day_index, enforce_rest=False):
                        chosen = bridge_worker
                if chosen is None:
                    chosen = next(
                        (w for w in fewest_hours_first(pool, certified_first=n == closing_index)
                         if take(w, starts_at, ends_at, day_index)),
                        None,
                    )
                if chosen is None and not is_lead:
                    chosen = next(
                        (w for w in fewest_hours_first(leads)
                         if take(w, starts_at, ends_at, day_index)),
                        None,
                    )
                # A block nobody can lawfully take stays on the schedule with
                # nobody's name on it. That is what an unfilled slot is, and it
                # belongs in the operator's open-shifts row rather than being
                # quietly dropped so the week looks fuller than it is.
                if chosen is None:
                    uncovered += 1
                shifts.append(Shift(
                    shift_id=f"s-{suffix}-{day:%Y%m%d}-{start_hour:02d}{end_hour:02d}-{n}",
                    site_id=site.site_id,
                    role=Role.SHIFT_LEAD if is_lead else Role.BARISTA,
                    starts_at=starts_at, ends_at=ends_at,
                    worker_id=chosen.worker_id if chosen else None,
                ))

        self._uncovered_blocks[site.site_id] = uncovered
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
        scale = _DEMAND_SCALE.get(site_id, 1.0) * _DAY_SCALE[day.weekday()]
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

    def posted_weeks(self, site_id: str) -> list[datetime]:
        """Week-start datetimes this site already has a posted schedule for.

        The API records these in its ledger at start-up, because the dependency
        guard decides whether a shift may be touched by looking for a posting
        entry there, and a week the world posted before the process began would
        otherwise look unposted.
        """
        return [
            week for (sid, week), schedule in self._schedules.items()
            if sid == site_id and schedule.is_posted
        ]

    def store_schedule(self, schedule: Schedule) -> None:
        self._schedules[(schedule.site_id, schedule.week_starts_at)] = schedule
        for shift in schedule.shifts:
            self._shifts[shift.shift_id] = shift
