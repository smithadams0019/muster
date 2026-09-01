"""Raising autonomy must never increase escalations.

A dial that surfaces *more* decisions as you trust it more is not a dial; it is a
bug that would train an operator to distrust the setting.
"""

import itertools

from muster.domain.types import AutonomyLevel, Money
from muster.policy.rules import CoverContext, evaluate

LEVELS = [AutonomyLevel.CONSERVATIVE, AutonomyLevel.BALANCED, AutonomyLevel.TRUSTED]


def _contexts():
    for cost in ("0.00", "10.00", "75.00", "120.00", "300.00"):
        for overtime in (0.0, 1.0, 3.0, 7.0):
            for shortfall in (0.0, 0.05, 0.15, 0.30):
                yield CoverContext(
                    cost=Money.from_dollars(cost), week_spend=Money.zero(),
                    overtime_hours=overtime, shortfall_fraction=shortfall,
                    requires_rest_waiver=False, worker_declined=False,
                    meets_role_minimum=True, meets_certification_minimum=True,
                    assessable=True,
                )


def test_escalations_never_increase_as_autonomy_rises():
    for context in _contexts():
        counts = [len(evaluate(context, level)) for level in LEVELS]
        assert counts == sorted(counts, reverse=True), (context, counts)


def test_every_rule_that_fires_at_trusted_also_fires_at_conservative():
    for context in _contexts():
        trusted = {h.rule for h in evaluate(context, AutonomyLevel.TRUSTED)}
        conservative = {h.rule for h in evaluate(context, AutonomyLevel.CONSERVATIVE)}
        assert trusted <= conservative, context
