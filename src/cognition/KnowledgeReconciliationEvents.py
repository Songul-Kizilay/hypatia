"""Bounded observability for knowledge reconciliation.

Payloads carry counts and two explicit zeroes stating that nothing was removed
or repaired. They never carry a resource identity, a title, or a document
identifier: a reconciliation event naming specific documents alongside the word
orphan is exactly the artefact that gets quoted later as a cleanup list.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.KnowledgeReconciliationReport import KnowledgeReconciliationReport

RECONCILIATION_REPORTED = "knowledge_reconciliation.reported"

EVENT_SOURCE = "knowledge.reconciliation"


class KnowledgeReconciliationEvents:
    """Publish bounded reconciliation events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def reported(self, report: KnowledgeReconciliationReport) -> None:
        payload: dict[str, object] = dict(report.counts())
        payload["healthy"] = report.healthy
        payload["documents_removed"] = 0
        payload["references_repaired"] = 0
        payload["executed"] = False
        self._emit(RECONCILIATION_REPORTED, payload)

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
