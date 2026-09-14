"""What one execution has already spent of its approved budget.

Counters rather than a log. What matters at the moment of deciding whether the
next step may run is how much is left, and a list of past operations would have
to be re-totalled to answer that — which is one more place for the answer to
come out differently.

`active_seconds` is the summed wall-clock of attempted advances, not the time
since the execution started. Those differ by everything: an execution stepped
by a person is idle between advances and idle entirely while the application is
closed, and charging that idle time would exhaust a budget nobody spent. What is
counted is the time inside an attempt, which is the only span the state can
truthfully observe.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core.Exceptions import ResearchError
from research.ResearchOperationCost import ResearchOperationCost


@dataclass(frozen=True, slots=True)
class ResearchExecutionSpend:
    """Count what one execution has consumed, monotonically."""

    step_advances: int = 0
    network_operations: int = 0
    llm_operations: int = 0
    active_seconds: float = 0.0

    def __post_init__(self) -> None:
        for value, label in (
            (self.step_advances, "step advances"),
            (self.network_operations, "network operations"),
            (self.llm_operations, "LLM operations"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(
                    f"Research execution spent {label} must be a "
                    "non-negative integer."
                )
        if isinstance(self.active_seconds, bool) or not isinstance(
            self.active_seconds, (int, float)
        ):
            raise ResearchError("Research execution active seconds must be a number.")
        if self.active_seconds < 0:
            raise ResearchError("Research execution active seconds cannot be negative.")
        object.__setattr__(self, "active_seconds", float(self.active_seconds))

    def with_elapsed(self, seconds: float) -> ResearchExecutionSpend:
        """Return this spend with more active time and nothing else.

        Separate from `charged` because time is known only after an attempt
        resolves, while the attempt itself is counted before the operation
        runs. One method doing both would have to be called twice and undone
        once.
        """
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise ResearchError("Research execution elapsed seconds must be a number.")
        return replace(
            self,
            active_seconds=self.active_seconds + max(float(seconds), 0.0),
        )

    def charged(
        self,
        cost: ResearchOperationCost,
        seconds: float = 0.0,
    ) -> ResearchExecutionSpend:
        """Return this spend plus one attempted advance and its declared cost.

        One attempt, charged once. Nothing here asks whether the operation
        succeeded, because an attempt that failed still spent the network call
        it made and still used up one of the advances that were approved.
        """
        if not isinstance(cost, ResearchOperationCost):
            raise ResearchError("Research execution cost is invalid.")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise ResearchError("Research execution elapsed seconds must be a number.")
        return replace(
            self,
            step_advances=self.step_advances + 1,
            network_operations=self.network_operations + cost.network_operations,
            llm_operations=self.llm_operations + cost.llm_operations,
            active_seconds=self.active_seconds + max(float(seconds), 0.0),
        )
