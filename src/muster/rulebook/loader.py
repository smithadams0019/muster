"""Load jurisdiction rulebooks from data files.

Deliberately eager and cached: the whole rulebook is a few kilobytes, and a
lookup that can fail at request time on a filesystem error is a lookup that can
fail open. Loading at import means a malformed rulebook stops the process rather
than mispricing one worker's shift.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from muster.domain.types import CarveOut, ChangeKind, NoticeBand
from muster.rulebook.schema import CoverageTest, Jurisdiction, PremiumRule, RestRemedy

DATA = Path(__file__).parent / "data"


def _premium(raw: dict) -> PremiumRule:
    return PremiumRule(
        band=NoticeBand(raw["band"]),
        kinds=frozenset(ChangeKind(k) for k in raw["kinds"]),
        citation=raw["citation"],
        amount_cents=raw.get("amount_cents"),
        hours_at_rate=raw.get("hours_at_rate"),
        fraction_of_lost_hours=raw.get("fraction_of_lost_hours"),
    )


def _jurisdiction(raw: dict) -> Jurisdiction:
    return Jurisdiction(
        code=raw["code"],
        name=raw["name"],
        effective_from=date.fromisoformat(raw["effective_from"]),
        notice_hours=raw["notice_hours"],
        premiums=tuple(_premium(p) for p in raw["premiums"]),
        rest_hours=float(raw["rest_hours"]),
        rest_remedy=RestRemedy(**raw["rest_remedy"]),
        rest_requires_written_consent=raw["rest_requires_written_consent"],
        rest_has_carve_outs=raw["rest_has_carve_outs"],
        carve_outs=frozenset(CarveOut(c) for c in raw["carve_outs"]),
        coverage=CoverageTest(
            industries=frozenset(raw["coverage"]["industries"]),
            min_employees_worldwide=raw["coverage"]["min_employees_worldwide"],
        ),
        citation=raw["citation"],
    )


@lru_cache(maxsize=1)
def load_all() -> dict[str, list[Jurisdiction]]:
    """Every rulebook, keyed by code, each list sorted oldest version first."""
    by_code: dict[str, list[Jurisdiction]] = {}
    for path in sorted(DATA.glob("*.json")):
        rules = _jurisdiction(json.loads(path.read_text(encoding="utf-8")))
        by_code.setdefault(rules.code, []).append(rules)
    for versions in by_code.values():
        versions.sort(key=lambda j: j.effective_from)
    return by_code


def for_code(code: str, on: date) -> Jurisdiction:
    """The version of a jurisdiction's rulebook in force on a date.

    Raises rather than defaulting. A jurisdiction Muster does not know is not a
    jurisdiction with no rules; it is a jurisdiction Muster must not act in.
    """
    versions = load_all().get(code)
    if versions is None:
        raise KeyError(f"no rulebook for {code!r}")
    in_force = [v for v in versions if v.effective_from <= on]
    if not in_force:
        raise LookupError(f"no version of {code} was in force on {on.isoformat()}")
    return in_force[-1]
