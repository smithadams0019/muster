"""Process-wide state for the control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from muster.adapters.simulated import SableCoffee
from muster.domain.types import AutonomyLevel
from muster.hooks.audit import AuditTrail
from muster.persistence.consent import ConsentStore
from muster.persistence.inbox import DecisionInbox
from muster.persistence.receipts import ReceiptBook


@dataclass
class MusterState:
    world: SableCoffee = field(default_factory=SableCoffee)
    inbox: DecisionInbox = field(default_factory=DecisionInbox)
    consent: ConsentStore = field(default_factory=ConsentStore)
    receipts: ReceiptBook = field(default_factory=ReceiptBook)
    trail: AuditTrail = field(default_factory=AuditTrail)
    ledger: list[dict[str, Any]] = field(default_factory=list)
    autonomy: AutonomyLevel = AutonomyLevel.BALANCED
