"""Bounded observability for research reflection.

Payloads carry report and run identifiers, bounded finding-kind counts, and
canonical counts. They never carry a research question, claim text, finding
detail, proposed question text, URL, source body, or an exception message.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchReflectionReport import ResearchReflectionReport

REFLECTION_PRODUCED = "reflection.produced"
REFLECTION_STORED = "reflection.stored"

EVENT_SOURCE = "research.reflection"


class ReflectionEvents:
    """Publish bounded reflection events, or nothing when no bus is present."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def produced(self, report: ResearchReflectionReport) -> None:
        self._emit(REFLECTION_PRODUCED, self._payload(report))

    def stored(self, report: ResearchReflectionReport, total_count: int) -> None:
        payload = self._payload(report)
        payload["stored_report_count"] = total_count
        self._emit(REFLECTION_STORED, payload)

    @staticmethod
    def _payload(report: ResearchReflectionReport) -> dict[str, object]:
        return {
            "report_id": report.report_id,
            "run_id": report.run_id,
            "finding_count": len(report.findings),
            "lesson_count": len(report.lessons),
            "finding_kinds": report.counts(),
            "source_count": report.summary.source_count,
            "evidence_count": report.summary.evidence_count,
            "claim_count": report.summary.claim_count,
            "executed": False,
        }

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
