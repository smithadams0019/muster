"""Whether a claimed exemption actually holds.

Every ordinance here has exceptions that reduce a premium to nothing, which makes
them the highest-value thing for an agent to be wrong about. So a claim is never
taken at face value: each kind is checked against a record the world holds. The
agent may propose "she asked for this swap"; only a request record makes it true.

`against_rest` exists because Chicago says in terms that the Right to Rest has no
exceptions, and NYC's clopening consent requirement admits none either. When the
rule being carved out is a rest rule, a jurisdiction with `rest_has_carve_outs`
false refuses every claim, however well evidenced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from muster.domain.types import CarveOut
from muster.rulebook.schema import Jurisdiction


@dataclass(frozen=True)
class CarveOutClaim:
    kind: CarveOut
    evidence_id: str | None = None


class CarveOutEvidence(Protocol):
    """What the world can attest to. Implemented by the world adapter."""

    def worker_requested(self, worker_id: str, shift_id: str) -> bool: ...
    def on_standby_list(self, worker_id: str) -> bool: ...
    def standby_accepted(self, worker_id: str, shift_id: str) -> bool: ...
    def trade_accepted_by_both(self, shift_id: str, from_worker: str, to_worker: str) -> bool: ...
    def written_agreement(self, evidence_id: str | None) -> bool: ...
    def declared_incident(self, evidence_id: str | None) -> CarveOut | None: ...


_INCIDENT_KINDS = frozenset(
    {CarveOut.ACT_OF_NATURE, CarveOut.UTILITY_FAILURE, CarveOut.THREAT_TO_SAFETY}
)


def carve_out_applies(
    claim: CarveOutClaim,
    *,
    rules: Jurisdiction,
    worker_id: str,
    shift_id: str,
    evidence: CarveOutEvidence,
    against_rest: bool = False,
) -> bool:
    """Whether this claim exempts this change under this jurisdiction."""
    if not isinstance(claim.kind, CarveOut):
        raise ValueError(f"unrecognised carve-out claim: {claim.kind!r}")

    if against_rest and not rules.rest_has_carve_outs:
        return False
    if claim.kind not in rules.carve_outs:
        return False

    if claim.kind is CarveOut.WORKER_REQUESTED:
        return evidence.worker_requested(worker_id, shift_id)
    if claim.kind is CarveOut.STANDBY_LIST:
        return evidence.on_standby_list(worker_id) and evidence.standby_accepted(worker_id, shift_id)
    if claim.kind is CarveOut.MUTUAL_SHIFT_TRADE:
        return evidence.trade_accepted_by_both(shift_id, worker_id, worker_id)
    if claim.kind is CarveOut.MUTUAL_WRITTEN_AGREEMENT:
        return evidence.written_agreement(claim.evidence_id)
    if claim.kind in _INCIDENT_KINDS:
        return evidence.declared_incident(claim.evidence_id) is claim.kind
    return False
