"""Which research runs the interface needs to re-read, and nothing more.

This is the trigger half of the refresh, deliberately separated from the answer
half. It listens to ingestion events and remembers which run identifiers have
changed canonically. It never remembers a count, because a count taken from an
event is a count that can disagree with the store — and an interface showing a
number the store does not hold is exactly the failure this whole area keeps
producing.

So the contract is narrow: the event says *that* a run changed, and the
interface then goes and reads *what* it now contains. If the two ever disagree,
the store wins, because it is the thing evidence and claims are built on.

Only canonical acceptance marks a run. A local index changes no run, a refused
attachment changes no run, and a cancellation changes no run, so none of them
produce a refresh — an interface that redrew on those would be redrawing to show
the same numbers, and the one time it appeared to change something would be a
bug.

The signal is thread-safe because events arrive on the worker thread that ran
the request, while the interface drains on its own event-loop thread.
"""

from __future__ import annotations

from threading import Lock

from cognition.SourceIngestionEvents import ATTACH_COMPLETED
from eventbus.Event import Event
from eventbus.EventBus import EventBus


class ResearchStateRefreshSignal:
    """Record which runs changed canonically, so the interface can re-read them."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._lock = Lock()
        self._pending: list[str] = []
        if event_bus is not None:
            event_bus.subscribe(ATTACH_COMPLETED, self.note)

    def note(self, event: Event) -> None:
        """Mark one run as needing a re-read, if this event says it changed.

        The `attached_to_run` flag is checked as well as the event name, so a
        payload that does not claim canonical acceptance cannot trigger a
        refresh even if it arrives under an acceptance name.
        """
        if event.name != ATTACH_COMPLETED:
            return
        if not event.payload.get("attached_to_run"):
            return
        run_id = event.payload.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return
        with self._lock:
            if run_id not in self._pending:
                self._pending.append(run_id)

    def drain(self) -> tuple[str, ...]:
        """Return the runs awaiting a re-read, clearing them.

        Draining is destructive so one canonical change produces one refresh.
        A run that changes twice before anyone drains is still one re-read,
        because re-reading is idempotent and reads the latest state either way.
        """
        with self._lock:
            pending = tuple(self._pending)
            self._pending.clear()
        return pending

    @property
    def pending(self) -> bool:
        """Return whether any run is waiting to be re-read."""
        with self._lock:
            return bool(self._pending)
