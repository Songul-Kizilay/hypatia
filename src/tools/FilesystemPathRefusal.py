"""Why one requested path was not admitted, as a bounded value.

A raw OSError is exactly the wrong thing to carry out of a filesystem boundary:
Windows error strings interpolate the full path, and the full path is the one
piece of information this capability exists to control. So refusals are named,
not described, and the sentence a person reads is looked up from the name.

NONE means admitted, following the same idiom as `ToolCapability.NONE`: an
absent refusal is a value rather than a null every caller must remember to
check.

The taxonomy keeps "outside the root" and "no such entry" apart, which is a
deliberate decision rather than an oversight. Separating them lets a caller
distinguish a typo from a boundary, and it discloses nothing: the caller was
given the root, so it can already compute which paths are inside it. If a
future capability is ever granted to something that does not know the root,
this decision has to be revisited rather than inherited.
"""

from __future__ import annotations

from enum import StrEnum


class FilesystemPathRefusal(StrEnum):
    """Name one bounded reason a path was not admitted inside the root."""

    NONE = "none"
    NOT_RELATIVE = "not_relative"
    STREAM_SYNTAX = "stream_syntax"
    RESERVED_DEVICE = "reserved_device"
    ESCAPES_ROOT = "escapes_root"
    LINK_COMPONENT = "link_component"
    MISSING = "missing"
    NOT_A_DIRECTORY = "not_a_directory"
    UNREADABLE = "unreadable"

    @property
    def admitted(self) -> bool:
        """Return whether the path was accepted."""
        return self is FilesystemPathRefusal.NONE

    @property
    def concerns_containment(self) -> bool:
        """Return whether the path was refused for leaving the authorized root.

        Link components count. A junction inside the root is lexically
        contained and actually is not, and treating that as a different sort of
        problem from `..` would suggest it is a smaller one.
        """
        return self in (
            FilesystemPathRefusal.NOT_RELATIVE,
            FilesystemPathRefusal.ESCAPES_ROOT,
            FilesystemPathRefusal.LINK_COMPONENT,
        )
