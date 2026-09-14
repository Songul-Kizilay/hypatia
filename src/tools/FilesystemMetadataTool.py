"""Report a few bounded facts about one named entry, and nothing inside it.

The governing rule for this capability is that Hypatia may learn facts *about* a
file without gaining the ability to read what is in it. Everything here is
shaped by that line: the tool takes a no-follow stat and reports four fields
from it, and there is no code path that opens anything.

It reuses `FilesystemRoot.locate` rather than re-deriving admission. That is
deliberate and it is most of the security argument. `locate` already rejects
rooted, drive-qualified, UNC, extended-length, stream-syntax, reserved-device,
over-deep and over-long paths, collapses `..` and refuses anything that climbs
out, walks every component with `lstat` refusing reparse points, and checks
containment on the resolved path. A second implementation of that would be a
second thing to get right, and the two would drift.

One consequence is worth stating rather than discovering: because `locate`
checks *every* component including the last, an entry that is itself a symlink
or junction is refused. This tool therefore never describes a link, never
follows one, and never reports a target's metadata as though it were the link's.
That is the safe model and it costs nothing, because the same rule already
governs listing.

The stat that is reported is the stat that was checked. After `locate` admits a
path, this takes one more `lstat` and re-examines *that* result for
indirection before using it, so the fields returned describe the object the
check was performed on rather than whatever occupied the path a moment earlier.
That narrows the race between validation and use; it does not remove it, and
the module docstring of `FilesystemRoot` says plainly what remains possible.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult

FILESYSTEM_METADATA_SUMMARY = (
    "Report the kind, size and modification time of one entry in the authorized "
    "root. Reads no file contents."
)

PATH_ARGUMENT = "path"

ACCEPTED_ARGUMENTS: frozenset[str] = frozenset({PATH_ARGUMENT})

MAX_ENTRY_NAME_LENGTH = 255

MISSING_PATH_DETAIL = "This tool requires a 'path' argument."
UNKNOWN_ARGUMENT_DETAIL = "This tool accepts only a 'path' argument."
NOT_TEXT_DETAIL = "The 'path' argument must be text."
DESCRIBED_DETAIL = "Described one entry."
VANISHED_DETAIL = "The entry existed when it was checked and no longer does."
CHANGED_DETAIL = "The entry changed while it was being examined."
UNREADABLE_DETAIL = "That entry could not be read."

_DETAILS: dict[FilesystemPathRefusal, str] = {
    FilesystemPathRefusal.NOT_RELATIVE: (
        "The path must be relative to the authorized root."
    ),
    FilesystemPathRefusal.STREAM_SYNTAX: "That is not a valid path.",
    FilesystemPathRefusal.RESERVED_DEVICE: "That is not a file.",
    FilesystemPathRefusal.ESCAPES_ROOT: "That path is outside the authorized root.",
    FilesystemPathRefusal.LINK_COMPONENT: (
        "That path goes through a link, which is not followed."
    ),
    FilesystemPathRefusal.MISSING: "There is no such entry.",
    FilesystemPathRefusal.NOT_A_DIRECTORY: "That is not a directory.",
    FilesystemPathRefusal.UNREADABLE: UNREADABLE_DETAIL,
}


class FilesystemMetadataTool:
    """Describe one authorized entry without opening it."""

    def __init__(self, root: FilesystemRoot) -> None:
        """Take the one root this tool may ever look inside."""
        if not isinstance(root, FilesystemRoot):
            raise TypeError("A filesystem metadata tool requires a configured root.")
        self._root = root
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.FILESYSTEM_METADATA,
            effects=frozenset({ToolEffect.READS_FILESYSTEM_METADATA}),
            summary=FILESYSTEM_METADATA_SUMMARY,
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
        """Describe one entry, or say plainly why it described nothing.

        The two unsuccessful outcomes are kept apart deliberately. A path this
        tool will not accept is a decline: nothing was attempted and the request
        is what would have to change. A path that was accepted and then could
        not be read is a failed attempt, because the request was fine and the
        machine was not.
        """
        if self._unsupported(invocation):
            return self._declined(UNKNOWN_ARGUMENT_DETAIL)
        if not self._supplied(invocation):
            return self._declined(MISSING_PATH_DETAIL)
        requested = invocation.argument(PATH_ARGUMENT)
        if not isinstance(requested, str):
            return self._declined(NOT_TEXT_DETAIL)
        refusal, entry = self._root.locate(requested)
        if not refusal.admitted or entry is None:
            if refusal is FilesystemPathRefusal.UNREADABLE:
                return self._failed(_DETAILS[refusal])
            return self._declined(_DETAILS[refusal])
        return self._describe(entry)

    def _describe(self, entry: Path) -> ToolResult:
        """Take one no-follow stat and report only what it plainly says.

        Everything after this point comes from a single `lstat`. There is no
        second syscall to disagree with it, no directory scan, and nothing that
        opens the entry — so the answer describes one object at one moment
        rather than being assembled from several.
        """
        try:
            status = entry.lstat()
        except FileNotFoundError:
            # It was there when `locate` walked to it. Something removed it in
            # between, which is a fact about the machine rather than about the
            # request, so it is reported as a failed attempt.
            return self._failed(VANISHED_DETAIL)
        except OSError:
            return self._failed(UNREADABLE_DETAIL)
        kind = FilesystemEntryKind.from_status(status, entry.is_symlink())
        if kind.is_indirection:
            # `locate` refuses links, so reaching here means the entry became
            # one after it was checked. Reporting on it anyway would describe an
            # object that never passed the boundary.
            return self._failed(CHANGED_DETAIL)
        if not self._root.contains(entry):
            return self._failed(CHANGED_DETAIL)
        values: list[tuple[str, str]] = [
            ("name", entry.name[:MAX_ENTRY_NAME_LENGTH]),
            ("kind", kind.value),
            ("modified_utc", self._modified(status)),
        ]
        if kind.has_byte_size:
            # Only a regular file has a length. A directory is left without a
            # size rather than given a misleading one; `kind` says why it is
            # absent.
            values.append(("size_bytes", str(status.st_size)))
        return ToolResult(
            capability=ToolCapability.FILESYSTEM_METADATA,
            performed=True,
            detail=DESCRIBED_DETAIL,
            succeeded=True,
            values=tuple(values),
        )

    @staticmethod
    def _modified(status: os.stat_result) -> str:
        """Render the modification time as UTC seconds, and only that.

        Whole seconds because filesystems disagree below that — NTFS keeps
        100-nanosecond ticks, ext4 nanoseconds, FAT two-second granularity — and
        a field whose precision depends on the volume is a field that cannot be
        compared. UTC because a local time without an offset is a number that
        means different things on different machines.
        """
        moment = datetime.fromtimestamp(status.st_mtime, tz=UTC)
        return moment.isoformat(timespec="seconds")

    @staticmethod
    def _declined(detail: str) -> ToolResult:
        """Report a request this tool read and would not take."""
        return ToolResult.declined(ToolCapability.FILESYSTEM_METADATA, detail)

    @staticmethod
    def _failed(detail: str) -> ToolResult:
        """Report a request this tool accepted and could not answer."""
        return ToolResult.failed(ToolCapability.FILESYSTEM_METADATA, detail)

    @staticmethod
    def _unsupported(invocation: ToolInvocation) -> tuple[str, ...]:
        """Return argument names this tool does not accept."""
        return tuple(
            name for name, _ in invocation.arguments if name not in ACCEPTED_ARGUMENTS
        )

    @staticmethod
    def _supplied(invocation: ToolInvocation) -> bool:
        """Return whether 'path' was passed at all, empty or not."""
        return any(name == PATH_ARGUMENT for name, _ in invocation.arguments)
