"""Report the current time, and nothing else whatsoever.

The point of this tool is not the time. It is that the whole invocation path —
registry, authorization gate, lifecycle events, bounded result — can be proven
end to end while the worst possible bug is a wrong clock reading. Anything more
capable would have to be trusted before the path that constrains it was known to
work.

Its declared effect is exactly what it does: it reads local state. It touches no
network, no filesystem, no process, and no model, and it changes nothing, so
declaring anything else would be a lie the gate would then enforce as truth.

The clock is injected. A tool that read the wall clock directly could only be
tested against the second it happened to run in, which is not a test.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult

CLOCK_READ_SUMMARY = "Report the current UTC date and time. Reads nothing else."

ACCEPTED_ARGUMENTS: frozenset[str] = frozenset()


class ClockReadTool:
    """Return the current UTC time through the tool layer."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=frozenset({ToolEffect.READS_LOCAL_STATE}),
            summary=CLOCK_READ_SUMMARY,
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        """Return the declaration the authorization gate checks."""
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Read the clock, or explain why this call was not one it accepts.

        Unsupported arguments produce a performed-but-unsuccessful result rather
        than a refusal, because the tool did run: it was reached, it looked at
        what it was given, and it declined. A refusal means the implementation
        was never entered, and that distinction belongs to the gate.

        A clock source that answers with something other than an unambiguous
        time is a different matter and raises, because the request was fine and
        the environment was not. The service reports that as a failed attempt.
        """
        unsupported = self._unsupported(invocation)
        if unsupported:
            return ToolResult.declined(
                ToolCapability.CLOCK_READ,
                "This tool accepts no arguments.",
            )
        moment = self._read()
        return ToolResult(
            capability=ToolCapability.CLOCK_READ,
            performed=True,
            detail="Read the current UTC time.",
            succeeded=True,
            values=(
                ("utc_iso", moment.isoformat()),
                ("utc_date", moment.date().isoformat()),
                ("utc_time", moment.time().isoformat()),
                ("timezone", "UTC"),
            ),
        )

    def _read(self) -> datetime:
        """Return the injected clock's answer, refusing an ambiguous one."""
        moment = self._clock()
        if not isinstance(moment, datetime):
            raise ResearchError("The clock source did not return a time.")
        if moment.tzinfo is None:
            raise ResearchError("The clock source returned an ambiguous local time.")
        return moment.astimezone(UTC)

    @staticmethod
    def _unsupported(invocation: ToolInvocation) -> tuple[str, ...]:
        """Return argument names this tool does not accept, which is all of them."""
        return tuple(
            name for name, _ in invocation.arguments if name not in ACCEPTED_ARGUMENTS
        )
