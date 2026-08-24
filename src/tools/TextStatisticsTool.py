"""Count characters, words, and lines in text handed to the call.

The point of this tool is not the counts. `ClockReadTool` proved the invocation
path for a tool that takes nothing; this one proves it for a tool that takes
something. Arguments are where a tool layer usually starts leaking — into
results, into logs, into an error message that helpfully quotes what went wrong
— so the first tool with a real argument is the right place to fix the rule
while the argument is only somebody's paragraph.

It is pure. It reads no file, no clipboard, no network, no environment, no
process state, and no model, and it changes nothing. Its only input is the text
the caller passed in, so it declares `COMPUTES_LOCALLY` and nothing else. That
declaration is still checked: an empty grant refuses it, exactly as a grant
missing `READS_NETWORK` would refuse a fetching tool.

Counting definitions, fixed and tested:

    character_count                 len(text), i.e. Unicode code points
    word_count                      whitespace-separated non-empty segments
    line_count                      Python line boundaries in the text
    non_whitespace_character_count  code points that are not whitespace

Line counting uses `str.splitlines`, which treats a lone newline, a carriage
return, and a CRLF pair identically on every platform. That matters more than
which convention is chosen: a count that changed when the same text moved
between machines would be worse than one that is merely arbitrary. The
consequences are worth stating plainly, because they are the cases people
disagree about:

    ""              -> 0 lines     a file with nothing in it has no lines
    "hello"         -> 1 line      a line need not be terminated
    "hello\\n"       -> 1 line      the newline ends that line, it starts none
    "hello\\nworld"  -> 2 lines     both are lines, only one is terminated
    "\\n"            -> 1 line      the empty line before the break is a line

`character_count` counts code points rather than grapheme clusters, so a family
emoji built from several code points counts as several. Fixing that would mean
carrying a Unicode segmentation table for a tool whose entire purpose is to be
too boring to be dangerous.
"""

from __future__ import annotations

from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult

TEXT_STATISTICS_SUMMARY = (
    "Count characters, words, and lines in text supplied with the call. "
    "Reads nothing else."
)

TEXT_ARGUMENT = "text"

ACCEPTED_ARGUMENTS: frozenset[str] = frozenset({TEXT_ARGUMENT})

MISSING_TEXT_DETAIL = "This tool requires a 'text' argument."
UNKNOWN_ARGUMENT_DETAIL = "This tool accepts only a 'text' argument."
NON_TEXT_DETAIL = "The 'text' argument must be text."
COUNTED_DETAIL = "Counted the supplied text."


class TextStatisticsTool:
    """Report bounded counts over text passed in the invocation."""

    def __init__(self) -> None:
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.TEXT_STATISTICS,
            effects=frozenset({ToolEffect.COMPUTES_LOCALLY}),
            summary=TEXT_STATISTICS_SUMMARY,
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        """Return the declaration the authorization gate checks."""
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Count the supplied text, or explain what was wrong with the call.

        Every rejection here reports `performed=True, succeeded=False`, because
        the tool did run: it was reached, it looked at what it was given, and it
        declined. Only the gate refuses, and a refusal never reaches this
        method. Mislabelling a bad argument as a refusal would put "not allowed"
        and "not usable" in the same bucket, which is the one distinction the
        authorization boundary exists to keep.

        The details are fixed sentences. Nothing the caller passed is quoted
        back, not the text and not the name of an argument that was not
        expected, because a message is the easiest place for input to escape and
        the hardest place to notice it did.
        """
        if self._unsupported(invocation):
            return self._declined(UNKNOWN_ARGUMENT_DETAIL)
        if not self._supplied(invocation):
            return self._declined(MISSING_TEXT_DETAIL)
        text = invocation.argument(TEXT_ARGUMENT)
        if not isinstance(text, str):
            return self._declined(NON_TEXT_DETAIL)
        return ToolResult(
            capability=ToolCapability.TEXT_STATISTICS,
            performed=True,
            detail=COUNTED_DETAIL,
            succeeded=True,
            values=(
                ("character_count", str(len(text))),
                ("word_count", str(len(text.split()))),
                ("line_count", str(len(text.splitlines()))),
                (
                    "non_whitespace_character_count",
                    str(sum(1 for character in text if not character.isspace())),
                ),
            ),
        )

    @staticmethod
    def _declined(detail: str) -> ToolResult:
        """Report a call this tool ran and refused to answer."""
        return ToolResult(
            capability=ToolCapability.TEXT_STATISTICS,
            performed=True,
            detail=detail,
            succeeded=False,
        )

    @staticmethod
    def _unsupported(invocation: ToolInvocation) -> tuple[str, ...]:
        """Return argument names this tool does not accept."""
        return tuple(
            name for name, _ in invocation.arguments if name not in ACCEPTED_ARGUMENTS
        )

    @staticmethod
    def _supplied(invocation: ToolInvocation) -> bool:
        """Return whether 'text' was passed at all.

        Presence is checked by name rather than by reading the value, because an
        empty string is a real input with real answers and must not be confused
        with a missing one.
        """
        return any(name == TEXT_ARGUMENT for name, _ in invocation.arguments)
