"""Thread-safe cooperative cancellation signal for bounded runtime stages."""

from __future__ import annotations

from threading import Event
from typing import Protocol


class CancellationToken(Protocol):
    """Read-only cancellation state consumed at explicitly safe checkpoints."""

    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested."""


class CancellationSignal:
    """One-way signal shared between a request owner and runtime stages."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        """Request cooperative cancellation without terminating a thread."""
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()
