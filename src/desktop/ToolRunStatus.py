"""How one console run ended, in terms an operator can act on.

Six outcomes, each mapped from bounded Tool Layer state and never from wording.

INVALID_ARGUMENTS means the console refused to build an invocation at all, so
nothing was requested and no effect was granted. UNAUTHORIZED means the gate
refused, so the tool was never reached. Everything after that means a tool ran.

DECLINED and EXECUTION_FAILED used to be one status, because the Tool Layer gave
the console one failure kind for both and the difference survived only in a
sentence. They are separate now for the reason they were always different: a
declined request is something the operator can fix by asking differently, and a
failed execution is something to go and look at. The console still does not
invent the distinction — it reads `ToolFailureKind` and translates, which is why
there is no string matching anywhere in this file or its controller.
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
    DECLINED = "declined"
    EXECUTION_FAILED = "execution_failed"

    @property
    def reached_the_tool(self) -> bool:
        """Return whether an implementation actually ran."""
        return self in (
            ToolRunStatus.SUCCEEDED,
            ToolRunStatus.DECLINED,
            ToolRunStatus.EXECUTION_FAILED,
        )

    @property
    def attempted_the_work(self) -> bool:
        """Return whether the tool got as far as doing what it was asked."""
        return self in (ToolRunStatus.SUCCEEDED, ToolRunStatus.EXECUTION_FAILED)

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
    ToolRunStatus.DECLINED: (
        "Request declined. The tool read it and would not take it, so nothing "
        "was attempted."
    ),
    ToolRunStatus.EXECUTION_FAILED: (
        "Execution failed. The tool accepted the request, started, and could "
        "not finish."
    ),
}
