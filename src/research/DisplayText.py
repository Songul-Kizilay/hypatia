"""Reduce authored text to something safe to render beside other records.

Reports here list records one per line. A record whose own text contains a line
break can therefore forge entries in the report it appears in — a failure
reason typed by a person becoming a lesson the system never derived, sitting in
the list looking exactly like one it did.

The defence belongs next to the text rather than at each place that prints it.
A rendering convention every composer has to remember is one a composer will
eventually forget, and the forgetting is invisible until someone reads a report
that is quietly wrong.
"""

from __future__ import annotations

#: What a shortened value ends with, so a reader can tell it was cut.
ELLIPSIS = "..."


def one_line(value: str) -> str:
    """Collapse any run of whitespace, including line breaks, to one space."""
    return " ".join(value.split())


def one_bounded_line(value: str, limit: int) -> str:
    """Collapse to one line and shorten it to fit, marking that it was cut."""
    if limit < 1:
        raise ValueError("A display limit must be positive.")
    collapsed = one_line(value)
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(limit - len(ELLIPSIS), 1)] + ELLIPSIS
