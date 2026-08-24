"""Why a tool invocation did not produce what was asked for.

Bounded on purpose. A raw exception string is the easiest thing to put in a
result and the worst thing to have there: it carries file paths, argument
values, and whatever a library decided to interpolate, and it ends up in logs,
telemetry, and eventually a screen. A caller deciding what to do next needs a
category, not a sentence.

The kinds separate refusals from failures. A refusal means the tool never ran —
the capability was not registered, the effects were not granted, the arguments
were wrong, or the work was cancelled first. A failure means the implementation
ran and did not achieve its outcome. Collapsing the two would make "it did not
work" indistinguishable from "it was not allowed", which is exactly the
distinction an authorization boundary exists to preserve.
"""

from __future__ import annotations

from enum import StrEnum


class ToolFailureKind(StrEnum):
    """Name one bounded reason an invocation did not succeed."""

    UNKNOWN_CAPABILITY = "unknown_capability"
    UNAUTHORIZED_EFFECT = "unauthorized_effect"
    INVALID_ARGUMENTS = "invalid_arguments"
    CANCELLED = "cancelled"
    TOOL_FAILED = "tool_failed"

    @property
    def refused_before_execution(self) -> bool:
        """Return whether the implementation was never reached.

        Only TOOL_FAILED means the tool actually ran, so everything else here
        must leave `performed` false.
        """
        return self is not ToolFailureKind.TOOL_FAILED

    @property
    def concerns_authorization(self) -> bool:
        """Return whether this refusal came from the effect gate."""
        return self is ToolFailureKind.UNAUTHORIZED_EFFECT
