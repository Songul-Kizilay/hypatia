"""Split a reply into styled segments so Markdown markers stop showing raw.

The desktop transcript is a plain Tk text widget, so a reply containing
`**Morvella**` displayed the asterisks. This module turns such a string into
styled segments the widget can tag. It is pure text handling: no Tk import, no
widget, no rendering decision beyond which span carries which style.

The parser is deliberately small and conservative. It handles bold, italic, and
inline code, nothing else, and it never spans a line break. Anything it cannot
match — an unclosed marker, an empty span, an underscore inside an identifier —
is emitted literally, because losing a character of a reply is worse than
showing a stray asterisk. Concatenating every segment always reproduces the
input exactly, and a test asserts it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarkdownStyle(StrEnum):
    """The bounded set of styles the transcript knows how to draw."""

    PLAIN = "plain"
    BOLD = "bold"
    ITALIC = "italic"
    CODE = "code"


@dataclass(frozen=True, slots=True)
class MarkdownSegment:
    """One run of text with a single style."""

    text: str
    style: MarkdownStyle = MarkdownStyle.PLAIN


def markdown_segments(value: str) -> tuple[MarkdownSegment, ...]:
    """Return styled segments whose concatenated text equals the input."""
    if not isinstance(value, str) or not value:
        return ()
    segments: list[MarkdownSegment] = []
    plain: list[str] = []
    index = 0
    length = len(value)

    def flush() -> None:
        if plain:
            segments.append(MarkdownSegment("".join(plain)))
            plain.clear()

    while index < length:
        span = _span_at(value, index)
        if span is None:
            plain.append(value[index])
            index += 1
            continue
        inner, style, consumed = span
        flush()
        segments.append(MarkdownSegment(inner, style))
        index += consumed

    flush()
    return tuple(segments)


def rendered_text(segments: tuple[MarkdownSegment, ...]) -> str:
    """Return what the reader sees, with the markers removed."""
    return "".join(segment.text for segment in segments)


def _span_at(value: str, index: int) -> tuple[str, MarkdownStyle, int] | None:
    """Return the span opening at this index, or None when none does."""
    if value.startswith("`", index):
        return _delimited(value, index, "`", MarkdownStyle.CODE)
    if value.startswith("**", index):
        return _delimited(value, index, "**", MarkdownStyle.BOLD)
    if value.startswith("*", index):
        return _delimited(value, index, "*", MarkdownStyle.ITALIC)
    if value.startswith("_", index) and _underscore_opens(value, index):
        return _delimited(value, index, "_", MarkdownStyle.ITALIC)
    return None


def _delimited(
    value: str,
    index: int,
    marker: str,
    style: MarkdownStyle,
) -> tuple[str, MarkdownStyle, int] | None:
    """Match one non-empty span closed by the same marker on the same line."""
    start = index + len(marker)
    end = value.find(marker, start)
    if end == -1 or end == start:
        return None
    if "\n" in value[start:end]:
        return None
    if marker == "_" and not _underscore_closes(value, end):
        return None
    return value[start:end], style, end + len(marker) - index


def _underscore_opens(value: str, index: int) -> bool:
    """Refuse an underscore that sits inside a word, so identifiers survive."""
    return index == 0 or not value[index - 1].isalnum()


def _underscore_closes(value: str, end: int) -> bool:
    """Refuse a closing underscore followed by more of the same word."""
    after = end + 1
    return after >= len(value) or not value[after].isalnum()
