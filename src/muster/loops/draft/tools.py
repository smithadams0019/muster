"""Tools for the DRAFT loop: propose a week, find what breaks, repair it, post it.

Five tools, only one guarded. The agent is not asked to solve a rota; it is asked
to propose shifts and repeatedly call `check_draft` until nothing is wrong - the
same generate-and-repair loop a human scheduler runs by hand. `check_draft`
computes rest breaches with `rest_gap_hours` / `breaches_rest` against the site's
own jurisdiction, so a draft is checked under the same rules a later change to it
would be priced under.

The draft itself lives only in `draft_state`, in memory, until `post_schedule`
writes it into the world. Nothing here mutates the world's posted schedule before
that call.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from strands import tool

from muster.adapters.base import WorldAdapter
from muster.domain.models import Schedule, Shift
from muster.domain.rest import breaches_rest, rest_gap_hours
from muster.domain.types import Role
from muster.rulebook.loader import for_code

#: The certification Sable Coffee's sites require at least one worker per shift
#: hour to hold. `Site.certified_handler_minimum` says how many; this says which.
CERTIFICATION = "food_handler"


def check_draft_problems(
    world: WorldAdapter,
    draft_state: dict[str, list[Shift]],
    site_id: str,
    week_starts_at: datetime,
) -> list[dict[str, Any]]:
    """Every problem the current draft for `site_id` has, or an empty list.

    Shared between the `check_draft` tool and the DRAFT context provider, so the
    ranking the agent sees and the judgement the escalation policy makes about
    `post_schedule` can never disagree.
    """
    site = world.site(site_id)
    if site is None:
        return []

    shifts = list(draft_state.get(site_id, []))
    workers_by_id = {w.worker_id: w for w in world.workers(site_id)}
    problems: list[dict[str, Any]] = []

    for day_index in range(7):
        day_dt = week_starts_at + timedelta(days=day_index)
        day = day_dt.date()
        curve = world.demand(site_id, day_dt)

        for hour, required in curve.items():
            if required <= 0:
                continue

            moment = day_dt.replace(hour=hour, minute=0, second=0, microsecond=0)
            covering = [s for s in shifts if s.starts_at <= moment < s.ends_at]
            covered = len(covering)

            if covered < required:
                problems.append({
                    "kind": "uncovered",
                    "detail": f"{site.name} needs {required} covering "
                              f"{day.isoformat()} at {hour:02d}:00 but only "
                              f"{covered} are scheduled.",
                    "day": day.isoformat(),
                    "hour": hour,
                })

            covering_workers = [
                workers_by_id[s.worker_id] for s in covering if s.worker_id in workers_by_id
            ]

            if site.certified_handler_minimum > 0:
                certified = sum(1 for w in covering_workers if w.is_certified(CERTIFICATION))
                if certified < site.certified_handler_minimum:
                    problems.append({
                        "kind": "no_certified_handler",
                        "detail": f"No {CERTIFICATION.replace('_', ' ')} on shift at "
                                  f"{site.name} on {day.isoformat()} at {hour:02d}:00.",
                        "day": day.isoformat(),
                        "hour": hour,
                    })

            role_counts: Counter[Role] = Counter(w.role for w in covering_workers)
            for role, minimum in site.role_minimums.items():
                if role_counts.get(role, 0) < minimum:
                    problems.append({
                        "kind": "role_minimum",
                        "detail": f"{site.name} needs {minimum} {role.value}(s) on "
                                  f"{day.isoformat()} at {hour:02d}:00, has "
                                  f"{role_counts.get(role, 0)}.",
                        "day": day.isoformat(),
                        "hour": hour,
                    })

    by_worker: dict[str, list[Shift]] = defaultdict(list)
    for s in shifts:
        by_worker[s.worker_id].append(s)

    try:
        rules = for_code(site.jurisdiction_code, on=world.now().date())
    except (KeyError, LookupError):
        rules = None

    for worker_id, worker_shifts in by_worker.items():
        worker = workers_by_id.get(worker_id)
        ordered = sorted(worker_shifts, key=lambda s: s.starts_at)

        for s in ordered:
            if worker is not None and not worker.is_available(s.starts_at, s.ends_at):
                problems.append({
                    "kind": "unavailable",
                    "detail": f"{worker.name} is not available for the shift on "
                              f"{s.starts_at.date().isoformat()} starting at "
                              f"{s.starts_at:%H:%M}.",
                    "worker_id": worker_id,
                    "day": s.starts_at.date().isoformat(),
                })

        if rules is not None:
            for prev_shift, next_shift in zip(ordered, ordered[1:]):
                gap = rest_gap_hours(prev_shift.ends_at, next_shift.starts_at)
                if breaches_rest(gap, rules):
                    name = worker.name if worker is not None else worker_id
                    problems.append({
                        "kind": "rest_breach",
                        "detail": f"{name} would get only {gap:.1f}h of rest between "
                                  f"a shift ending {prev_shift.ends_at:%Y-%m-%d %H:%M} "
                                  f"and one starting {next_shift.starts_at:%Y-%m-%d %H:%M}; "
                                  f"{site.jurisdiction_code} requires {rules.rest_hours:.1f}h.",
                        "worker_id": worker_id,
                        "day": next_shift.starts_at.date().isoformat(),
                    })

    hours_by_worker: dict[str, float] = defaultdict(float)
    for s in shifts:
        hours_by_worker[s.worker_id] += s.hours
    for worker in world.workers(site_id):
        scheduled = hours_by_worker.get(worker.worker_id, 0.0)
        if worker.good_faith_hours and scheduled < worker.good_faith_hours:
            problems.append({
                "kind": "hours_shortfall",
                "detail": f"{worker.name} is scheduled {scheduled:.1f}h against a "
                          f"good-faith target of {worker.good_faith_hours:.1f}h.",
                "worker_id": worker.worker_id,
            })

    return problems


def build_draft_tools(
    world: WorldAdapter,
    ledger: list[dict[str, Any]],
    week_starts_at: datetime,
    clock: Any,
    draft_state: dict[str, list[Shift]] | None = None,
) -> list[Any]:
    """The five DRAFT-loop tools, closed over one shared in-memory draft.

    `draft_state` may be supplied so a context provider built alongside these
    tools can read the same not-yet-posted draft; when omitted, a fresh one is
    created here.
    """
    state: dict[str, list[Shift]] = {} if draft_state is None else draft_state

    @tool
    def demand_for_week(site_id: str) -> dict[str, Any]:
        """The hourly cover requirement for every day of the drafted week."""
        site = world.site(site_id)
        if site is None:
            return {"error": f"unknown site {site_id!r}"}
        days: dict[str, dict[int, int]] = {}
        for day_index in range(7):
            day_dt = week_starts_at + timedelta(days=day_index)
            days[day_dt.date().isoformat()] = world.demand(site_id, day_dt)
        return {
            "site_id": site_id,
            "week_starts_at": week_starts_at.date().isoformat(),
            "days": days,
        }

    @tool
    def list_workers(site_id: str) -> list[dict[str, Any]] | dict[str, str]:
        """The roster at a site: rates, availability, certifications, good-faith hours."""
        site = world.site(site_id)
        if site is None:
            return {"error": f"unknown site {site_id!r}"}
        return [
            {
                "worker_id": w.worker_id,
                "name": w.name,
                "role": w.role.value,
                "hourly_rate_cents": w.hourly_rate.cents,
                "good_faith_hours": w.good_faith_hours,
                "certifications": sorted(w.certifications),
                "on_standby_list": w.on_standby_list,
                "unavailable": [
                    {
                        "starts_at": u.starts_at.isoformat(),
                        "ends_at": u.ends_at.isoformat(),
                        "reason": u.reason,
                    }
                    for u in w.unavailable
                ],
            }
            for w in world.workers(site_id)
        ]

    @tool
    def propose_shift(
        site_id: str, worker_id: str, day: str, start_hour: int, end_hour: int, role: str
    ) -> dict[str, Any]:
        """Add one shift to the working draft. Returns its shift_id, or an error."""
        site = world.site(site_id)
        if site is None:
            return {"error": f"unknown site {site_id!r}"}

        worker = world.worker(worker_id)
        if worker is None:
            return {"error": f"unknown worker {worker_id!r}"}
        if worker.site_id != site_id:
            return {"error": f"{worker_id!r} belongs to site {worker.site_id!r}, not {site_id!r}"}

        try:
            day_date = date.fromisoformat(day)
        except ValueError:
            return {"error": f"day must be an ISO date, got {day!r}"}
        offset = (day_date - week_starts_at.date()).days
        if not (0 <= offset <= 6):
            return {"error": f"{day} is outside the drafted week starting "
                              f"{week_starts_at.date().isoformat()}"}

        try:
            role_enum = Role(role)
        except ValueError:
            return {"error": f"unknown role {role!r}"}

        if end_hour <= start_hour:
            return {"error": "end_hour must be after start_hour"}

        tzinfo = week_starts_at.tzinfo
        starts_at = datetime(day_date.year, day_date.month, day_date.day, start_hour, tzinfo=tzinfo)
        ends_at = datetime(day_date.year, day_date.month, day_date.day, end_hour, tzinfo=tzinfo)

        existing = state.setdefault(site_id, [])
        shift_id = f"draft-{site_id}-{day_date.isoformat()}-{start_hour:02d}{end_hour:02d}" \
                   f"-{worker_id}-{len(existing) + 1}"
        try:
            shift = Shift(
                shift_id=shift_id, site_id=site_id, role=role_enum,
                starts_at=starts_at, ends_at=ends_at, worker_id=worker_id,
            )
        except ValueError as exc:
            return {"error": str(exc)}

        existing.append(shift)
        return {
            "shift_id": shift_id, "site_id": site_id, "worker_id": worker_id,
            "day": day_date.isoformat(), "start_hour": start_hour, "end_hour": end_hour,
            "role": role_enum.value,
        }

    @tool
    def check_draft(site_id: str) -> list[dict[str, Any]]:
        """Every problem the current draft has: uncovered hours, rest breaches,

        availability conflicts, workers below good-faith hours, missing certified
        handler coverage, and role-minimum shortfalls.
        """
        return check_draft_problems(world, state, site_id, week_starts_at)

    @tool
    def post_schedule(site_id: str) -> dict[str, Any]:
        """Post the draft. Refuses an empty draft. The notice clock starts here."""
        site = world.site(site_id)
        if site is None:
            return {"error": f"unknown site {site_id!r}"}

        shifts = state.get(site_id, [])
        if not shifts:
            return {"error": "cannot post an empty draft; propose at least one shift first"}

        posted_at = clock()
        ordered = tuple(sorted(shifts, key=lambda s: s.starts_at))
        schedule = Schedule(
            site_id=site_id, week_starts_at=week_starts_at,
            posted_at=posted_at, shifts=ordered,
        )
        world.store_schedule(schedule)

        shift_ids = [s.shift_id for s in ordered]
        ledger.append({
            "kind": "post_schedule", "site_id": site_id,
            "shift_ids": shift_ids, "at": posted_at,
        })
        state[site_id] = list(ordered)
        return {"posted_at": posted_at.isoformat(), "site_id": site_id, "shift_ids": shift_ids}

    return [demand_for_week, list_workers, propose_shift, check_draft, post_schedule]
