"""Typed resource cost of running one research operation."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchOperationCost:
    """Declared external operations one capability may consume when it runs."""

    network_operations: int = 0
    llm_operations: int = 0

    def __post_init__(self) -> None:
        for value, label in (
            (self.network_operations, "network"),
            (self.llm_operations, "LLM"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(
                    f"Research operation {label} cost must be a "
                    "non-negative integer."
                )
