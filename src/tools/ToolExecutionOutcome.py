"""The full record of one invocation, for callers that need more than a result.

`ToolResult` says what the tool produced and is what most callers want. This
adds what happened around it: whether the capability resolved, whether the gate
allowed it, and which bounded failure kind applies. Keeping that outside the
result means a tool never has to describe its own authorization, which is the
property the gate exists to guarantee.

`authorized` is a fact about this invocation, not a standing permission. It says
the effects declared by this tool were granted for this call, and nothing about
the next one.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolResult import ToolResult


@dataclass(frozen=True, slots=True)
class ToolExecutionOutcome:
    """Report the result together with how far the invocation actually got."""

    capability: ToolCapability
    result: ToolResult
    resolved: bool
    authorized: bool
    failure_kind: ToolFailureKind | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ToolCapability):
            raise ResearchError("An execution outcome capability must be bounded.")
        if not isinstance(self.result, ToolResult):
            raise ResearchError("An execution outcome requires a tool result.")
        for flag, label in (
            (self.resolved, "resolved flag"),
            (self.authorized, "authorized flag"),
        ):
            if not isinstance(flag, bool):
                raise ResearchError(f"An execution outcome {label} must be boolean.")
        if self.failure_kind is not None and not isinstance(
            self.failure_kind, ToolFailureKind
        ):
            raise ResearchError("An execution failure kind must be bounded.")
        self._validate_consistency()

    def _validate_consistency(self) -> None:
        """Refuse an outcome that disagrees with itself."""
        if self.authorized and not self.resolved:
            raise ResearchError("An unresolved capability cannot be authorized.")
        if self.result.performed and not self.authorized:
            raise ResearchError(
                "A tool cannot have performed work without authorization."
            )
        if self.result.succeeded and self.failure_kind is not None:
            raise ResearchError("A successful result carries no failure kind.")
        if not self.result.succeeded and self.failure_kind is None:
            raise ResearchError("An unsuccessful result must name a failure kind.")
        if (
            self.failure_kind is not None
            and self.failure_kind.refused_before_execution
            and self.result.performed
        ):
            raise ResearchError(
                "A refusal before execution cannot report performed work."
            )

    @property
    def refused(self) -> bool:
        """Return whether the implementation was never reached."""
        return not self.result.performed
