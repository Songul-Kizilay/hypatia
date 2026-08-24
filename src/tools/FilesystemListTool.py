"""List one directory level inside the authorized root, and nothing else.

This is the first capability where the argument selects the target. The two
tools before it were safe by construction — a clock cannot be pointed anywhere,
and counting words only ever touches the words it was handed. Here a bad
argument does not produce a wrong answer; it produces a correct answer about the
wrong thing, which is worse, because nothing looks broken.

So the boundary lives in `FilesystemRoot` and this tool never joins a path
itself. It asks the root to admit one, receives either a path or a bounded
reason, and turns the reason into a fixed sentence. Nothing the caller passed is
quoted back — not the path, not an entry name, not an OSError, whose Windows
text interpolates the full path it failed on.

Nothing is followed. An entry that is a reparse point is reported as a link and
its target is neither resolved nor described, so a junction pointing at
C:\\Users appears as a link named whatever it is named and stops there.

Bounding, and why it is paging rather than a bigger limit
--------------------------------------------------------
`ToolResult` allows 20 values. A directory can hold thousands. Raising that
limit was the obvious fix and the wrong one: the bound protects every tool, and
relaxing it here would relax it for tools that have no business returning
hundreds of values.

So the result is a page. Five values describe the directory and fifteen carry
entries, which is exactly the existing budget and requires no change to any
shared limit. The caller pages with `offset`. Both kinds of incompleteness are
reported separately, because collapsing them would let "this directory has more
in it" and "this page has more after it" look like the same statement:

    entry_count        entries counted in this directory
    entries_exceeded   the directory holds more than the scan ceiling
    page_offset        where this page starts
    page_size          entries in this page
    more_pages         entries remain after this page

Ordering is by casefolded name with the exact name as a tie-break, over the
whole collected set rather than the page, so paging is stable: entry 16 is the
same entry whether it is read first or last.
"""

from __future__ import annotations

import os
from pathlib import Path

from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import MAX_TOOL_VALUES, ToolResult

FILESYSTEM_LIST_SUMMARY = (
    "List the entries directly inside one directory of the authorized root. "
    "Reads no file contents."
)

PATH_ARGUMENT = "path"
OFFSET_ARGUMENT = "offset"

ACCEPTED_ARGUMENTS: frozenset[str] = frozenset({PATH_ARGUMENT, OFFSET_ARGUMENT})

#: Values describing the directory rather than an entry in it.
SUMMARY_VALUE_COUNT = 5

#: Entries carried by one page. Derived from the shared result budget rather
#: than chosen, so this tool can never quietly outgrow it.
PAGE_SIZE = MAX_TOOL_VALUES - SUMMARY_VALUE_COUNT

#: How many entries the tool will read before giving up on counting exactly.
#: The whole set is collected so the sort — and therefore paging — is over
#: complete information; a ceiling that truncated the scan would make page two
#: depend on the order the filesystem happened to return names in.
MAX_SCANNED_ENTRIES = 2_000

MAX_ENTRY_NAME_LENGTH = 255

_DETAILS: dict[FilesystemPathRefusal, str] = {
    FilesystemPathRefusal.NOT_RELATIVE: (
        "The path must be relative to the authorized root."
    ),
    FilesystemPathRefusal.STREAM_SYNTAX: "That is not a valid path.",
    FilesystemPathRefusal.RESERVED_DEVICE: "That is not a file.",
    FilesystemPathRefusal.ESCAPES_ROOT: "That path is outside the authorized root.",
    FilesystemPathRefusal.LINK_COMPONENT: "That path goes through a link, which is "
    "not followed.",
    FilesystemPathRefusal.MISSING: "There is no such entry.",
    FilesystemPathRefusal.NOT_A_DIRECTORY: "That is not a directory.",
    FilesystemPathRefusal.UNREADABLE: "That path could not be read.",
}

MISSING_PATH_DETAIL = "This tool requires a 'path' argument."
UNKNOWN_ARGUMENT_DETAIL = "This tool accepts only 'path' and 'offset' arguments."
BAD_OFFSET_DETAIL = "The 'offset' argument must be a whole number of entries."
NOT_TEXT_DETAIL = "The 'path' argument must be text."
LISTED_DETAIL = "Listed one directory."


class FilesystemListTool:
    """Report the entries directly inside one authorized directory."""

    def __init__(self, root: FilesystemRoot) -> None:
        """Take the one root this tool may ever see inside.

        The root is required. There is no default and no unconfigured mode: a
        runtime with no root configured registers no filesystem tool at all,
        because a registered tool that refuses everything is one configuration
        mistake away from working.
        """
        if not isinstance(root, FilesystemRoot):
            raise TypeError("A filesystem list tool requires a configured root.")
        self._root = root
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.FILESYSTEM_LIST,
            effects=frozenset({ToolEffect.READS_FILESYSTEM_METADATA}),
            summary=FILESYSTEM_LIST_SUMMARY,
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        """Return the declaration the authorization gate checks."""
        return self._descriptor

    @property
    def root_id(self) -> str:
        """Return the opaque identifier standing in for the root's path."""
        return self._root.root_id

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """List one directory, or say plainly why this call listed nothing.

        Every outcome here reports `performed=True, succeeded=False`. The tool
        ran: it was reached, it looked at what it was given, and it either
        declined the request or accepted it and could not finish. Which of those
        two is recorded as bounded state rather than left to the wording, since
        one says fix the path and the other says look at the machine. Only the
        effect gate refuses, and a refusal never reaches this method.
        """
        if self._unsupported(invocation):
            return self._declined(UNKNOWN_ARGUMENT_DETAIL)
        if not self._supplied(invocation, PATH_ARGUMENT):
            return self._declined(MISSING_PATH_DETAIL)
        requested = invocation.argument(PATH_ARGUMENT)
        if not isinstance(requested, str):
            return self._declined(NOT_TEXT_DETAIL)
        offset = self._offset(invocation)
        if offset is None:
            return self._declined(BAD_OFFSET_DETAIL)
        refusal, directory = self._root.locate(requested)
        if not refusal.admitted or directory is None:
            # The bounded refusal reason decides which this was. Every reason is
            # about the request except UNREADABLE, which is the filesystem
            # declining to answer a question that was properly formed.
            if refusal is FilesystemPathRefusal.UNREADABLE:
                return self._failed(_DETAILS[refusal])
            return self._declined(_DETAILS[refusal])
        return self._list(directory, offset)

    def _list(self, directory: Path, offset: int) -> ToolResult:
        """Scan one directory level, then report a bounded page of it."""
        try:
            names = self._scan(directory)
        except NotADirectoryError:
            return self._declined(_DETAILS[FilesystemPathRefusal.NOT_A_DIRECTORY])
        except FileNotFoundError:
            return self._declined(_DETAILS[FilesystemPathRefusal.MISSING])
        except OSError:
            # No WinError text crosses this boundary: it interpolates the path.
            # The tool had accepted the request and started reading, so this is
            # a failed attempt rather than a rejected request.
            return self._failed(_DETAILS[FilesystemPathRefusal.UNREADABLE])
        if not self._still_contained(directory):
            # Re-checked after the scan. This narrows the window between
            # validating and reading; it does not close it. See the module
            # docstring in FilesystemRoot for what remains possible.
            return self._declined(_DETAILS[FilesystemPathRefusal.ESCAPES_ROOT])
        entries, exceeded = names
        page = entries[offset : offset + PAGE_SIZE]
        values: list[tuple[str, str]] = [
            ("entry_count", str(len(entries))),
            ("entries_exceeded", str(exceeded).lower()),
            ("page_offset", str(offset)),
            ("page_size", str(len(page))),
            ("more_pages", str(offset + len(page) < len(entries)).lower()),
        ]
        values.extend(
            (f"entry_{index}", value)
            for index, value in enumerate(page, start=offset + 1)
        )
        return ToolResult(
            capability=ToolCapability.FILESYSTEM_LIST,
            performed=True,
            detail=LISTED_DETAIL,
            succeeded=True,
            values=tuple(values),
        )

    def _scan(self, directory: Path) -> tuple[tuple[str, ...], bool]:
        """Collect one directory level as sorted `kind:name` text.

        The whole level is collected before sorting, so the order a page is cut
        from does not depend on the order the filesystem returned names in. An
        entry that disappears while the scan is running is dropped rather than
        guessed at, because a name is all this tool ever had and it no longer
        has that.
        """
        collected: list[str] = []
        exceeded = False
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(collected) >= MAX_SCANNED_ENTRIES:
                    exceeded = True
                    break
                try:
                    kind = FilesystemEntryKind.of(entry)
                except OSError:
                    continue
                collected.append(f"{kind.value}:{entry.name[:MAX_ENTRY_NAME_LENGTH]}")
        collected.sort(key=lambda value: (value.casefold(), value))
        return (tuple(collected), exceeded)

    def _still_contained(self, directory: Path) -> bool:
        """Return whether the listed directory is still inside the root."""
        try:
            return self._root.contains(directory.resolve())
        except OSError:
            return False

    @staticmethod
    def _offset(invocation: ToolInvocation) -> int | None:
        """Return the requested page start, refusing anything that is not one."""
        raw = invocation.argument(OFFSET_ARGUMENT)
        if not isinstance(raw, str):
            return None
        text = raw.strip()
        if not text:
            return 0
        if not text.isdigit():
            return None
        return int(text)

    @staticmethod
    def _declined(detail: str) -> ToolResult:
        """Report a request this tool read and would not take.

        Nothing was listed and nothing was attempted. The path, the arguments,
        or the scope is what would have to change.
        """
        return ToolResult.declined(ToolCapability.FILESYSTEM_LIST, detail)

    @staticmethod
    def _failed(detail: str) -> ToolResult:
        """Report a request this tool accepted and could not finish.

        Used only where the filesystem itself refused work that had already
        begun. That is not the caller asking badly, and reporting it as a
        decline would send someone to rewrite a path that was never the
        problem.
        """
        return ToolResult.failed(ToolCapability.FILESYSTEM_LIST, detail)

    @staticmethod
    def _unsupported(invocation: ToolInvocation) -> tuple[str, ...]:
        """Return argument names this tool does not accept."""
        return tuple(
            name for name, _ in invocation.arguments if name not in ACCEPTED_ARGUMENTS
        )

    @staticmethod
    def _supplied(invocation: ToolInvocation, name: str) -> bool:
        """Return whether one argument was passed at all, empty or not."""
        return any(candidate == name for candidate, _ in invocation.arguments)
