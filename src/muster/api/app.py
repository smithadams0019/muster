"""Muster's control plane: the FastAPI surface the console and the demo talk to.

The state lives on `app.state.muster`, a single process-wide `MusterState`
(Task 18's counterpart to a database). `hold_runner`, `draft_runner` and
`decision_resumer` are injected rather than imported directly, so tests can
swap the real Strands agents for fakes without touching a network or an AWS
credential. In production `create_app()` with no arguments wires the real
`run_hold`/`run_draft`/`resume_hold` functions.

The one property this module exists to hold: `POST /api/decisions/{id}/answer`
does not just record who said what. It awaits the resumer and acts on what
comes back. Recording the human and never resuming the run is the exact bug
this task was written to prevent - see the module docstring in
`tests/api/test_app.py` for the story.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from muster.adapters.base import WorldAdapter
from muster.api.state import MusterState
from muster.domain.models import Disruption
from muster.domain.types import AutonomyLevel, ConsentOutcome, DecisionOutcome, DisruptionKind
from muster.loops.draft.runner import (
    build_default_policy as build_default_draft_policy,
    build_draft_agent,
    run_draft,
)
from muster.loops.hold.runner import (
    HoldRunResult,
    build_default_policy as build_default_hold_policy,
    build_hold_agent,
    describe_disruption,
    resume_hold,
    run_hold,
)
from muster.persistence.inbox import Decision, PendingDecision
from muster.policy.rules import THRESHOLDS
from muster.rulebook.loader import for_code

RunResult = Any
HoldRunnerFn = Callable[[MusterState, Disruption], Awaitable[RunResult]]
DraftRunnerFn = Callable[[MusterState, str], Awaitable[RunResult]]
DecisionResumerFn = Callable[[MusterState, PendingDecision], Awaitable[RunResult]]


# -- default runners, wiring the real agents ---------------------------------


async def _default_hold_runner(state: MusterState, disruption: Disruption) -> RunResult:
    policy = build_default_hold_policy(state.world, state.ledger, state.consent, state.autonomy)
    agent = build_hold_agent(
        state.world, state.ledger, state.receipts, state.consent, policy, state.trail,
    )
    prompt = describe_disruption(state.world, disruption)
    return await run_hold(agent, prompt, policy)


async def _default_draft_runner(state: MusterState, site_id: str) -> RunResult:
    week_starts_at = _next_week_start(state.world)
    policy = build_default_draft_policy(state.world, {}, week_starts_at, state.autonomy)
    agent = build_draft_agent(
        state.world, state.ledger, week_starts_at, state.world.now, policy, state.trail,
    )
    prompt = f"Draft the week beginning {week_starts_at:%Y-%m-%d} for {site_id}."
    return await run_draft(agent, prompt, policy)


async def _default_decision_resumer(state: MusterState, pending: PendingDecision) -> RunResult:
    policy = build_default_hold_policy(state.world, state.ledger, state.consent, state.autonomy)
    agent = build_hold_agent(
        state.world, state.ledger, state.receipts, state.consent, policy, state.trail,
    )
    decision = pending.decision
    decision_record = {
        "outcome": decision.outcome.value if decision.outcome else None,
        "by": decision.by,
        "role": decision.role,
        "note": decision.note,
    }
    return await resume_hold(agent, pending.snapshot, pending.interrupt_id, decision_record, policy)


def _next_week_start(world: WorldAdapter) -> datetime:
    """The Monday on or after the world's clock, at midnight."""
    now = world.now()
    days_ahead = (7 - now.weekday()) % 7
    monday = now + timedelta(days=days_ahead)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


# -- request/response models --------------------------------------------------


class DisruptionIn(BaseModel):
    kind: DisruptionKind
    shift_id: str
    note: str = ""


class DecisionAnswerIn(BaseModel):
    outcome: DecisionOutcome
    by: str
    role: str
    note: str = ""


class ConsentAnswerIn(BaseModel):
    outcome: ConsentOutcome
    channel: str = "console"


class AutonomyIn(BaseModel):
    level: AutonomyLevel


# -- helpers shared by routes --------------------------------------------------


def _open_decision(state: MusterState, offer_id: str, result: RunResult) -> str:
    """Park a paused run in the inbox and return the new decision id."""
    decision_id = f"dec-{uuid.uuid4().hex[:8]}"
    decision = Decision(
        decision_id=decision_id,
        offer_id=offer_id,
        rule=result.interrupt_reason or "unknown",
        prompt=result.text,
    )
    state.inbox.open(
        decision,
        interrupt_id=result.interrupt_id,
        snapshot=result.snapshot or {},
        rule_hits=result.rule_hits,
    )
    return decision_id


def _shift_is_covered(state: MusterState, shift_id: str, result: RunResult) -> bool:
    """Coverage is read from the ledger, never guessed from a run's exit status.

    A run can assign a cover and then pause on a later step (the notification),
    so the ledger is authoritative: `assign_cover` always writes an entry here
    before anything else happens. The result's own text is consulted only when
    the ledger carries no evidence at all for this shift.
    """
    if any(
        entry.get("kind") == "assign_cover" and entry.get("shift_id") == shift_id
        for entry in state.ledger
    ):
        return True
    return "cover" in (result.text or "").lower()


def _serialize_pending(pending: PendingDecision) -> dict[str, Any]:
    decision = pending.decision
    return {
        "decision_id": decision.decision_id,
        "offer_id": decision.offer_id,
        "rule": decision.rule,
        "prompt": decision.prompt,
        "rule_hits": pending.rule_hits,
        "outcome": decision.outcome.value if decision.outcome else None,
        "by": decision.by,
        "role": decision.role,
        "note": decision.note,
    }


def _serialize_receipt(receipt: Any) -> dict[str, Any]:
    return {
        "at": receipt.at.isoformat(),
        "site_id": receipt.site_id,
        "worker_id": receipt.worker_id,
        "shift_id": receipt.shift_id,
        "kind": receipt.kind.value,
        "jurisdiction_code": receipt.jurisdiction_code,
        "rulebook_effective_from": receipt.rulebook_effective_from,
        "lines": [
            {"clause": line.clause, "citation": line.citation, "amount": line.amount.dollars}
            for line in receipt.lines
        ],
        "total": receipt.total.dollars,
        "carve_outs_applied": [c.value for c in receipt.carve_outs_applied],
        "decided_by": receipt.decided_by,
        "consent": (
            {
                "outcome": receipt.consent.outcome.value,
                "answered_at": (
                    receipt.consent.answered_at.isoformat() if receipt.consent.answered_at else None
                ),
            }
            if receipt.consent
            else None
        ),
    }


# -- the app --------------------------------------------------------------------


def create_app(
    hold_runner: HoldRunnerFn | None = None,
    draft_runner: DraftRunnerFn | None = None,
    decision_resumer: DecisionResumerFn | None = None,
) -> FastAPI:
    hold_runner = hold_runner or _default_hold_runner
    draft_runner = draft_runner or _default_draft_runner
    decision_resumer = decision_resumer or _default_decision_resumer

    app = FastAPI(title="Muster")
    app.state.muster = MusterState()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/world")
    def get_world() -> dict[str, Any]:
        state: MusterState = app.state.muster
        world = state.world
        now = world.now()
        sites = [
            {
                "site_id": site.site_id,
                "name": site.name,
                "jurisdiction_code": site.jurisdiction_code,
                "opens_at_hour": site.opens_at_hour,
                "closes_at_hour": site.closes_at_hour,
            }
            for site in world.sites()
        ]
        jurisdictions = {
            site.jurisdiction_code: for_code(site.jurisdiction_code, on=now.date())
            for site in world.sites()
        }
        return {
            "now": now.isoformat(),
            "sites": sites,
            "workers": [
                {
                    "worker_id": worker.worker_id,
                    "name": worker.name,
                    "site_id": worker.site_id,
                    "role": worker.role.value,
                    "hourly_rate": worker.hourly_rate.dollars,
                    "good_faith_hours": worker.good_faith_hours,
                }
                for worker in world.workers()
            ],
            "jurisdictions": [
                {
                    "code": rules.code,
                    "name": rules.name,
                    "effective_from": rules.effective_from.isoformat(),
                    "citation": rules.citation,
                }
                for rules in jurisdictions.values()
            ],
        }

    @app.get("/api/schedule/{site_id}")
    def get_schedule(site_id: str) -> dict[str, Any]:
        state: MusterState = app.state.muster
        week_starts_at = _next_week_start(state.world)
        schedule = state.world.schedule(site_id, week_starts_at)
        if schedule is None:
            raise HTTPException(status_code=404, detail=f"no schedule for {site_id!r}")
        return {
            "site_id": schedule.site_id,
            "week_starts_at": schedule.week_starts_at.isoformat(),
            "posted_at": schedule.posted_at.isoformat() if schedule.posted_at else None,
            "shifts": [
                {
                    "shift_id": shift.shift_id,
                    "role": shift.role.value,
                    "starts_at": shift.starts_at.isoformat(),
                    "ends_at": shift.ends_at.isoformat(),
                    "worker_id": shift.worker_id,
                }
                for shift in schedule.shifts
            ],
        }

    @app.post("/api/draft/{site_id}")
    async def post_draft(site_id: str) -> dict[str, Any]:
        state: MusterState = app.state.muster
        result = await draft_runner(state, site_id)
        if result.paused:
            decision_id = _open_decision(state, site_id, result)
            return {"status": "awaiting_decision", "decision_id": decision_id}
        return {"status": "drafted", "text": result.text}

    @app.post("/api/disruptions")
    async def post_disruption(payload: DisruptionIn) -> dict[str, Any]:
        state: MusterState = app.state.muster
        disruption = Disruption(
            disruption_id=f"dis-{uuid.uuid4().hex[:8]}",
            kind=payload.kind,
            shift_id=payload.shift_id,
            reported_at=state.world.now(),
            note=payload.note,
        )
        result = await hold_runner(state, disruption)
        if result.paused:
            decision_id = _open_decision(state, disruption.shift_id, result)
            return {"status": "awaiting_decision", "decision_id": decision_id}
        covered = _shift_is_covered(state, disruption.shift_id, result)
        return {"status": "covered" if covered else "uncovered"}

    @app.get("/api/decisions")
    def get_decisions() -> list[dict[str, Any]]:
        state: MusterState = app.state.muster
        return [_serialize_pending(p) for p in state.inbox.pending()]

    @app.post("/api/decisions/{decision_id}/answer")
    async def answer_decision(decision_id: str, payload: DecisionAnswerIn) -> dict[str, Any]:
        state: MusterState = app.state.muster
        if state.inbox.get(decision_id) is None:
            raise HTTPException(status_code=404, detail=f"no pending decision {decision_id!r}")

        pending = state.inbox.answer(
            decision_id, payload.outcome, by=payload.by, role=payload.role, note=payload.note,
        )

        result = await decision_resumer(state, pending)

        if result.paused:
            new_id = _open_decision(state, pending.decision.offer_id, result)
            return {"status": "awaiting_decision", "decision_id": new_id}

        covered = _shift_is_covered(state, pending.decision.offer_id, result)
        return {"status": "covered" if covered else "uncovered"}

    @app.get("/api/consent")
    def get_consent() -> list[dict[str, Any]]:
        state: MusterState = app.state.muster
        return [
            {
                "request_id": request.request_id,
                "worker_id": request.worker_id,
                "shift_id": request.shift_id,
                "kind": request.kind.value,
                "premium_owed": request.premium_owed.dollars,
                "what_it_means": request.what_it_means,
                "asked_at": request.asked_at.isoformat(),
                "expires_at": request.expires_at.isoformat(),
            }
            for request in state.consent.pending()
        ]

    @app.post("/api/consent/{request_id}/answer")
    def answer_consent(request_id: str, payload: ConsentAnswerIn) -> dict[str, Any]:
        state: MusterState = app.state.muster
        try:
            record = state.consent.answer(
                request_id, payload.outcome, answered_at=state.world.now(), channel=payload.channel,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"request_id": request_id, "outcome": record.outcome.value}

    @app.get("/api/receipts")
    def get_receipts() -> list[dict[str, Any]]:
        state: MusterState = app.state.muster
        return [_serialize_receipt(r) for r in state.receipts.all()]

    @app.get("/api/receipts.csv")
    def get_receipts_csv() -> Response:
        state: MusterState = app.state.muster
        return Response(
            content=state.receipts.to_csv(),
            media_type="text/csv",
            headers={"content-disposition": "attachment; filename=receipts.csv"},
        )

    @app.get("/api/timeline")
    def get_timeline() -> list[dict[str, Any]]:
        state: MusterState = app.state.muster
        return [
            {
                "kind": entry.kind,
                "label": entry.label,
                "at": entry.at.isoformat(),
                "detail": entry.detail,
            }
            for entry in state.trail.entries()
        ]

    @app.get("/api/autonomy")
    def get_autonomy() -> dict[str, Any]:
        state: MusterState = app.state.muster
        thresholds = THRESHOLDS[state.autonomy]
        return {
            "level": state.autonomy.value,
            "thresholds": {
                "max_unattended_cents": thresholds.max_unattended_cents,
                "weekly_budget_cents": thresholds.weekly_budget_cents,
                "max_overtime_hours": thresholds.max_overtime_hours,
                "max_shortfall_fraction": thresholds.max_shortfall_fraction,
            },
        }

    @app.put("/api/autonomy")
    def put_autonomy(payload: AutonomyIn) -> dict[str, Any]:
        state: MusterState = app.state.muster
        state.autonomy = payload.level
        return get_autonomy()

    return app
