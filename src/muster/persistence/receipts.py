"""The immutable record of every change to a posted schedule.

Rendered from the same CostBreakdown the decision was made from. A receipt built
separately would be a second account of what happened, and two accounts eventually
disagree - which is the position the enforcement settlements describe.

A held change writes no receipt. The book records what happened, never what was
contemplated.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from muster.domain.pricing import CostBreakdown, LineItem
from muster.domain.types import CarveOut, ChangeKind, Money
from muster.persistence.consent import ConsentRecord


@dataclass(frozen=True)
class Receipt:
    at: datetime
    site_id: str
    worker_id: str
    shift_id: str
    kind: ChangeKind
    jurisdiction_code: str
    rulebook_effective_from: str
    lines: tuple[LineItem, ...]
    total: Money
    carve_outs_applied: tuple[CarveOut, ...]
    decided_by: str
    consent: ConsentRecord | None


class ReceiptBook:
    def __init__(self) -> None:
        self._receipts: list[Receipt] = []

    def write(
        self,
        *,
        site_id: str,
        worker_id: str,
        shift_id: str,
        kind: ChangeKind,
        jurisdiction_code: str,
        rulebook_effective_from: str,
        breakdown: CostBreakdown,
        decided_by: str,
        consent: ConsentRecord | None,
        at: datetime,
    ) -> Receipt:
        receipt = Receipt(
            at=at, site_id=site_id, worker_id=worker_id, shift_id=shift_id, kind=kind,
            jurisdiction_code=jurisdiction_code,
            rulebook_effective_from=rulebook_effective_from,
            lines=breakdown.lines, total=breakdown.total,
            carve_outs_applied=breakdown.carve_outs_applied,
            decided_by=decided_by, consent=consent,
        )
        self._receipts.append(receipt)
        return receipt

    def all(self) -> list[Receipt]:
        return list(self._receipts)

    def for_site(self, site_id: str) -> list[Receipt]:
        return [r for r in self._receipts if r.site_id == site_id]

    def to_csv(self) -> str:
        """The export an investigator asks for."""
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([
            "at", "site_id", "worker_id", "shift_id", "change", "jurisdiction",
            "rulebook_effective_from", "premium_total", "clauses", "carve_outs",
            "decided_by", "consent_outcome", "consent_answered_at",
        ])
        for r in self._receipts:
            writer.writerow([
                r.at.isoformat(), r.site_id, r.worker_id, r.shift_id, r.kind.value,
                r.jurisdiction_code, r.rulebook_effective_from, r.total.dollars,
                " | ".join(line.clause for line in r.lines),
                " | ".join(c.value for c in r.carve_outs_applied),
                r.decided_by,
                r.consent.outcome.value if r.consent else "",
                r.consent.answered_at.isoformat() if r.consent and r.consent.answered_at else "",
            ])
        return out.getvalue()
