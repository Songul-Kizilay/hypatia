"""What one directory entry is, decided without following it anywhere.

The kinds are deliberately coarse, and one of them is load-bearing. LINK is not
"symlink": it is any reparse point, which on Windows also covers directory
junctions, OneDrive placeholders, and app execution aliases. That distinction
was measured rather than assumed, and it matters more than it looks:

    a junction created by mklink /J reports
        is_symlink()                    -> False
        is_dir(follow_symlinks=False)   -> True
        FILE_ATTRIBUTE_REPARSE_POINT    -> set

So the obvious check — "it is a directory and it is not a symlink, therefore it
is an ordinary directory" — classifies a junction pointing at C:\\Users as safe.
Worse, on the development machine creating a symlink needs elevation and fails
with WinError 1314, while creating a junction needs no privilege at all. The
indirection an unprivileged attacker can actually make is precisely the one the
naive check misses.

Hence every decision here reads the reparse attribute, and falls back to
is_symlink only where that attribute does not exist, which is POSIX.
"""

from __future__ import annotations

import os
import stat
from enum import StrEnum


class FilesystemEntryKind(StrEnum):
    """Name what a directory entry is, without resolving what it points at."""

    DIRECTORY = "directory"
    FILE = "file"
    LINK = "link"
    OTHER = "other"

    @property
    def is_indirection(self) -> bool:
        """Return whether this entry points somewhere this tool will not go."""
        return self is FilesystemEntryKind.LINK

    @property
    def listable(self) -> bool:
        """Return whether listing this entry's contents could ever be allowed.

        A link is excluded even when it points at a directory, because whether
        it does is a question that can only be answered by following it.
        """
        return self is FilesystemEntryKind.DIRECTORY

    @classmethod
    def of(cls, entry: os.DirEntry[str]) -> FilesystemEntryKind:
        """Classify one scanned entry without a single following syscall."""
        return cls.from_status(
            entry.stat(follow_symlinks=False),
            entry.is_symlink(),
        )

    @classmethod
    def from_status(
        cls,
        status: os.stat_result,
        symlink: bool,
    ) -> FilesystemEntryKind:
        """Classify one already-taken no-follow stat.

        Directory scanning and single-entry lookup ask the same question from
        different starting points, and answering it twice would be two
        implementations of one security-relevant rule. This is the one answer;
        `of` is the DirEntry-shaped door into it.

        The caller must have taken the stat without following, because nothing
        here can tell whether it did. Passing a followed stat would describe a
        link's target while calling it the link.
        """
        if is_indirection(status, symlink):
            return cls.LINK
        if stat.S_ISDIR(status.st_mode):
            return cls.DIRECTORY
        if stat.S_ISREG(status.st_mode):
            return cls.FILE
        return cls.OTHER

    @property
    def has_byte_size(self) -> bool:
        """Return whether a byte count means anything for this kind.

        Only a regular file has a length. A directory's stat size is bookkeeping
        about the directory record, not the size of what is inside it, and
        reporting it as `size` would be a number that looks like an answer to a
        question nobody asked.
        """
        return self is FilesystemEntryKind.FILE


def is_indirection(status: os.stat_result, symlink: bool) -> bool:
    """Return whether this stat describes something that points elsewhere.

    The attribute check comes first and is the real one. `symlink` is the POSIX
    fallback, and is also passed on Windows so a symlink is still caught if a
    future filesystem reports one without the reparse attribute.
    """
    attributes = getattr(status, "st_file_attributes", 0)
    if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    return bool(symlink)
