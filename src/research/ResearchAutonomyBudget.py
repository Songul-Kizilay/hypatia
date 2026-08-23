"""Immutable enforced budget for one bounded autonomous research run.

Every bound is enforced, never advisory. `max_step_advances` counts attempted
advances rather than successful ones, so a plan that keeps blocking cannot loop
forever by never succeeding.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_AUTONOMY_STEP_ADVANCES = 50
MAX_AUTONOMY_NETWORK_OPERATIONS = 25
MAX_AUTONOMY_LLM_OPERATIONS = 25
MAX_AUTONOMY_SECONDS = 3_600.0


@dataclass(frozen=True, slots=True)
class ResearchAutonomyBudget:
    """Hard limits on one autonomous run."""

    max_step_advances: int = 5
    max_network_operations: int = 3
    max_llm_operations: int = 0
    max_seconds: float = 60.0

    def __post_init__(self) -> None:
        for value, label, ceiling in (
            (self.max_step_advances, "step advances", MAX_AUTONOMY_STEP_ADVANCES),
            (
                self.max_network_operations,
                "network operations",
                MAX_AUTONOMY_NETWORK_OPERATIONS,
            ),
            (
                self.max_llm_operations,
                "LLM operations",
                MAX_AUTONOMY_LLM_OPERATIONS,
            ),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(
                    f"Research autonomy {label} budget must be a "
                    "non-negative integer."
                )
            if value > ceiling:
                raise ResearchError(
                    f"Research autonomy {label} budget exceeds its hard ceiling."
                )
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, int | float)
            or self.max_seconds < 0
            or self.max_seconds > MAX_AUTONOMY_SECONDS
        ):
            raise ResearchError(
                "Research autonomy time budget must be within its hard ceiling."
            )
