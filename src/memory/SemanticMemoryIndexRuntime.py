"""Thread-safe owner for single-flight background semantic-index rebuilding."""

from __future__ import annotations

from threading import Event as ThreadEvent
from threading import RLock, Thread
from typing import Literal

from core.Exceptions import MemoryError
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
        self._last_rebuild_error: str | None = None
        self._last_update_error: str | None = None
        self._lock = RLock()
        self._cancel_rebuild = ThreadEvent()
        self._rebuilding = False
        self._memory_changed_during_rebuild = False
        self._stopped = False
        self._worker: Thread | None = None

    def current(self) -> InMemorySemanticMemoryIndex | None:
        """Return the last complete index, or None before the first refresh."""
        with self._lock:
            return self._index

    def refresh(self, memory_manager: MemoryManager) -> InMemorySemanticMemoryIndex:
        """Build and atomically publish a replacement index on success only."""
        with self._lock:
            if self._stopped:
                raise MemoryError("Semantic index runtime is stopped.")
            if self._rebuilding:
                raise MemoryError("Semantic index rebuild is already in progress.")
            self._rebuilding = True
            self._memory_changed_during_rebuild = False
            self._cancel_rebuild.clear()
        try:
            replacement = self._builder.build(
                memory_manager,
                cancelled=self._cancel_rebuild.is_set,
            )
        except Exception:
            with self._lock:
                if not self._stopped:
                    self._last_rebuild_error = "Semantic index rebuild failed."
                self._rebuilding = False
            raise
        with self._lock:
            if self._stopped:
                self._rebuilding = False
                raise MemoryError("Semantic index runtime is stopped.")
            if self._memory_changed_during_rebuild:
                self._last_rebuild_error = "Semantic index rebuild failed."
                self._rebuilding = False
                raise MemoryError("Memory changed during semantic index rebuild.")
            self._index = replacement
            self._last_rebuild_error = None
            self._last_update_error = None
            self._rebuilding = False
            return replacement

    def start_refresh(
        self,
        memory_manager: MemoryManager,
    ) -> Literal["started", "already_running", "stopped", "failed"]:
        """Start one daemon rebuild without blocking the caller."""
        with self._lock:
            if self._stopped:
                return "stopped"
            if self._rebuilding:
                return "already_running"
            self._rebuilding = True
            self._memory_changed_during_rebuild = False
            self._cancel_rebuild.clear()
            worker = Thread(
                target=self._run_background_refresh,
                args=(memory_manager,),
                name="hypatia-semantic-rebuild",
                daemon=True,
            )
            self._worker = worker
        try:
            worker.start()
        except Exception:
            with self._lock:
                self._worker = None
                self._rebuilding = False
                if not self._stopped:
                    self._last_rebuild_error = "Semantic index rebuild failed."
            return "failed"
        return "started"

    def _run_background_refresh(self, memory_manager: MemoryManager) -> None:
        """Publish only a complete quiet snapshot, with one dirty retry."""
        for attempt in range(2):
            with self._lock:
                if self._stopped:
                    self._finish_background_refresh_locked()
                    return
                self._memory_changed_during_rebuild = False
            try:
                replacement = self._builder.build(
                    memory_manager,
                    cancelled=self._cancel_rebuild.is_set,
                )
            except Exception:
                with self._lock:
                    if not self._stopped:
                        self._last_rebuild_error = "Semantic index rebuild failed."
                    self._finish_background_refresh_locked()
                return
            with self._lock:
                if self._stopped:
                    self._finish_background_refresh_locked()
                    return
                if self._memory_changed_during_rebuild:
                    if attempt == 0:
                        continue
                    self._last_rebuild_error = "Semantic index rebuild failed."
                    self._finish_background_refresh_locked()
                    return
                self._index = replacement
                self._last_rebuild_error = None
                self._last_update_error = None
                self._finish_background_refresh_locked()
                return

    def _finish_background_refresh_locked(self) -> None:
        self._rebuilding = False
        self._worker = None

    def wait_for_idle(self, timeout_seconds: float | None = None) -> bool:
        """Wait for the current worker in tests or controlled host shutdowns."""
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout_seconds)
        with self._lock:
            return not self._rebuilding

    def shutdown(self) -> None:
        """Prevent new rebuilds and suppress publication by in-flight work."""
        with self._lock:
            self._stopped = True
            self._cancel_rebuild.set()

    def is_rebuilding(self) -> bool:
        with self._lock:
            return self._rebuilding

    def is_stopped(self) -> bool:
        with self._lock:
            return self._stopped

    def last_rebuild_error(self) -> str | None:
        """Return a safe diagnostic when the latest full rebuild failed."""
        with self._lock:
            return self._last_rebuild_error

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
            if self._index is None or self._rebuilding or self._stopped:
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
                if self._stopped:
                    return
                if self._rebuilding:
                    self._memory_changed_during_rebuild = True
                    return
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
