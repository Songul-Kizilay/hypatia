"""Structural boundary for one real research operation on a plan step."""

from typing import Protocol

from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult


class ResearchPlanStepOperation(Protocol):
    """Run one bounded research operation for an authored step."""

    @property
    def operation_name(self) -> str:
        """Return the stable identifier recorded for this operation."""

    def run(self, step: ResearchPlanStep) -> ResearchPlanStepOperationResult:
        """Perform the operation and report exactly what it did."""
