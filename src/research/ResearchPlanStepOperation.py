"""Structural boundary for one real research operation on a plan step."""

from typing import Protocol

from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult


class ResearchPlanStepOperation(Protocol):
    """Run one bounded research operation for an authored step.

    Collaborators are injected when the operation is constructed. The context
    carries only the explicit per-execution data, so an operation never reaches
    a container, service locator, global, or unrelated store.
    """

    @property
    def operation_name(self) -> str:
        """Return the stable identifier recorded for this operation."""

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Perform the operation and report exactly what it did."""
