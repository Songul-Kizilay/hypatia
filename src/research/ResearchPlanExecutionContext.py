"""Immutable per-execution context supplied to a plan-step operation.

This carries only the small explicit data one execution needs, plus the
cooperative cancellation signal for the current request. Collaborators such as a
knowledge engine, run manager, or discovery provider are injected into an
operation at composition time; they never travel in this context and are never
looked up by an operation from a container, locator, or global.

Capability authorization stays separate: a step declares what it may run, and
this context describes what it runs against.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.CancellationSignal import CancellationToken
from core.Exceptions import ResearchError
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding

MAX_RESEARCH_EXECUTION_RUN_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ResearchPlanExecutionContext:
    """Bounded explicit context for one research-plan execution."""

    research_run_id: str | None = None
    cancellation_token: CancellationToken | None = None
    target_binding: ResearchPlanTargetBinding | None = None

    def __post_init__(self) -> None:
        if self.target_binding is not None and not isinstance(
            self.target_binding, ResearchPlanTargetBinding
        ):
            raise ResearchError("Research execution target binding is invalid.")
        run_id = self.research_run_id
        if run_id is None:
            return
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("Research execution run ID cannot be empty.")
        normalized = run_id.strip()
        if len(normalized) > MAX_RESEARCH_EXECUTION_RUN_ID_CHARACTERS:
            raise ResearchError("Research execution run ID is too long.")
        object.__setattr__(self, "research_run_id", normalized)

    @property
    def has_research_run(self) -> bool:
        """Return whether this execution is bound to a research run."""
        return self.research_run_id is not None

    @property
    def cancelled(self) -> bool:
        """Report cooperative cancellation without owning the signal."""
        token = self.cancellation_token
        return token is not None and token.is_cancelled()
