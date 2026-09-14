"""The one directory a filesystem capability may see inside, set by the operator.

The root is configuration and never an argument. A tool that took its root from
the invocation would have unrestricted filesystem authority with extra steps,
because the caller would simply pass the drive. So it is resolved once, here,
and a request supplies only a relative path within it.

Containment is decided on the resolved path. A string prefix comparison looks
equivalent and is not:

    r"D:\\hypatia-main-secrets\\notes.txt".startswith(r"D:\\hypatia-main")   -> True
    Path(same).is_relative_to(r"D:\\hypatia-main")                          -> False

A sibling directory whose name merely begins with the root's name passes the
first check. That is the most likely way to build this wrongly and it fails
silently, so it has a named test.

Links are refused rather than followed, and the check runs on every component
rather than the last one. `resolve()` follows indirection silently, so by the
time a resolved path is available the traversal has already happened; the walk
therefore lstats each lexical component itself. What counts as a link is
decided by the reparse attribute rather than `is_symlink`, because a Windows
junction answers False to that question — see `FilesystemEntryKind`.

What this cannot promise: that the path is still inside the root at the moment
it is read. Validation and access are separate syscalls, Python offers no
atomic validate-and-open for a directory listing on Windows, and an attacker
with write access to the root can replace a component in between. That risk is
accepted here because the prize is a list of names and because such an attacker
already has write access to the user's own project directory. It would not be
acceptable for a capability that returned file contents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from core.Exceptions import ResearchError
from tools.FilesystemEntryKind import is_indirection
from tools.FilesystemPathRefusal import FilesystemPathRefusal

MAX_ROOT_ID_LENGTH = 64
MAX_RELATIVE_PATH_LENGTH = 1_024
MAX_PATH_DEPTH = 32

#: Names the Windows device namespace answers to from inside any directory.
#: `NUL` reports as existing in every directory it is asked about, so a
#: containment check alone admits it. It is refused by name because a confident
#: answer about a device that is not a file is the wrong kind of wrong.
RESERVED_DEVICE_NAMES: frozenset[str] = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"com{digit}" for digit in range(1, 10)}
    | {f"lpt{digit}" for digit in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class FilesystemRoot:
    """Hold one resolved directory and admit only paths that stay inside it."""

    path: Path
    root_id: str = field(default="root-1")

    def __post_init__(self) -> None:
        if not isinstance(self.root_id, str) or not self.root_id.strip():
            raise ResearchError("A filesystem root needs an identifier.")
        if len(self.root_id) > MAX_ROOT_ID_LENGTH:
            raise ResearchError("A filesystem root identifier is too long.")
        if not isinstance(self.path, Path):
            raise ResearchError("A filesystem root must be a path.")
        expanded = self.path.expanduser()
        # Checked before resolving, not after. `resolve()` follows indirection
        # silently, so a root configured as a junction would arrive here as its
        # own target and pass a link check cleanly — the operator would have
        # pointed at one directory and authorised another.
        try:
            given = expanded.lstat()
        except OSError as error:
            raise ResearchError(
                "A filesystem root must be an existing directory."
            ) from error
        if is_indirection(given, expanded.is_symlink()):
            raise ResearchError("A filesystem root cannot be a link.")
        resolved = expanded.resolve()
        if not resolved.is_absolute():
            raise ResearchError("A filesystem root must be absolute.")
        if not resolved.is_dir():
            raise ResearchError("A filesystem root must be an existing directory.")
        object.__setattr__(self, "path", resolved)

    def depth_of(self, relative: str) -> int:
        """Return how many components a request names, for safe telemetry.

        Depth is shape, not content. It is the one thing about a requested path
        that can be reported without disclosing where the person was looking.
        """
        if not isinstance(relative, str):
            return 0
        candidate = relative.strip().replace("\\", "/")
        return len([part for part in candidate.split("/") if part not in ("", ".")])

    def locate(self, relative: str) -> tuple[FilesystemPathRefusal, Path | None]:
        """Return the admitted path inside the root, or why it was refused.

        The order matters and each step catches something the next would miss.
        Rooted forms are rejected before joining, because joining them silently
        discards the root: on Windows a leading slash is not absolute, it
        inherits the root's drive, so `/Windows` under `D:\\project` becomes
        `D:\\Windows` — inside no root at all.
        """
        if not isinstance(relative, str):
            return (FilesystemPathRefusal.NOT_RELATIVE, None)
        candidate = relative.strip()
        if len(candidate) > MAX_RELATIVE_PATH_LENGTH:
            return (FilesystemPathRefusal.NOT_RELATIVE, None)
        if not candidate or candidate == ".":
            return (FilesystemPathRefusal.NONE, self.path)
        if self._is_rooted(candidate):
            return (FilesystemPathRefusal.NOT_RELATIVE, None)
        if ":" in candidate:
            # The drive check has already run, so a colon can only be NTFS
            # stream syntax here. `README.md::$DATA` resolves to the plain file
            # while keeping the stream text in `.name`, so neither the resolved
            # path nor the name can be trusted to reveal it.
            return (FilesystemPathRefusal.STREAM_SYNTAX, None)
        parts = self._normalized_parts(candidate)
        if parts is None:
            return (FilesystemPathRefusal.ESCAPES_ROOT, None)
        if len(parts) > MAX_PATH_DEPTH:
            return (FilesystemPathRefusal.NOT_RELATIVE, None)
        if any(self._is_reserved_device(part) for part in parts):
            return (FilesystemPathRefusal.RESERVED_DEVICE, None)
        return self._walk(parts)

    def contains(self, resolved: Path) -> bool:
        """Return whether an already-resolved path lies inside this root."""
        try:
            return resolved.is_relative_to(self.path)
        except OSError, ValueError:
            return False

    @staticmethod
    def _is_rooted(candidate: str) -> bool:
        """Return whether the argument names a place rather than a direction.

        Both path flavours are consulted, so a Windows escape is refused on
        POSIX and a POSIX one on Windows. The tool should not become safer or
        weaker depending on where it happens to run.
        """
        for flavour in (PureWindowsPath(candidate), PurePosixPath(candidate)):
            if flavour.is_absolute() or flavour.drive or flavour.anchor:
                return True
        return False

    @staticmethod
    def _normalized_parts(candidate: str) -> tuple[str, ...] | None:
        """Collapse `..` lexically, refusing anything that climbs out.

        Collapsing before touching the filesystem is what makes the per
        component walk correct: walking the raw text would lstat directories
        the request never meant to visit, and a missing one of those would
        refuse a path that is in fact fine.
        """
        # normpath answers in the platform separator, so on Windows it hands
        # back backslashes. Splitting those with PurePosixPath yields one
        # component containing the whole path, which silently disables every
        # per-component check below. Normalising back is not cosmetic.
        normalized = os.path.normpath(candidate.replace("\\", "/")).replace("\\", "/")
        parts = tuple(
            part for part in PurePosixPath(normalized).parts if part not in ("", ".")
        )
        if any(part == ".." for part in parts):
            return None
        return parts

    @staticmethod
    def _is_reserved_device(part: str) -> bool:
        """Return whether one component names the device namespace.

        The stem before the first dot is what matters: `con.txt` reaches the
        console just as `con` does, so extensions do not make a device safe.
        """
        return part.split(".")[0].casefold() in RESERVED_DEVICE_NAMES

    def _walk(
        self,
        parts: tuple[str, ...],
    ) -> tuple[FilesystemPathRefusal, Path | None]:
        """Descend one component at a time, refusing any link on the way down.

        Checking only the final component would miss `root/link/file.txt`,
        where the indirection is passed through rather than landed on.
        """
        current = self.path
        for part in parts:
            current = current / part
            try:
                status = current.lstat()
            except FileNotFoundError:
                return (FilesystemPathRefusal.MISSING, None)
            except NotADirectoryError:
                return (FilesystemPathRefusal.NOT_A_DIRECTORY, None)
            except OSError:
                return (FilesystemPathRefusal.UNREADABLE, None)
            if is_indirection(status, current.is_symlink()):
                return (FilesystemPathRefusal.LINK_COMPONENT, None)
        try:
            resolved = current.resolve()
        except OSError:
            return (FilesystemPathRefusal.UNREADABLE, None)
        if not self.contains(resolved):
            return (FilesystemPathRefusal.ESCAPES_ROOT, None)
        return (FilesystemPathRefusal.NONE, resolved)
