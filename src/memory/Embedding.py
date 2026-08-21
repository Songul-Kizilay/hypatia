"""Validated immutable numeric vector used by semantic retrieval boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

MAX_EMBEDDING_DIMENSION = 16_384


@dataclass(frozen=True, slots=True)
class Embedding:
    """A non-empty, finite embedding vector with a stable tuple representation."""

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("Embedding values cannot be empty.")
        if len(self.values) > MAX_EMBEDDING_DIMENSION:
            raise ValueError(
                "Embedding dimension cannot exceed "
                f"{MAX_EMBEDDING_DIMENSION:,} values."
            )

        normalized_values: list[float] = []
        for value in self.values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Embedding values must be finite numbers.")
            normalized_value = float(value)
            if not isfinite(normalized_value):
                raise ValueError("Embedding values must be finite numbers.")
            normalized_values.append(normalized_value)

        object.__setattr__(self, "values", tuple(normalized_values))

    @property
    def dimension(self) -> int:
        """Return the number of coordinates in the vector."""
        return len(self.values)
