"""Bounded observability for autonomous research runs.

Two events only, at the boundaries of a run. Nothing is emitted per internal
decision, so a long run cannot flood the bus.

Payloads carry the plan identifier, declared budgets, bounded counters, and a
stop-reason category. They never carry authored instructions, questions, URLs,
source content, evidence text, or claim text.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import ResearchAutonomyResult

AUTONOMY_STARTED = "research.autonomy.started"
AUTONOMY_STOPPED = "research.autonomy.stopped"

EVENT_SOURCE = "research.autonomy"


class ResearchAutonomyEvents:
    """Publish bounded autonomy events, or nothing when no bus is present."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def started(self, plan_id: str, budget: ResearchAutonomyBudget) -> None:
        """Report the declared budget one run will be held to."""
        self._emit(
            AUTONOMY_STARTED,
            {
                "plan_id": plan_id,
                "max_step_advances": budget.max_step_advances,
                "max_network_operations": budget.max_network_operations,
                "max_llm_operations": budget.max_llm_operations,
                "max_seconds": budget.max_seconds,
            },
        )

    def stopped(self, result: ResearchAutonomyResult) -> None:
        """Report exactly what the run consumed and why it stopped."""
        self._emit(
            AUTONOMY_STOPPED,
            {
                "plan_id": result.plan_id,
                "stop_reason": result.stop_reason.value,
                "execution_status": result.execution_status,
                "steps_attempted": result.steps_attempted,
                "operations_performed": result.operations_performed,
                "network_operations": result.network_operations,
                "llm_operations": result.llm_operations,
            },
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
