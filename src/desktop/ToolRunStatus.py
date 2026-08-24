"""How one console run ended, in terms an operator can act on.

Five outcomes, and the boundary between the first two is the one that matters.
INVALID_ARGUMENTS means the console refused to build an invocation at all, so
nothing was requested and no effect was granted. UNAUTHORIZED means the gate
refused, so the tool was never reached. Everything after that means a tool ran.

REFUSED covers a tool that ran and did not succeed, whether because it declined
the arguments it was given or because its work failed. The Tool Layer does not
distinguish those two: both arrive as `ToolFailureKind.TOOL_FAILED`, and the
difference exists only in a detail sentence the tool chose. The console does not
invent the distinction. Splitting them here would mean guessing, and a guess
presented as a category is worse than a category that admits it is coarse.
"""

from __future__ import annotations

from enum import StrEnum


class ToolRunStatus(StrEnum):
    """Name one bounded outcome of one operator-requested run."""

    SUCCEEDED = "succeeded"
    INVALID_ARGUMENTS = "invalid_arguments"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    CANCELLED = "cancelled"
    REFUSED = "refused"

    @property
    def reached_the_tool(self) -> bool:
        """Return whether an implementation actually ran."""
        return self in (ToolRunStatus.SUCCEEDED, ToolRunStatus.REFUSED)

    @property
    def concerns_authorization(self) -> bool:
        """Return whether the effect gate stopped this run."""
        return self is ToolRunStatus.UNAUTHORIZED

    @property
    def label(self) -> str:
        """Return the fixed sentence shown beside the result."""
        return _LABELS[self]


_LABELS: dict[ToolRunStatus, str] = {
    ToolRunStatus.SUCCEEDED: "Succeeded.",
    ToolRunStatus.INVALID_ARGUMENTS: (
        "Not run. The arguments were rejected before anything was requested."
    ),
    ToolRunStatus.UNAVAILABLE: "Not run. That capability is not registered.",
    ToolRunStatus.UNAUTHORIZED: (
        "Not run. The required effects were not authorized for this invocation."
    ),
    ToolRunStatus.CANCELLED: "Not run. The invocation was cancelled first.",
    ToolRunStatus.REFUSED: "The tool ran and did not succeed.",
}
