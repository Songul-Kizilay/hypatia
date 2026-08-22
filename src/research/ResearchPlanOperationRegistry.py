"""Explicit capability-to-operation registration for plan execution.

Operation selection is a table lookup on a typed capability, never a heuristic
over authored instruction text. A capability with no registered operation is
unauthorized and blocks the step rather than falling back to something else.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperation import ResearchPlanStepOperation


class ResearchPlanOperationRegistry:
    """Resolve exactly one registered operation for a declared capability."""

    def __init__(
        self,
        operations: (
            dict[ResearchPlanStepCapability, ResearchPlanStepOperation] | None
        ) = None,
    ) -> None:
        self._operations: dict[
            ResearchPlanStepCapability, ResearchPlanStepOperation
        ] = {}
        for capability, operation in (operations or {}).items():
            self.register(capability, operation)

    def register(
        self,
        capability: ResearchPlanStepCapability,
        operation: ResearchPlanStepOperation,
    ) -> None:
        """Bind one executable capability to exactly one operation."""
        if not isinstance(capability, ResearchPlanStepCapability):
            raise ResearchError("Research plan capability is invalid.")
        if not capability.executable:
            raise ResearchError("Research plan capability 'none' cannot be registered.")
        if capability in self._operations:
            raise ResearchError("Research plan capability is already registered.")
        self._operations[capability] = operation

    def resolve(
        self,
        capability: ResearchPlanStepCapability,
    ) -> ResearchPlanStepOperation | None:
        """Return the registered operation, or None when unauthorized."""
        if not isinstance(capability, ResearchPlanStepCapability):
            raise ResearchError("Research plan capability is invalid.")
        if not capability.executable:
            return None
        return self._operations.get(capability)

    @property
    def registered_capabilities(self) -> tuple[ResearchPlanStepCapability, ...]:
        """Return registered capabilities in deterministic declared order."""
        return tuple(
            capability
            for capability in ResearchPlanStepCapability
            if capability in self._operations
        )
