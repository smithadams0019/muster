"""Muster's compliance engine, served over MCP.

The rulebook and the cost engine are the most reusable part of this project and
the safest to expose: deterministic, side-effect free, no credentials, no model in
the path. An operator who already has scheduling software can take the reasoning
without taking the app.

Read-only, deliberately. Nothing here can move a shift, post a schedule or record
a consent. Those live behind the escalation policy inside Muster, where a human's
authority is modelled. A protocol that let a stranger's agent reassign somebody's
Tuesday would be a different and much worse product.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from mcp.server.fastmcp import FastMCP

from muster.domain.carve_outs import CarveOutClaim
from muster.domain.pricing import price_change
from muster.domain.rest import breaches_rest, rest_gap_hours, rest_remedy_owed
from muster.domain.types import ChangeKind, Money
from muster.rulebook.loader import for_code, load_all


class _NoEvidence:
    """The protocol over MCP carries no world, so no carve-out can be evidenced."""

    def worker_requested(self, worker_id, shift_id): return False
    def on_standby_list(self, worker_id): return False
    def standby_accepted(self, worker_id, shift_id): return False
    def trade_accepted_by_both(self, shift_id, a, b): return False
    def written_agreement(self, evidence_id): return False
    def declared_incident(self, evidence_id): return None


def build_server() -> FastMCP:
    server = FastMCP("muster")

    @server.tool()
    def list_jurisdictions() -> list[dict]:
        """Every fair-workweek rulebook Muster has encoded, with the effective date
        of each version and the government source its figures were read from."""
        return [
            {"code": j.code, "name": j.name,
             "effective_from": j.effective_from.isoformat(),
             "notice_hours": j.notice_hours, "rest_hours": j.rest_hours,
             "citation": j.citation}
            for versions in load_all().values() for j in versions
        ]

    @server.tool()
    def get_rules(jurisdiction: str, on: str | None = None) -> dict:
        """The full rulebook in force for a jurisdiction on a date: notice window,
        premium schedule, rest period and remedy, carve-outs, and citations."""
        rules = for_code(jurisdiction, on=date.fromisoformat(on) if on else date.today())
        return {
            "code": rules.code, "name": rules.name,
            "effective_from": rules.effective_from.isoformat(),
            "notice_hours": rules.notice_hours,
            "rest_hours": rules.rest_hours,
            "rest_requires_written_consent": rules.rest_requires_written_consent,
            "rest_has_carve_outs": rules.rest_has_carve_outs,
            "carve_outs": sorted(c.value for c in rules.carve_outs),
            "premiums": [
                {"band": p.band.value, "kinds": sorted(k.value for k in p.kinds),
                 "amount_cents": p.amount_cents, "hours_at_rate": p.hours_at_rate,
                 "fraction_of_lost_hours": p.fraction_of_lost_hours,
                 "citation": p.citation}
                for p in rules.premiums
            ],
            "citation": rules.citation,
        }

    @server.tool()
    def price_schedule_change(
        jurisdiction: str,
        posted_at: str,
        changed_at: str,
        schedule_starts_at: str,
        change_kind: str,
        hourly_rate_dollars: str,
        hours_lost: float = 0.0,
        hours_worked: float = 0.0,
        hours_before_this_week: float = 0.0,
        rest_gap_hours_value: float | None = None,
    ) -> dict:
        """What one change to a posted schedule owes under a jurisdiction's
        ordinance, itemised by the clause that produced each line. Timestamps are
        ISO-8601 with an offset. Carve-outs are not applied here: they require
        evidence this protocol does not carry."""
        rules = for_code(jurisdiction, on=datetime.fromisoformat(changed_at).date())
        breakdown = price_change(
            rules=rules, kind=ChangeKind(change_kind),
            posted_at=datetime.fromisoformat(posted_at),
            changed_at=datetime.fromisoformat(changed_at),
            schedule_starts_at=datetime.fromisoformat(schedule_starts_at),
            hourly_rate=Money.from_dollars(hourly_rate_dollars),
            hours_lost=hours_lost, hours_worked=hours_worked,
            hours_before_this_week=hours_before_this_week,
            rest_gap_hours=rest_gap_hours_value,
            worker_id="mcp", shift_id="mcp",
            claims=(), evidence=_NoEvidence(),
        )
        return {
            "jurisdiction": rules.code,
            "total": breakdown.total.dollars,
            "total_cents": breakdown.total.cents,
            "lawful": breakdown.lawful,
            "unlawful_reason": breakdown.unlawful_reason,
            "requires_consent": breakdown.requires_consent,
            "lines": [
                {"clause": line.clause, "citation": line.citation,
                 "amount": line.amount.dollars}
                for line in breakdown.lines
            ],
        }

    @server.tool()
    def check_rest(
        jurisdiction: str,
        previous_shift_end: str,
        next_shift_start: str,
        hourly_rate_dollars: str,
        hours_worked: float,
        overtime_hours: float = 0.0,
    ) -> dict:
        """The gap between two shifts, whether it breaches the protected rest
        period, the premium owed if the worker agrees to it, whether written
        consent is required, and whether the jurisdiction allows any exception."""
        rules = for_code(jurisdiction, on=datetime.fromisoformat(next_shift_start).date())
        gap = rest_gap_hours(datetime.fromisoformat(previous_shift_end),
                             datetime.fromisoformat(next_shift_start))
        breaches = breaches_rest(gap, rules)
        remedy = rest_remedy_owed(hours_worked, overtime_hours,
                                  Money.from_dollars(hourly_rate_dollars), rules)
        return {
            "jurisdiction": rules.code,
            "gap_hours": round(gap, 2),
            "protected_hours": rules.rest_hours,
            "breaches": breaches,
            "premium_if_worked": remedy.dollars if breaches else "0.00",
            "written_consent_required": rules.rest_requires_written_consent and breaches,
            "carve_outs_available": rules.rest_has_carve_outs,
            "note": ("This jurisdiction allows no exceptions to the rest rule."
                     if not rules.rest_has_carve_outs else ""),
            "citation": rules.citation,
        }

    @server.tool()
    def audit_schedule(jurisdiction: str, posted_at: str, schedule_starts_at: str,
                       shifts_json: str, hourly_rate_dollars: str) -> dict:
        """Every rest breach across a whole posted week. `shifts_json` is a JSON
        list of {worker_id, starts_at, ends_at} with ISO-8601 timestamps."""
        rules = for_code(jurisdiction, on=datetime.fromisoformat(posted_at).date())
        shifts = json.loads(shifts_json)
        by_worker: dict[str, list[dict]] = {}
        for shift in shifts:
            by_worker.setdefault(shift["worker_id"], []).append(shift)

        findings = []
        for worker_id, worker_shifts in by_worker.items():
            worker_shifts.sort(key=lambda s: s["starts_at"])
            for earlier, later in zip(worker_shifts, worker_shifts[1:]):
                gap = rest_gap_hours(datetime.fromisoformat(earlier["ends_at"]),
                                     datetime.fromisoformat(later["starts_at"]))
                if breaches_rest(gap, rules):
                    findings.append({
                        "worker_id": worker_id, "gap_hours": round(gap, 2),
                        "between": [earlier["ends_at"], later["starts_at"]],
                        "premium_owed": rest_remedy_owed(
                            (datetime.fromisoformat(later["ends_at"])
                             - datetime.fromisoformat(later["starts_at"])).total_seconds() / 3600,
                            0.0, Money.from_dollars(hourly_rate_dollars), rules).dollars,
                    })
        return {"jurisdiction": rules.code, "rest_breaches": findings,
                "citation": rules.citation}

    @server.resource("muster://rulebook/{code}")
    def rulebook(code: str) -> str:
        """The cited rulebook itself, so a client can read the rules rather than
        trusting a summary of them."""
        return json.dumps(get_rules(code), indent=2)

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
