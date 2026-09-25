"""One observed HTTP response header, preserved exactly as received.

A header value can legitimately repeat under the same name (for example
multiple `Set-Cookie` headers) or itself contain a `:` (for example a `Link`
header, or a `Date` value's comma), so this record never merges, dedups, or
re-interprets what a reviewed `curl --head` invocation returned. Casing is
never folded: `Content-Type` and `content-type` are stored as whatever the
server actually sent. A tuple of these records — never a dict, which would
silently drop duplicates or reorder — is what holds one complete observed
header set elsewhere in this milestone.

Every field here is untrusted display/storage data with zero instruction
authority. It is never parsed as a shell command, never dispatched as a
Brain intent, and never consulted by scope resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_HTTP_HEADER_NAME_CHARACTERS = 500
MAX_HTTP_HEADER_VALUE_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchHttpHeaderRecord:
    """One observed `Name: Value` header pair, preserved verbatim."""

    name: str
    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or "\x00" in self.name
            or "\r" in self.name
            or "\n" in self.name
        ):
            raise ResearchError("HTTP header name is invalid.")
        if len(self.name) > MAX_HTTP_HEADER_NAME_CHARACTERS:
            raise ResearchError("HTTP header name is too long.")
        if (
            not isinstance(self.value, str)
            or "\x00" in self.value
            or "\r" in self.value
            or "\n" in self.value
        ):
            raise ResearchError("HTTP header value is invalid.")
        if len(self.value) > MAX_HTTP_HEADER_VALUE_CHARACTERS:
            raise ResearchError("HTTP header value is too long.")
