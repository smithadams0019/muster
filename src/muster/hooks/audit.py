"""Every model call and tool call, written by hooks on the agent loop.

Hooks rather than the agent reporting on itself: an agent's account of what it did
is exactly the thing that must not be trusted when the record is a legal defence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import AfterToolCallEvent, BeforeModelCallEvent, BeforeToolCallEvent


@dataclass(frozen=True)
class TrailEntry:
    kind: str
    label: str
    at: datetime
    detail: dict[str, Any] = field(default_factory=dict)


class AuditTrail(HookProvider):
    def __init__(self) -> None:
        self._entries: list[TrailEntry] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self._on_model)
        registry.add_callback(BeforeToolCallEvent, self._on_tool)
        registry.add_callback(AfterToolCallEvent, self._on_result)

    def record(self, kind: str, label: str, detail: dict[str, Any] | None = None) -> None:
        self._entries.append(TrailEntry(kind, label, datetime.now(timezone.utc), dict(detail or {})))

    def entries(self) -> list[TrailEntry]:
        return list(self._entries)

    def _on_model(self, event: Any) -> None:
        self.record("model_call", "reasoning")

    def _on_tool(self, event: Any) -> None:
        self.record("tool_call", event.tool_use["name"], dict(event.tool_use.get("input", {})))

    def _on_result(self, event: Any) -> None:
        self.record("tool_result", event.tool_use["name"])
