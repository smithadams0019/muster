from datetime import datetime, timezone

from muster.adapters.simulated import SableCoffee
from muster.domain.types import AutonomyLevel
from muster.loops.hold.context import build_hold_context_provider
from muster.persistence.consent import ConsentStore

TZ = timezone.utc


def _provider(level=AutonomyLevel.BALANCED, ledger=None):
    world = SableCoffee()
    return world, build_hold_context_provider(world, ledger if ledger is not None else [],
                                              ConsentStore(), level)


def test_an_unguarded_tool_needs_no_context():
    _, provider = _provider()
    assert provider("list_cover_options", {}) is None


def test_the_cost_comes_from_the_world_not_from_the_agents_arguments():
    """An agent that understates the premium is judged on the real one."""
    world, provider = _provider()
    schedule = world.schedule("site-nyc", datetime(2026, 7, 27, tzinfo=TZ))
    shift = next(s for s in schedule.shifts if s.starts_at.hour == 7)
    context = provider("assign_cover", {
        "shift_id": shift.shift_id, "worker_id": "w-nyc-3", "total_cents": 0,
    })
    assert context is not None
    assert context.cost.cents > 0


def test_a_prior_decline_is_read_from_the_world_even_if_the_agent_omits_it():
    world, provider = _provider()
    schedule = world.schedule("site-or", datetime(2026, 7, 27, tzinfo=TZ))
    shift = next(s for s in schedule.shifts if s.starts_at.hour == 7)
    world.record_decline("w-or-2", shift.shift_id)
    context = provider("assign_cover", {"shift_id": shift.shift_id, "worker_id": "w-or-2"})
    assert context.worker_declined is True


def test_an_unresolvable_shift_yields_no_context_so_the_policy_escalates():
    _, provider = _provider()
    assert provider("assign_cover", {"shift_id": "s-nope", "worker_id": "w-or-1"}) is None


def test_the_week_spend_is_summed_from_the_ledger():
    ledger = [{"kind": "assign_cover", "site_id": "site-or", "total_cents": 12000,
               "shift_id": "s-x", "worker_id": "w-x"}]
    world, provider = _provider(ledger=ledger)
    schedule = world.schedule("site-or", datetime(2026, 7, 27, tzinfo=TZ))
    shift = next(s for s in schedule.shifts if s.starts_at.hour == 7)
    context = provider("assign_cover", {"shift_id": shift.shift_id, "worker_id": "w-or-2"})
    assert context.week_spend.cents == 12000
