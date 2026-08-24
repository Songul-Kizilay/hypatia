"""What a tool actually did, keeping running and succeeding apart.

The two flags mirror research step operations, for the same reason. A tool can
genuinely run and still not produce what was wanted, and collapsing that into
one boolean turns "I tried and it did not work" into either a lie or a silence.

``performed`` is set only by a tool that really executed. A refusal before
invocation performs nothing, and nothing that performed nothing may report
success.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability

MAX_TOOL_DETAIL_LENGTH = 500
MAX_TOOL_VALUES = 20
MAX_TOOL_VALUE_LENGTH = 300


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Report whether a tool ran, whether it worked, and what it returned."""

    capability: ToolCapability
    performed: bool
    detail: str
    succeeded: bool = True
    values: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ToolCapability):
            raise ResearchError("A tool result capability must be bounded.")
        for flag, label in (
            (self.performed, "performed flag"),
            (self.succeeded, "succeeded flag"),
        ):
            if not isinstance(flag, bool):
                raise ResearchError(f"A tool result {label} must be boolean.")
        if self.succeeded and not self.performed:
            raise ResearchError("A tool that performed nothing cannot have succeeded.")
        if not self.detail.strip():
            raise ResearchError("A tool result detail cannot be empty.")
        if len(self.detail) > MAX_TOOL_DETAIL_LENGTH:
            raise ResearchError("A tool result detail is too long.")
        self._validate_values()

    def _validate_values(self) -> None:
        if len(self.values) > MAX_TOOL_VALUES:
            raise ResearchError("A tool result returned too many values.")
        names = [name for name, _ in self.values]
        if len(names) != len(set(names)):
            raise ResearchError("A tool result repeated a value name.")
        for name, value in self.values:
            if not name.strip():
                raise ResearchError("A tool result value name cannot be empty.")
            if len(value) > MAX_TOOL_VALUE_LENGTH:
                raise ResearchError("A tool result value is too long.")
        if self.values and not self.performed:
            raise ResearchError("A tool that performed nothing returned values.")

    def lines(self) -> tuple[str, ...]:
        """Render the returned values as bounded, labelled lines."""
        return tuple(f"{name}: {value}" for name, value in self.values)

    @classmethod
    def refused(cls, capability: ToolCapability, reason: str) -> ToolResult:
        """Return a result for a tool that was never invoked."""
        return cls(
            capability=capability,
            performed=False,
            detail=reason,
            succeeded=False,
        )
