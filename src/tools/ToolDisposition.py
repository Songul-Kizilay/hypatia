"""What a tool did with the request it was handed.

This exists because two very different things were arriving as one fact. A tool
that looked at its arguments and said no, and a tool that accepted the request
and then hit an error partway through, both produced `succeeded=False` and both
became `TOOL_FAILED`. The only surviving difference was a sentence, and a
sentence is not something a later system can reason over: deciding whether to
retry by matching prose is how a caller ends up retrying a malformed request
forever, or giving up on a transient one immediately.

The obvious shortcut is to infer this at the execution seam — a tool that raised
must have failed, a tool that returned must have declined. That does not hold
here. `FilesystemListTool` catches its own OSError and returns it as a result,
so an unreadable directory would be filed as a bad request. Only the tool knows
which of the two happened, so the tool says.

The four values are not four kinds of failure. NOT_REACHED means no tool saw the
request at all, which is what the authorization gate and an unknown capability
produce, and it is what keeps "we refused you" from being confused with
"something went wrong". The remaining three are the whole vocabulary a tool has:
it did the work, it would not take the request, or it took the request and could
not finish it.
"""

from __future__ import annotations

from enum import StrEnum


class ToolDisposition(StrEnum):
    """Name what one tool did with one request."""

    NOT_REACHED = "not_reached"
    COMPLETED = "completed"
    DECLINED = "declined"
    FAILED = "failed"

    @property
    def entered_the_tool(self) -> bool:
        """Return whether the implementation was reached at all.

        This is the fact `performed` records, so the two are defined against
        each other rather than being maintained separately and drifting.
        """
        return self is not ToolDisposition.NOT_REACHED

    @property
    def attempted_the_work(self) -> bool:
        """Return whether the tool started doing what it was asked to do.

        A decline is deliberately not an attempt. The tool read the request and
        did nothing else, so nothing was half-done, nothing partially changed,
        and repeating the same request will get the same answer.
        """
        return self in (ToolDisposition.COMPLETED, ToolDisposition.FAILED)

    @property
    def worth_reformulating(self) -> bool:
        """Return whether a different request might succeed where this did not.

        The one question a caller most often needs answered, made explicit so it
        is never answered by reading a sentence. A decline is about the request;
        a failure is about the world. Neither promises the retry will work.
        """
        return self is ToolDisposition.DECLINED

    @property
    def succeeded(self) -> bool:
        """Return whether the tool produced what was asked for."""
        return self is ToolDisposition.COMPLETED
