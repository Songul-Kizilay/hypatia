"""Single-flight background execution boundary for the Tkinter desktop."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock, Thread
from typing import Literal


@dataclass(frozen=True, slots=True)
class DesktopRequestCompletion[T]:
    """One worker result consumed only by the Tkinter main thread."""

    value: T | None = None
    error: Exception | None = None
    cancelled: bool = False


class DesktopRequestRunner:
    """Run at most one bounded desktop action away from the Tk event loop."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._running = False
        self._stopped = False
        self._cancel_requested = False
        self._cancel_callback: Callable[[], None] | None = None
        self._completions: deque[DesktopRequestCompletion[object]] = deque()

    def start[T](
        self,
        action: Callable[[], T],
        *,
        cancel_callback: Callable[[], None] | None = None,
    ) -> Literal["started", "busy", "stopped", "failed"]:
        """Start one daemon request without queueing a second request."""
        with self._lock:
            if self._stopped:
                return "stopped"
            if self._running or self._completions:
                return "busy"
            self._running = True
            self._cancel_requested = False
            self._cancel_callback = cancel_callback
            worker = Thread(
                target=self._run,
                args=(action,),
                name="hypatia-desktop-request",
                daemon=True,
            )
        try:
            worker.start()
        except Exception:
            with self._lock:
                self._running = False
                self._cancel_callback = None
            return "failed"
        return "started"

    def _run(self, action: Callable[[], object]) -> None:
        try:
            completion = DesktopRequestCompletion(value=action())
        except Exception as error:
            completion = DesktopRequestCompletion(error=error)
        with self._lock:
            self._running = False
            self._cancel_callback = None
            if not self._stopped:
                self._completions.append(
                    DesktopRequestCompletion(cancelled=True)
                    if self._cancel_requested
                    else completion
                )

    def drain(self) -> tuple[DesktopRequestCompletion[object], ...]:
        """Remove current completions for main-thread presentation."""
        with self._lock:
            completions = tuple(self._completions)
            self._completions.clear()
            self._cancel_requested = False
            return completions

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def request_cancel(
        self,
    ) -> Literal["requested", "already_requested", "idle", "stopped"]:
        """Discard the result after the active bounded operation returns."""
        cancel_callback: Callable[[], None] | None = None
        with self._lock:
            if self._stopped:
                return "stopped"
            if not self._running:
                if self._completions:
                    if self._cancel_requested:
                        return "already_requested"
                    self._cancel_requested = True
                    self._completions.clear()
                    self._completions.append(DesktopRequestCompletion(cancelled=True))
                    return "requested"
                return "idle"
            if self._cancel_requested:
                return "already_requested"
            self._cancel_requested = True
            cancel_callback = self._cancel_callback
        if cancel_callback is not None:
            self._invoke_cancel_callback(cancel_callback)
        return "requested"

    def is_cancellation_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def stop(self) -> None:
        """Reject new requests and discard any late presentation result."""
        cancel_callback: Callable[[], None] | None = None
        with self._lock:
            self._stopped = True
            self._cancel_requested = True
            cancel_callback = self._cancel_callback
            self._completions.clear()
        if cancel_callback is not None:
            self._invoke_cancel_callback(cancel_callback)

    @staticmethod
    def _invoke_cancel_callback(cancel_callback: Callable[[], None]) -> None:
        """Keep presentation cancellation valid if a cooperative hook fails."""
        try:
            cancel_callback()
        except Exception:
            pass
