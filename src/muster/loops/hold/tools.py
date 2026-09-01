"""The six tools the HOLD agent gets to cover a gap.

`list_cover_options` is the single place the agent's ranking is built, and it
prices every option with the same `price_change` the escalation policy's context
provider (`muster.loops.hold.context`) uses to judge the same call. That is the
whole point: the ranking the model sees and the judgement the policy makes are
computed from the same inputs, so they cannot disagree.

Every tool below re-validates its own identifiers against the world and, for
`assign_cover`, against the priced-option cache `list_cover_options` fills in.
A `{"error": ...}` dict is the refusal shape throughout - never a default, and
never an action taken on a value the model invented.

Money never rounds twice: the `CostBreakdown` an option was priced with is the
same object handed to `receipts.write(...)` when that option is assigned.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from strands import tool

from muster.adapters.base import WorldAdapter
from muster.domain.models import Schedule, Shift, Site, Worker
from muster.domain.options import enumerate_cover_options
from muster.domain.pricing import CostBreakdown, price_change
from muster.domain.types import ChangeKind, ConsentKind
from muster.persistence.consent import ConsentStore
from muster.persistence.receipts import ReceiptBook
from muster.rulebook.loader import for_code
from muster.rulebook.schema import Jurisdiction

Clock = Callable[[], datetime]


def _week_start(moment: datetime) -> datetime:
    monday = moment - timedelta(days=moment.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


class _Resolved:
    """The shift, its site, the rulebook in force and its posted schedule."""

    __slots__ = ("shift", "site", "rules", "week_start", "schedule")

    def __init__(self, shift: Shift, site: Site, rules: Jurisdiction,
                 week_start: datetime, schedule: Schedule) -> None:
        self.shift = shift
        self.site = site
        self.rules = rules
        self.week_start = week_start
        self.schedule = schedule


def _resolve_shift(
    world: WorldAdapter, clock: Clock, shift_id: str,
) -> tuple[_Resolved | None, str | None]:
    """Everything a price needs for `shift_id`, or an error a caller can return."""
    shift = world.shift(shift_id)
    if shift is None:
        return None, f"unknown shift_id {shift_id!r}"
    site = world.site(shift.site_id)
    if site is None:
        return None, f"shift {shift_id!r} belongs to an unknown site {shift.site_id!r}"
    try:
        rules = for_code(site.jurisdiction_code, on=clock().date())
    except (KeyError, LookupError) as exc:
        return None, str(exc)
    week_start = _week_start(shift.starts_at)
    schedule = world.schedule(site.site_id, week_start)
    if schedule is None or schedule.posted_at is None:
        return None, f"shift {shift_id!r} has no posted schedule to change"
    return _Resolved(shift, site, rules, week_start, schedule), None


def _price_add_shift(
    world: WorldAdapter, clock: Clock, resolved: _Resolved, worker: Worker, option: Any,
) -> CostBreakdown:
    """Price `worker` covering `resolved.shift`, exactly as the context provider does."""
    return price_change(
        rules=resolved.rules, kind=ChangeKind.ADD_SHIFT,
        posted_at=resolved.schedule.posted_at, changed_at=clock(),
        schedule_starts_at=resolved.week_start, hourly_rate=worker.hourly_rate,
        hours_lost=0.0, hours_worked=resolved.shift.hours,
        hours_before_this_week=resolved.schedule.hours_for(worker.worker_id),
        rest_gap_hours=option.rest_gap_hours if option else None,
        worker_id=worker.worker_id, shift_id=resolved.shift.shift_id,
        claims=option.claims if option else (), evidence=world,
    )


def build_hold_tools(
    world: WorldAdapter,
    ledger: list[dict[str, Any]],
    receipts: ReceiptBook,
    consent: ConsentStore,
    clock: Clock,
) -> list[Any]:
    """The six tools, closed over one world, one ledger and one priced-option cache."""

    #: option_id -> what it takes to honour it. Filled by `list_cover_options`, read
    #: by `explain_option` and `assign_cover`. Never trust an option_id that is not
    #: a key here - it is a value the model invented rather than one it was offered.
    priced: dict[str, dict[str, Any]] = {}

    def _find_option(shift: Shift, worker_id: str) -> Any:
        return next(
            (o for o in enumerate_cover_options(world, shift, at=clock())
             if o.worker_id == worker_id),
            None,
        )

    @tool
    def list_cover_options(shift_id: str) -> Any:
        """Every lawful way to cover shift_id, each already priced, cheapest first."""
        resolved, error = _resolve_shift(world, clock, shift_id)
        if error:
            return {"error": error}

        offers: list[dict[str, Any]] = []
        for option in enumerate_cover_options(world, resolved.shift, at=clock()):
            worker = world.worker(option.worker_id)
            if worker is None:
                continue
            breakdown = _price_add_shift(world, clock, resolved, worker, option)
            if not breakdown.lawful:
                continue

            priced[option.option_id] = {
                "shift_id": resolved.shift.shift_id,
                "worker_id": worker.worker_id,
                "site_id": resolved.site.site_id,
                "jurisdiction_code": resolved.site.jurisdiction_code,
                "rulebook_effective_from": resolved.rules.effective_from.isoformat(),
                "kind": option.kind,
                "breakdown": breakdown,
            }
            offers.append({
                "option_id": option.option_id,
                "worker_id": worker.worker_id,
                "worker_name": worker.name,
                "total_cents": breakdown.total.cents,
                "total": str(breakdown.total),
                "requires_consent": breakdown.requires_consent,
                "rest_gap_hours": option.rest_gap_hours,
                "carve_outs": [c.value for c in breakdown.carve_outs_applied],
                "clauses": [line.clause for line in breakdown.lines],
            })

        offers.sort(key=lambda o: (o["total_cents"], o["worker_name"]))
        return offers

    @tool
    def explain_option(option_id: str) -> Any:
        """The itemised breakdown for one option list_cover_options already offered."""
        cached = priced.get(option_id)
        if cached is None:
            return {"error": f"unknown option_id {option_id!r}; call list_cover_options first"}
        breakdown: CostBreakdown = cached["breakdown"]
        return {
            "option_id": option_id,
            "shift_id": cached["shift_id"],
            "worker_id": cached["worker_id"],
            "total_cents": breakdown.total.cents,
            "total": str(breakdown.total),
            "requires_consent": breakdown.requires_consent,
            "carve_outs": [c.value for c in breakdown.carve_outs_applied],
            "lines": [
                {"clause": line.clause, "citation": line.citation,
                 "amount_cents": line.amount.cents}
                for line in breakdown.lines
            ],
        }

    @tool
    def assign_cover(shift_id: str, worker_id: str, option_id: str) -> Any:
        """Write a priced cover into the ledger and a receipt.

        Only an option_id `list_cover_options` actually offered, for this exact
        shift and worker, is honoured; anything else is refused.
        """
        cached = priced.get(option_id)
        if cached is None:
            return {"error": f"unknown option_id {option_id!r}; call list_cover_options first"}
        if cached["shift_id"] != shift_id or cached["worker_id"] != worker_id:
            return {"error": f"option {option_id!r} was never offered for shift "
                              f"{shift_id!r} and worker {worker_id!r}"}

        breakdown: CostBreakdown = cached["breakdown"]
        at = clock()
        receipts.write(
            site_id=cached["site_id"], worker_id=worker_id, shift_id=shift_id,
            kind=cached["kind"], jurisdiction_code=cached["jurisdiction_code"],
            rulebook_effective_from=cached["rulebook_effective_from"],
            breakdown=breakdown, decided_by="muster", consent=None, at=at,
        )
        ledger.append({
            "kind": "assign_cover", "shift_id": shift_id, "worker_id": worker_id,
            "option_id": option_id, "total_cents": breakdown.total.cents,
            "site_id": cached["site_id"], "at": at.isoformat(),
        })
        return {"assigned": True, "shift_id": shift_id, "worker_id": worker_id,
                "option_id": option_id, "total_cents": breakdown.total.cents}

    @tool
    def request_consent(worker_id: str, shift_id: str, kind: str) -> Any:
        """Ask a worker for consent, stating the premium they would be owed."""
        resolved, error = _resolve_shift(world, clock, shift_id)
        if error:
            return {"error": error}
        worker = world.worker(worker_id)
        if worker is None:
            return {"error": f"unknown worker_id {worker_id!r}"}
        if world.has_declined(worker_id, shift_id) or consent.has_declined(worker_id, shift_id):
            return {"error": f"{worker.name} has already declined shift {shift_id!r}; "
                              "Muster does not ask twice."}
        try:
            consent_kind = ConsentKind(kind)
        except ValueError:
            return {"error": f"unknown consent kind {kind!r}"}

        option = _find_option(resolved.shift, worker_id)
        breakdown = _price_add_shift(world, clock, resolved, worker, option)

        try:
            request = consent.ask(
                worker_id=worker_id, shift_id=shift_id, kind=consent_kind,
                premium_owed=breakdown.total,
                what_it_means=f"Muster is asking you to cover shift {shift_id}.",
                asked_at=clock(), expires_in=timedelta(hours=4),
            )
        except PermissionError as exc:
            return {"error": str(exc)}

        return {
            "request_id": request.request_id, "worker_id": worker_id, "shift_id": shift_id,
            "kind": consent_kind.value, "what_it_means": request.what_it_means,
            "expires_at": request.expires_at.isoformat(),
        }

    @tool
    def notify_worker(worker_id: str, shift_id: str) -> Any:
        """Tell worker_id about a change to shift_id already recorded in the ledger."""
        worker = world.worker(worker_id)
        if worker is None:
            return {"error": f"unknown worker_id {worker_id!r}"}
        shift = world.shift(shift_id)
        if shift is None:
            return {"error": f"unknown shift_id {shift_id!r}"}
        return {
            "notified": True, "worker_id": worker_id, "shift_id": shift_id,
            "message": f"{worker.name}, you're covering shift {shift_id} "
                       f"({shift.starts_at:%A %H:%M}-{shift.ends_at:%H:%M}).",
        }

    @tool
    def cancel_shift(shift_id: str) -> Any:
        """Cancel shift_id outright, pricing the loss for whoever was assigned to it."""
        resolved, error = _resolve_shift(world, clock, shift_id)
        if error:
            return {"error": error}
        shift = resolved.shift
        if shift.worker_id is None:
            return {"error": f"shift {shift_id!r} has no assigned worker to cancel for"}
        worker = world.worker(shift.worker_id)
        if worker is None:
            return {"error": f"shift {shift_id!r} is assigned to an unknown worker "
                              f"{shift.worker_id!r}"}

        breakdown = price_change(
            rules=resolved.rules, kind=ChangeKind.CANCEL_SHIFT,
            posted_at=resolved.schedule.posted_at, changed_at=clock(),
            schedule_starts_at=resolved.week_start, hourly_rate=worker.hourly_rate,
            hours_lost=shift.hours, hours_worked=0.0,
            hours_before_this_week=max(
                0.0, resolved.schedule.hours_for(worker.worker_id) - shift.hours,
            ),
            rest_gap_hours=None, worker_id=worker.worker_id, shift_id=shift.shift_id,
            claims=(), evidence=world,
        )
        if not breakdown.lawful:
            return {"error": breakdown.unlawful_reason}

        at = clock()
        receipts.write(
            site_id=resolved.site.site_id, worker_id=worker.worker_id, shift_id=shift_id,
            kind=ChangeKind.CANCEL_SHIFT, jurisdiction_code=resolved.site.jurisdiction_code,
            rulebook_effective_from=resolved.rules.effective_from.isoformat(),
            breakdown=breakdown, decided_by="muster", consent=None, at=at,
        )
        ledger.append({
            "kind": "cancel_shift", "shift_id": shift_id, "worker_id": worker.worker_id,
            "total_cents": breakdown.total.cents, "site_id": resolved.site.site_id,
            "at": at.isoformat(),
        })
        return {"cancelled": True, "shift_id": shift_id, "worker_id": worker.worker_id,
                "total_cents": breakdown.total.cents}

    return [
        list_cover_options, explain_option, assign_cover,
        request_consent, notify_worker, cancel_shift,
    ]
