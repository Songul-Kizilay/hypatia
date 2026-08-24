"""What kind of value one tool argument accepts, for a typed control.

Kinds exist so the console can offer a checkbox-shaped question rather than a
text box for everything. They are presentation-level: the tool still validates
its own arguments, and this never replaces that. It only stops obviously wrong
input from becoming an invocation at all, which keeps the audit trail free of
executions that were never going to work.

There is deliberately no FREE_FORM kind. An argument nobody can describe is an
argument nobody can review, and the moment one exists the console becomes a
place to type whatever the tool layer happens to accept today.
"""

from __future__ import annotations

from enum import StrEnum


class ToolArgumentKind(StrEnum):
    """Name the shape of one bounded argument value."""

    TEXT = "text"
    RELATIVE_PATH = "relative_path"
    WHOLE_NUMBER = "whole_number"

    @property
    def multiline(self) -> bool:
        """Return whether this value deserves more than one line of input."""
        return self is ToolArgumentKind.TEXT

    def rejects(self, value: str) -> bool:
        """Return whether this value is obviously wrong for this kind.

        Obviously, not exhaustively. A relative path is refused here only for
        the forms that are never relative under any rule; deciding what is
        actually inside the root belongs to the root, which is the only thing
        that knows where the root is.
        """
        if not isinstance(value, str):
            return True
        if self is ToolArgumentKind.WHOLE_NUMBER:
            return bool(value.strip()) and not value.strip().isdigit()
        if self is ToolArgumentKind.RELATIVE_PATH:
            stripped = value.strip()
            return stripped.startswith(("/", "\\")) or ":" in stripped
        return False
