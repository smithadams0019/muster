"""How much warning the worker got.

Measured from the moment the change is made to the *first day on the work
schedule*, not to the shift being changed. That is how the DCWP's own worked
examples compute it: a Thursday shift altered six days before the Monday the
schedule begins is priced from the Monday.

Boundaries are inclusive in the worker's favour at the top and exclusive at each
step down: a change made exactly at the notice window is full notice, exactly
seven days out is not yet "under seven days", exactly twenty-four hours out is not
yet "under twenty-four hours".
"""

from __future__ import annotations

from datetime import datetime, timedelta

from muster.domain.types import NoticeBand
from muster.rulebook.schema import Jurisdiction

_SEVEN_DAYS = timedelta(days=7)
_ONE_DAY = timedelta(hours=24)


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must carry a timezone; got a naive datetime")


def notice_band(
    posted_at: datetime,
    changed_at: datetime,
    schedule_starts_at: datetime,
    rules: Jurisdiction,
) -> NoticeBand:
    """Which band a change falls into under this jurisdiction's notice window."""
    for name, value in (("posted_at", posted_at), ("changed_at", changed_at),
                        ("schedule_starts_at", schedule_starts_at)):
        _require_aware(name, value)

    lead = schedule_starts_at - changed_at
    if lead >= timedelta(hours=rules.notice_hours):
        return NoticeBand.FULL_NOTICE
    if lead < _ONE_DAY:
        return NoticeBand.UNDER_24_HOURS
    if lead < _SEVEN_DAYS:
        return NoticeBand.UNDER_7_DAYS
    return NoticeBand.INSIDE_WINDOW
