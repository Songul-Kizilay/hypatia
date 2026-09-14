"""Why a tool invocation did not produce what was asked for.

Bounded on purpose. A raw exception string is the easiest thing to put in a
result and the worst thing to have there: it carries file paths, argument
values, and whatever a library decided to interpolate, and it ends up in logs,
telemetry, and eventually a screen. A caller deciding what to do next needs a
category, not a sentence.

The kinds separate three things a caller would act on differently.

A refusal means no tool ran: the capability was not registered, the effects were
not granted, or the work was cancelled first. INVOCATION_DECLINED means a tool
was reached, read the request, and would not take it — nothing was attempted, so
the request is the thing to change. EXECUTION_FAILED means a tool took the
request and could not finish it, so the request may be fine and the environment
is the thing to look at.

The last two used to be one member. Both produced `succeeded=False`, both became
TOOL_FAILED, and the only surviving difference was the wording of a detail
sentence. That is an important distinction living in prose, which means a later
system deciding whether to retry would have to read English to decide — and
would eventually retry a malformed request forever, or abandon a transient
failure on the first attempt.

Collapsing refusal into either would be worse still. "It did not work" and "it
was not allowed" are exactly the distinction an authorization boundary exists to
preserve.
"""

from __future__ import annotations

from enum import StrEnum

from core.Exceptions import ResearchError
from tools.ToolDisposition import ToolDisposition


class ToolFailureKind(StrEnum):
    """Name one bounded reason an invocation did not succeed."""

    UNKNOWN_CAPABILITY = "unknown_capability"
    UNAUTHORIZED_EFFECT = "unauthorized_effect"
    CANCELLED = "cancelled"
    INVOCATION_DECLINED = "invocation_declined"
    EXECUTION_FAILED = "execution_failed"

    @property
    def refused_before_execution(self) -> bool:
        """Return whether the implementation was never reached.

        Only the last two mean a tool actually ran, so everything else here must
        leave `performed` false.
        """
        return self not in (
            ToolFailureKind.INVOCATION_DECLINED,
            ToolFailureKind.EXECUTION_FAILED,
        )

    @property
    def concerns_authorization(self) -> bool:
        """Return whether this refusal came from the effect gate."""
        return self is ToolFailureKind.UNAUTHORIZED_EFFECT

    @property
    def attempted_the_work(self) -> bool:
        """Return whether the tool started doing what it was asked to do.

        A decline is not an attempt. The tool read the request and stopped, so
        nothing is half-done and repeating it will get the same answer.
        """
        return self is ToolFailureKind.EXECUTION_FAILED

    @property
    def concerns_the_request(self) -> bool:
        """Return whether changing the request could plausibly help.

        The question a caller actually has, answered from bounded state instead
        of from a sentence. It says a different request might be accepted, never
        that it would succeed.
        """
        return self is ToolFailureKind.INVOCATION_DECLINED

    @classmethod
    def for_disposition(
        cls,
        disposition: ToolDisposition | None,
    ) -> ToolFailureKind | None:
        """Return the kind one tool disposition amounts to, or None on success.

        The single translation point between what a tool says it did and how the
        service reports it. Having exactly one keeps the two vocabularies from
        drifting into disagreement.
        """
        if disposition is ToolDisposition.COMPLETED:
            return None
        if disposition is ToolDisposition.DECLINED:
            return cls.INVOCATION_DECLINED
        if disposition is ToolDisposition.FAILED:
            return cls.EXECUTION_FAILED
        # NOT_REACHED and an unsettled value both mean no tool saw this, which
        # the gate reports for itself. Classifying it here would invent a tool
        # opinion that no tool ever had.
        raise ResearchError("A tool that was never reached reports no tool failure.")
