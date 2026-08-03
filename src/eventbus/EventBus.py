"""
Synchronous Event Bus for the Hypatia core runtime.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from threading import RLock

from core.Exceptions import EventBusError
from eventbus.Event import Event

type EventHandler = Callable[[Event], None]


class EventBus:
    """Registers subscribers and publishes immutable events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event name."""
        if not event_name.strip():
            raise EventBusError("Event name cannot be empty.")

        with self._lock:
            if handler not in self._subscribers[event_name]:
                self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> bool:
        """Remove a handler. Returns True when it was registered."""
        with self._lock:
            handlers = self._subscribers.get(event_name)

            if not handlers or handler not in handlers:
                return False

            handlers.remove(handler)

            if not handlers:
                self._subscribers.pop(event_name, None)

            return True

    def publish(self, event: Event) -> int:
        """Publish an event and return the number of invoked handlers."""
        with self._lock:
            handlers = tuple(self._subscribers.get(event.name, ()))
            wildcard_handlers = tuple(self._subscribers.get("*", ()))

        invoked = 0

        for handler in (*handlers, *wildcard_handlers):
            handler(event)
            invoked += 1

        return invoked

    def emit(
        self,
        name: str,
        payload: dict[str, object] | None = None,
        *,
        source: str = "hypatia",
    ) -> Event:
        """Create and immediately publish an event."""
        event = Event(
            name=name,
            payload=dict(payload or {}),
            source=source,
        )
        self.publish(event)
        return event

    def subscriber_count(self, event_name: str | None = None) -> int:
        """Return subscriber count for one event or the whole bus."""
        with self._lock:
            if event_name is not None:
                return len(self._subscribers.get(event_name, ()))

            return sum(len(handlers) for handlers in self._subscribers.values())

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscribers.clear()
