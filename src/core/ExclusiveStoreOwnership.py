"""One process at a time may own a writable durable store.

Two Hypatia processes pointed at one execution store do not race over a field;
they lose whole executions. Each keeps its own picture in memory and each write
replaces the entire document, so whichever saves last erases what the other had
recorded. That was reproduced with two real processes before this existed.

Ownership is an OS lock on a small sidecar file, not the existence of that file.
The difference matters after a crash: a file that merely exists would keep a
dead owner's claim forever and leave somebody deleting it by hand, whereas a
lock held by the kernel is released the moment the owning process ends, however
it ends.

The claim is per store, not per machine. Two processes working on different
stores are no danger to each other and are left alone. Within one process the
same path may be claimed again — the process already owns it, and rebuilding an
application should not deadlock against itself.

Nothing here makes a store safe to share. It makes sharing fail loudly instead
of quietly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from threading import RLock
from typing import IO

from core.Exceptions import BootstrapError

#: Claims held by this process, keyed by the resolved store path. Consulted so a
#: second claim from the same process is recognised as its own rather than
#: refused, which would make an application unable to rebuild itself.
_HELD: dict[str, ExclusiveStoreOwnership] = {}
_REGISTRY_LOCK = RLock()


class ExclusiveStoreOwnership:
    """One process's held claim on one durable store."""

    def __init__(self, path: Path, handle: IO[bytes], key: str) -> None:
        self._path = path
        self._handle = handle
        self._key = key
        self._released = False

    @property
    def path(self) -> Path:
        """Return the store this claim is for."""
        return self._path

    @property
    def held(self) -> bool:
        """Return whether this claim is still in force."""
        return not self._released

    def release(self) -> None:
        """Give up the claim, letting another process take it.

        Ordinarily unnecessary: ending the process releases the lock. It exists
        so a test can hand ownership on without spawning a new process, and is
        safe to call more than once.
        """
        with _REGISTRY_LOCK:
            if self._released:
                return
            self._released = True
            _HELD.pop(self._key, None)
            try:
                _unlock(self._handle)
            finally:
                self._handle.close()


def claim(store_path: Path) -> ExclusiveStoreOwnership:
    """Return this process's exclusive claim on one store, or refuse.

    Refusing is the whole point, so it raises rather than returning something
    falsy that a caller could overlook and then quietly write through.
    """
    if not isinstance(store_path, Path):
        raise BootstrapError("A store claim needs a real path.")
    resolved = store_path.resolve()
    return _claim(
        resolved,
        resolved.with_name(resolved.name + ".lock"),
        "The research execution store is already owned by another Hypatia "
        f"process: {resolved}. Close that one first, or point this process at "
        "a different store.",
    )


def claim_directory(directory: Path) -> ExclusiveStoreOwnership:
    """Return this process's exclusive claim on one writable data directory.

    Claimed rather than each file inside it, because the files in one of these
    directories are written by one runtime as a set. A second process holding
    any of them would be the same data loss, so the directory is the honest
    unit; the files are not independently shareable.
    """
    if not isinstance(directory, Path):
        raise BootstrapError("A directory claim needs a real path.")
    resolved = directory.resolve()
    return _claim(
        resolved,
        resolved / ".hypatia-owner.lock",
        "Another Hypatia process already owns this writable runtime data "
        f"directory: {resolved}. Close that one first, or point this process "
        "at a different data directory.",
    )


def _claim(
    subject: Path,
    lock_path: Path,
    refusal: str,
) -> ExclusiveStoreOwnership:
    """Take one OS lock, or refuse with the caller's own words."""
    key = str(lock_path)
    with _REGISTRY_LOCK:
        existing = _HELD.get(key)
        if existing is not None and existing.held:
            return existing
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = _open_lock(lock_path)
        except OSError as error:
            # On Windows a lock file another owner is still holding can be
            # pending deletion, which refuses to open at all. That is the same
            # answer by a different route: somebody has it.
            raise BootstrapError(refusal) from error
        try:
            _lock(handle)
        except OSError as error:
            handle.close()
            raise BootstrapError(refusal) from error
        owned = ExclusiveStoreOwnership(subject, handle, key)
        _HELD[key] = owned
        return owned


def release_all() -> None:
    """Give up every claim this process holds.

    For a process that is finished with its stores — shutting down, or a test
    tearing a temporary one down. Ending the process does the same thing, but a
    held handle keeps the lock file undeletable on Windows, so anything that
    wants the directory gone afterwards needs to say so.
    """
    with _REGISTRY_LOCK:
        for held in list(_HELD.values()):
            held.release()


def _open_lock(lock_path: Path) -> IO[bytes]:
    """Open the lock file in a way the platform can still tidy up around.

    On Windows the handle is opened so that others may delete the file while it
    is held, and so that it removes itself once released. Without that a held
    claim would make its own directory undeletable, which turns an ownership
    guard into a housekeeping problem for everything that creates a runtime and
    then wants the directory gone.
    """
    if sys.platform == "win32":
        import os

        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_TEMPORARY, 0o600)
        return os.fdopen(descriptor, "r+b")
    return open(lock_path, "a+b")


def _lock(handle: IO[bytes]) -> None:
    """Take the OS lock, without waiting for whoever might hold it."""
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: IO[bytes]) -> None:
    """Release the OS lock, tolerating a handle the platform already freed."""
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        # Closing the handle releases it regardless, and a platform that has
        # already done so is not an error worth propagating out of a release.
        return
