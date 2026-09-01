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

    def __init__(self, path: Path, handle: IO[bytes]) -> None:
        self._path = path
        self._handle = handle
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
            _HELD.pop(str(self._path), None)
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
    key = str(resolved)
    with _REGISTRY_LOCK:
        existing = _HELD.get(key)
        if existing is not None and existing.held:
            return existing
        lock_path = resolved.with_name(resolved.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+b")
        try:
            _lock(handle)
        except OSError as error:
            handle.close()
            raise BootstrapError(
                "The research execution store is already owned by another "
                f"Hypatia process: {resolved}. Close that one first, or point "
                "this process at a different store."
            ) from error
        owned = ExclusiveStoreOwnership(resolved, handle)
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
