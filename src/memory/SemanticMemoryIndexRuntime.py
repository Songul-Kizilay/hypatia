"""Thread-safe owner that swaps semantic indexes only after a full rebuild."""

from __future__ import annotations

from threading import RLock

from eventbus.Event import Event
from eventbus.EventBus import EventBus
from memory.InMemorySemanticMemoryIndex import InMemorySemanticMemoryIndex
from memory.MemoryManager import MemoryManager
from memory.SemanticMemoryIndexBuilder import SemanticMemoryIndexBuilder
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class SemanticMemoryIndexRuntime:
    """Keep the last successfully built semantic-memory index available."""

    def __init__(self, builder: SemanticMemoryIndexBuilder) -> None:
        self._builder = builder
        self._index: InMemorySemanticMemoryIndex | None = None
        self._last_update_error: str | None = None
        self._lock = RLock()

    def current(self) -> InMemorySemanticMemoryIndex | None:
        """Return the last complete index, or None before the first refresh."""
        with self._lock:
            return self._index

    def refresh(self, memory_manager: MemoryManager) -> InMemorySemanticMemoryIndex:
        """Build and atomically publish a replacement index on success only."""
        with self._lock:
            replacement = self._builder.build(memory_manager)
            self._index = replacement
            self._last_update_error = None
            return replacement

    def last_update_error(self) -> str | None:
        """Return a safe diagnostic when the latest incremental update failed."""
        with self._lock:
            return self._last_update_error

    def attach(self, event_bus: EventBus) -> None:
        """Keep the derived index current without making memory writes fail."""
        for event_name in (
            "memory.record.added",
            "memory.record.updated",
            "memory.record.deleted",
            "memory.record.expired",
        ):
            event_bus.subscribe(event_name, self._handle_memory_event)

    def search(
        self,
        source_text: str,
        *,
        limit: int | None = None,
    ) -> tuple[SemanticMemoryMatch, ...]:
        """Search the last complete index without rebuilding or changing it."""
        with self._lock:
            if self._index is None:
                return ()
            query_embedding = self._builder.embed(source_text)
            return self._index.search(query_embedding, limit=limit)

    def _handle_memory_event(self, event: Event) -> None:
        """Apply a best-effort incremental update after a successful memory write."""
        memory_id = event.payload.get("memory_id")
        if not isinstance(memory_id, str):
            return

        try:
            with self._lock:
                index = self._index
                if index is None:
                    return
                if event.name in {"memory.record.deleted", "memory.record.expired"}:
                    index.remove(memory_id)
                    self._builder.remove_memory_record(memory_id)
                    self._last_update_error = None
                    return

                content = event.payload.get("content")
                if not isinstance(content, str):
                    return
                self._builder.upsert_memory_record(
                    index,
                    memory_id,
                    content,
                )
                self._last_update_error = None
        except Exception:
            # Semantic retrieval is optional. A provider failure must not roll
            # back or surface from an already successful memory operation.
            with self._lock:
                self._last_update_error = "Semantic index update failed."
            return
