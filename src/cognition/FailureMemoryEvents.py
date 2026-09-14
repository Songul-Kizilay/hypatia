"""Bounded observability for remembered failure lessons.

Payloads carry run and lesson identifiers, bounded kind counts, provenance
counts, and recall counts. They never carry a lesson statement, a research
question, claim text, a URL, or an exception message. The provenance itself is
counted, never listed, because a provenance list is a list of identifiers whose
usefulness is in the store, not in a log line.
"""

from __future__ import annotations

from collections import Counter

from eventbus.EventBus import EventBus
from research.ResearchFailureLesson import ResearchFailureLesson

LESSONS_DERIVED = "failure_memory.lessons_derived"
LESSONS_STORED = "failure_memory.lessons_stored"
LESSONS_RECALLED = "failure_memory.lessons_recalled"

EVENT_SOURCE = "research.failure_memory"


class FailureMemoryEvents:
    """Publish bounded failure-memory events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def derived(
        self,
        run_id: str,
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> None:
        payload = self._payload(lessons)
        payload["run_id"] = run_id
        self._emit(LESSONS_DERIVED, payload)

    def stored(
        self,
        run_id: str,
        lessons: tuple[ResearchFailureLesson, ...],
        stored_count: int,
        total_count: int,
    ) -> None:
        payload = self._payload(lessons)
        payload["run_id"] = run_id
        payload["stored_count"] = stored_count
        payload["total_count"] = total_count
        self._emit(LESSONS_STORED, payload)

    def recalled(
        self,
        lessons: tuple[ResearchFailureLesson, ...],
        known_count: int,
    ) -> None:
        payload = self._payload(lessons)
        payload["known_count"] = known_count
        payload["advisory"] = True
        self._emit(LESSONS_RECALLED, payload)

    @staticmethod
    def _payload(
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> dict[str, object]:
        kinds = Counter(lesson.kind.value for lesson in lessons)
        return {
            "lesson_count": len(lessons),
            "belief_lesson_count": sum(
                1 for lesson in lessons if lesson.concerns_belief
            ),
            "lesson_kinds": dict(sorted(kinds.items())),
            "provenance_count": sum(len(lesson.provenance) for lesson in lessons),
            "executed": False,
        }

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
