"""``muster-demo`` — one seeded sick call, run through the whole HOLD loop.

This is what a judge without a browser sees. It builds the frozen Sable Coffee
demo world (see ``muster.adapters.simulated``), prices every lawful way to cover
a 6am sick call at the Portland site using the exact tools the HOLD agent uses
(``muster.loops.hold.tools.build_hold_tools``), prints each option with its price
and the clause that produced it, and then runs the real agent loop
(``muster.loops.hold.runner.run_hold``) against live Amazon Bedrock and prints the
outcome: either a lawful cover assigned without waking anyone, or a pause with the
priced options an operator would see.

It makes a live model call, so it is guarded: with no AWS credentials configured,
it prints a clear one-paragraph explanation and exits with a non-zero status
instead of dying partway through a stack trace.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from muster.adapters.simulated import SableCoffee
from muster.domain.models import Disruption
from muster.domain.types import AutonomyLevel, DisruptionKind
from muster.hooks.audit import AuditTrail
from muster.loops.hold.runner import (
    MODEL_ID,
    REGION,
    build_default_policy,
    build_hold_agent,
    describe_disruption,
    run_hold,
)
from muster.loops.hold.tools import build_hold_tools
from muster.persistence.consent import ConsentStore
from muster.persistence.receipts import ReceiptBook

# The Monday 07:00 open at Sable Pearl (Portland, OR) — the same shift the
# spec's Scenario 1 covers. Sam (w-or-3) is booked to open it; Morgan (w-or-5)
# is one of the site's two standby-list workers.
SITE_ID = "site-or"
WEEK_START = datetime(2026, 7, 27, tzinfo=timezone.utc)
STANDBY_WORKER_ID = "w-or-5"


def _rule(char: str = "-") -> str:
    return char * 72


def _credentials_problem() -> str | None:
    """A one-paragraph explanation if Bedrock plainly cannot be reached, else None.

    This checks only whether *some* credentials are configured, not whether they
    are valid or the account has Bedrock access — the model call itself is the
    only thing that can confirm that, and that failure is caught separately
    around the invocation below.
    """
    try:
        import boto3
    except ImportError:
        return (
            "boto3 is not installed. muster-demo needs the package installed with\n"
            "its dependencies:\n\n    pip install -e .\n"
        )
    session = boto3.Session()
    if session.get_credentials() is None:
        return (
            "No AWS credentials found.\n\n"
            f"muster-demo makes a live call to Amazon Bedrock (model {MODEL_ID!r} "
            f"in region {REGION!r}) to run the HOLD agent for real. Configure "
            "credentials for an AWS account with Bedrock access — environment "
            "variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / "
            "AWS_SESSION_TOKEN), `aws configure`, or an assumed role — and run "
            "muster-demo again."
        )
    return None


def _print_options(world: SableCoffee, shift_id: str) -> None:
    """Every lawful cover for `shift_id`, priced by the exact tools the agent
    uses (`build_hold_tools`), cheapest first, with the clause behind each price.

    Built on a throwaway ledger and receipt book: `list_cover_options` and
    `explain_option` never write anything, so nothing here touches the ledger
    or receipts the real agent run below produces.
    """
    list_cover_options, explain_option, *_ = build_hold_tools(
        world, ledger=[], receipts=ReceiptBook(), consent=ConsentStore(), clock=world.now,
    )
    offers = list_cover_options(shift_id)
    if isinstance(offers, dict) and "error" in offers:
        print(f"  (could not enumerate options: {offers['error']})")
        return

    for offer in offers:
        detail = explain_option(offer["option_id"])
        consent_note = " — needs the worker's consent" if offer["requires_consent"] else ""
        carve_note = f" [{', '.join(offer['carve_outs'])}]" if offer["carve_outs"] else ""
        print(f"  {offer['total']:>8}  {offer['worker_name']}{carve_note}{consent_note}")
        for line in detail["lines"]:
            print(f"            {line['clause']} — {line['citation']}")
        if not detail["lines"]:
            print("            no charge — the carve-out zeroes this option")


def _print_outcome(ledger: list[dict], receipts: ReceiptBook, result) -> None:
    print(_rule())
    if result.paused:
        print(f"HELD — {result.interrupt_reason}")
        print()
        for hit in result.rule_hits:
            print(f"  [{hit['rule']}] {hit['detail']}")
        print()
        print("Nothing was assigned. This is exactly what the console would show an")
        print("operator: the priced options above, and why Muster will not pick one alone.")
        return

    print("RESOLVED — Muster covered the shift without waking anyone.")
    print()
    print(result.text)
    assigned = [e for e in ledger if e["kind"] == "assign_cover"]
    for entry in assigned:
        print(
            f"\n  assigned {entry['worker_id']} to {entry['shift_id']} "
            f"for {entry['total_cents'] / 100:.2f} USD"
        )
    for receipt in receipts.all():
        print(f"  receipt written: {receipt.jurisdiction_code}, decided by {receipt.decided_by}")


async def _run() -> int:
    world = SableCoffee()
    schedule = world.schedule(SITE_ID, WEEK_START)
    shift = next(s for s in schedule.shifts if s.starts_at.hour == 7 and s.starts_at.weekday() == 0)
    caller = world.worker(shift.worker_id)

    # Scenario 1 from the design spec: the standby worker has already agreed by
    # the time Muster is asked to cover the shift. This is evidence recorded in
    # the world, not a claim the agent makes — the same guarantee the escalation
    # policy and MCP server both rely on.
    world.record_standby_acceptance(STANDBY_WORKER_ID, shift.shift_id)

    disruption = Disruption(
        disruption_id="d-demo-1",
        kind=DisruptionKind.SICK_CALL,
        shift_id=shift.shift_id,
        reported_at=world.now(),
        note="flu",
    )

    site = world.site(SITE_ID)
    print(_rule("="))
    print("MUSTER — one seeded sick call through the HOLD loop")
    print(_rule("="))
    print(f"{site.name} · {site.jurisdiction_code} · world clock {world.now().isoformat()}")
    print(f"{caller.name} called in sick for {shift.shift_id} "
          f"({shift.starts_at:%A %H:%M}–{shift.ends_at:%H:%M})")
    print()
    print("Every lawful cover, priced by the same functions the agent will use:")
    print()
    _print_options(world, shift.shift_id)
    print()
    print(_rule())
    print("Handing this to the HOLD agent (live Bedrock call)...")
    print()

    # `PostingDependencyGuard` requires a `post_schedule` ledger entry before it
    # will let HOLD touch a shift — the record, in the DRAFT loop's own words,
    # that this week actually went out to workers. Demo.py runs HOLD on its own,
    # so it seeds the one fact DRAFT would already have written: this site's
    # week (`schedule.posted_at` is set — see `SableCoffee`) is posted.
    ledger: list[dict] = [
        {"kind": "post_schedule", "site_id": SITE_ID,
         "shift_ids": [s.shift_id for s in schedule.shifts]},
    ]
    consent = ConsentStore()
    receipts = ReceiptBook()
    policy = build_default_policy(world, ledger, consent, AutonomyLevel.BALANCED)
    agent = build_hold_agent(world, ledger, receipts, consent, policy, AuditTrail())

    prompt = describe_disruption(world, disruption)
    result = await run_hold(agent, prompt, policy)
    _print_outcome(ledger, receipts, result)
    return 0


def main() -> None:
    problem = _credentials_problem()
    if problem is not None:
        print(problem, file=sys.stderr)
        raise SystemExit(1)

    try:
        exit_code = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — this is the top-level CLI entry point
        import botocore.exceptions as bce

        if isinstance(exc, (bce.NoCredentialsError, bce.ClientError, bce.EndpointConnectionError)):
            print(
                "\nCould not complete the live Bedrock call:\n\n"
                f"  {exc}\n\n"
                f"Check that the credentials in scope belong to an account with access "
                f"to model {MODEL_ID!r} in region {REGION!r}.",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        raise
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
