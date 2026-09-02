"""Consent as a record, not a checkbox.

Three properties this store exists to hold, each of which is a legal requirement
somewhere in the shipped rulebooks rather than a preference:

* A decline is final for that shift. Re-asking until someone gives in is how
  consent stops meaning anything, so asking again raises.
* Silence is a decline. An expired request is never a grant.
* The ask states the money. NYC defines consent as agreement after a meaningful
  opportunity to decline, and an opportunity to decline without knowing the $100
  you are owed is not meaningful.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from muster.domain.types import ConsentKind, ConsentOutcome, Money


@dataclass(frozen=True)
class ConsentRequest:
    request_id: str
    worker_id: str
    shift_id: str
    kind: ConsentKind
    premium_owed: Money
    what_it_means: str
    asked_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class ConsentRecord:
    request: ConsentRequest
    outcome: ConsentOutcome
    answered_at: datetime | None
    channel: str


class ConsentStore:
    def __init__(self) -> None:
        self._pending: dict[str, ConsentRequest] = {}
        self._answered: dict[str, ConsentRecord] = {}
        self._declined: set[tuple[str, str]] = set()

    def ask(
        self,
        *,
        worker_id: str,
        shift_id: str,
        kind: ConsentKind,
        premium_owed: Money,
        what_it_means: str,
        asked_at: datetime,
        expires_in: timedelta,
    ) -> ConsentRequest:
        if self.has_declined(worker_id, shift_id):
            raise PermissionError(
                f"{worker_id} has already declined {shift_id}; asking again is not permitted"
            )
        request = ConsentRequest(
            request_id=f"con-{uuid.uuid4().hex[:8]}",
            worker_id=worker_id,
            shift_id=shift_id,
            kind=kind,
            premium_owed=premium_owed,
            what_it_means=f"{what_it_means} You would be owed {premium_owed} if you accept.",
            asked_at=asked_at,
            expires_at=asked_at + expires_in,
        )
        self._pending[request.request_id] = request
        return request

    def answer(
        self, request_id: str, outcome: ConsentOutcome, *, answered_at: datetime, channel: str
    ) -> ConsentRecord:
        if request_id in self._answered:
            raise KeyError(f"{request_id} was already answered")
        request = self._pending.pop(request_id, None)
        if request is None:
            raise KeyError(f"no pending consent request {request_id!r}")
        record = ConsentRecord(request, outcome, answered_at, channel)
        self._answered[request_id] = record
        if outcome is not ConsentOutcome.GRANTED:
            self._declined.add((request.worker_id, request.shift_id))
        return record

    def expire_due(self, now: datetime) -> list[ConsentRecord]:
        """Turn every lapsed request into a decline. Silence is never a grant."""
        expired = [r for r in self._pending.values() if r.expires_at <= now]
        records = []
        for request in expired:
            self._pending.pop(request.request_id)
            record = ConsentRecord(request, ConsentOutcome.EXPIRED, None, "expired")
            self._answered[request.request_id] = record
            self._declined.add((request.worker_id, request.shift_id))
            records.append(record)
        return records

    def pending(self) -> list[ConsentRequest]:
        return list(self._pending.values())

    def answered(self) -> list[ConsentRecord]:
        """Every ask that has been settled, newest first.

        A decline is legally final and an expiry counts as one, so the record of
        it is the reason Muster may never ask that person again. Serving only
        `pending()` meant the console lost the answer at the moment it arrived:
        the screen could show what was outstanding and never what anyone said.
        """
        return sorted(
            self._answered.values(),
            key=lambda r: r.answered_at or r.request.expires_at,
            reverse=True,
        )

    def outcome_for(self, request_id: str) -> ConsentOutcome | None:
        record = self._answered.get(request_id)
        return record.outcome if record else None

    def has_declined(self, worker_id: str, shift_id: str) -> bool:
        return (worker_id, shift_id) in self._declined

    def has_granted(self, worker_id: str, shift_id: str) -> bool:
        """True if this worker has agreed, in the record, to this shift.

        What satisfies a rest-period waiver is the worker's own agreement. Until
        this existed the policy asked only whether a waiver was *needed*, so a
        cover the worker had already consented to was refused for needing the
        consent it already had - and the run went back round to ask again.
        """
        return self.grant_for(worker_id, shift_id) is not None

    def grant_for(self, worker_id: str, shift_id: str) -> ConsentRecord | None:
        """The granted record behind this cover, for the receipt to carry.

        A cover that exists only because someone agreed to it should say so, with
        who and when. Without this the receipt for a $100 clopening premium
        recorded the money and the clause and left the consent field empty - on
        the one artefact an investigator opens to find exactly that.
        """
        return next(
            (record for record in self._answered.values()
             if record.request.worker_id == worker_id
             and record.request.shift_id == shift_id
             and record.outcome is ConsentOutcome.GRANTED),
            None,
        )
