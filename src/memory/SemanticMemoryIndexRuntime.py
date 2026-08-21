"""Thread-safe owner for single-flight background semantic-index rebuilding."""

from __future__ import annotations

from dataclasses import dataclass
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

MAX_PENDING_SEMANTIC_MEMORY_UPDATES = 20_000


@dataclass(frozen=True, slots=True)
class _PendingSemanticMemoryUpdate:
    memory_id: str
    operation: Literal["upsert", "remove"]
    content: str | None
    generation: int


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
        self._rebuild_manager: MemoryManager | None = None
        self._updating = False
        self._pending_updates: dict[str, _PendingSemanticMemoryUpdate] = {}
        self._update_generations: dict[str, int] = {}
        self._failed_update_ids: set[str] = set()

    def current(self) -> InMemorySemanticMemoryIndex | None:
        """Return the last complete index, or None before the first refresh."""
        with self._lock:
            return self._index

    def refresh(self, memory_manager: MemoryManager) -> InMemorySemanticMemoryIndex:
        """Build and atomically publish a replacement index on success only."""
        with self._lock:
            if self._stopped:
                raise MemoryError("Semantic index runtime is stopped.")
            if self._rebuilding or self._worker is not None:
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
            self._failed_update_ids.clear()
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
            self._rebuild_manager = memory_manager
            self._memory_changed_during_rebuild = False
            self._cancel_rebuild.clear()
            worker = self._create_worker_locked()
        if worker is None:
            return "started"
        try:
            worker.start()
        except Exception:
            with self._lock:
                self._worker = None
                self._rebuilding = False
                self._rebuild_manager = None
                if not self._stopped:
                    self._last_rebuild_error = "Semantic index rebuild failed."
            return "failed"
        return "started"

    def _create_worker_locked(self) -> Thread | None:
        if self._worker is not None:
            return None
        worker = Thread(
            target=self._run_worker,
            name="hypatia-semantic-worker",
            daemon=True,
        )
        self._worker = worker
        return worker

    def _run_worker(self) -> None:
        """Run full rebuilds and coalesced incremental work on one worker."""
        while True:
            with self._lock:
                if self._stopped:
                    self._finish_worker_locked()
                    return
                memory_manager = self._rebuild_manager if self._rebuilding else None
                if memory_manager is not None:
                    self._pending_updates.clear()
                    self._update_generations.clear()
                    self._updating = False
                    update = None
                elif self._pending_updates:
                    memory_id = next(iter(self._pending_updates))
                    update = self._pending_updates.pop(memory_id)
                    self._updating = True
                else:
                    self._finish_worker_locked()
                    return
            if memory_manager is not None:
                self._run_background_refresh(memory_manager)
            elif update is not None:
                self._run_incremental_update(update)

    def _run_background_refresh(self, memory_manager: MemoryManager) -> None:
        """Publish only a complete quiet snapshot, with one dirty retry."""
        for attempt in range(2):
            with self._lock:
                if self._stopped:
                    self._finish_rebuild_locked()
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
                    self._finish_rebuild_locked()
                return
            with self._lock:
                if self._stopped:
                    self._finish_rebuild_locked()
                    return
                if self._memory_changed_during_rebuild:
                    if attempt == 0:
                        continue
                    self._last_rebuild_error = "Semantic index rebuild failed."
                    self._finish_rebuild_locked()
                    return
                self._index = replacement
                self._last_rebuild_error = None
                self._last_update_error = None
                self._failed_update_ids.clear()
                self._finish_rebuild_locked()
                return

    def _finish_rebuild_locked(self) -> None:
        self._rebuilding = False
        self._rebuild_manager = None

    def _finish_worker_locked(self) -> None:
        self._updating = False
        self._worker = None

    def _run_incremental_update(
        self,
        update: _PendingSemanticMemoryUpdate,
    ) -> None:
        if update.operation == "remove":
            self._publish_incremental_removal(update)
            return
        assert update.content is not None
        try:
            embedding = self._builder.embed(update.content)
        except Exception:
            with self._lock:
                if self._is_current_update_locked(update):
                    self._mark_update_failed_locked(update.memory_id)
                    self._complete_update_locked(update)
            return
        with self._lock:
            if not self._is_current_update_locked(update):
                return
            index = self._index
            if index is None:
                self._complete_update_locked(update)
                return
            try:
                self._builder.upsert_memory_embedding(
                    index,
                    update.memory_id,
                    embedding,
                )
            except Exception:
                self._mark_update_failed_locked(update.memory_id)
                self._complete_update_locked(update)
                return
            self._mark_update_succeeded_locked(update.memory_id)
            self._complete_update_locked(update)
        self._builder.retain_memory_record_embedding(
            update.memory_id,
            update.content,
            embedding,
        )

    def _publish_incremental_removal(
        self,
        update: _PendingSemanticMemoryUpdate,
    ) -> None:
        with self._lock:
            if not self._is_current_update_locked(update):
                return
            index = self._index
            if index is None:
                self._complete_update_locked(update)
                return
            try:
                index.remove(update.memory_id)
            except Exception:
                self._mark_update_failed_locked(update.memory_id)
                self._complete_update_locked(update)
                return
            self._mark_update_succeeded_locked(update.memory_id)
            self._complete_update_locked(update)
        self._builder.remove_memory_record(update.memory_id)

    def _is_current_update_locked(
        self,
        update: _PendingSemanticMemoryUpdate,
    ) -> bool:
        return (
            not self._stopped
            and not self._rebuilding
            and self._update_generations.get(update.memory_id) == update.generation
        )

    def _complete_update_locked(
        self,
        update: _PendingSemanticMemoryUpdate,
    ) -> None:
        if (
            self._update_generations.get(update.memory_id) == update.generation
            and update.memory_id not in self._pending_updates
        ):
            self._update_generations.pop(update.memory_id, None)

    def _mark_update_failed_locked(self, memory_id: str) -> None:
        if (
            memory_id in self._failed_update_ids
            or len(self._failed_update_ids) < MAX_PENDING_SEMANTIC_MEMORY_UPDATES
        ):
            self._failed_update_ids.add(memory_id)
        self._last_update_error = "Semantic index update failed."

    def _mark_update_succeeded_locked(self, memory_id: str) -> None:
        self._failed_update_ids.discard(memory_id)
        self._last_update_error = (
            "Semantic index update failed." if self._failed_update_ids else None
        )

    def wait_for_idle(self, timeout_seconds: float | None = None) -> bool:
        """Wait for the current worker in tests or controlled host shutdowns."""
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout_seconds)
        with self._lock:
            return (
                self._worker is None
                and not self._rebuilding
                and not self._pending_updates
            )

    def shutdown(self) -> None:
        """Prevent new rebuilds and suppress publication by in-flight work."""
        with self._lock:
            self._stopped = True
            self._cancel_rebuild.set()
            self._pending_updates.clear()
            self._update_generations.clear()
            self._failed_update_ids.clear()

    def is_rebuilding(self) -> bool:
        with self._lock:
            return self._rebuilding

    def is_stopped(self) -> bool:
        with self._lock:
            return self._stopped

    def is_updating(self) -> bool:
        with self._lock:
            return (
                not self._stopped and not self._rebuilding and self._worker is not None
            )

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
            if self._index is None or self._worker is not None or self._stopped:
                return ()
            query_embedding = self._builder.embed(source_text)
            return self._index.search(query_embedding, limit=limit)

    def _handle_memory_event(self, event: Event) -> None:
        """Apply a best-effort incremental update after a successful memory write."""
        memory_id = event.payload.get("memory_id")
        if not isinstance(memory_id, str):
            return

        operation: Literal["upsert", "remove"]
        content: str | None
        if event.name in {"memory.record.deleted", "memory.record.expired"}:
            operation = "remove"
            content = None
        else:
            operation = "upsert"
            raw_content = event.payload.get("content")
            if not isinstance(raw_content, str):
                return
            content = raw_content

        worker: Thread | None = None
        try:
            with self._lock:
                if self._stopped:
                    return
                if self._rebuilding:
                    self._memory_changed_during_rebuild = True
                    return
                if self._index is None:
                    return
                is_new_pending_id = memory_id not in self._pending_updates
                if (
                    is_new_pending_id
                    and len(self._pending_updates)
                    >= MAX_PENDING_SEMANTIC_MEMORY_UPDATES
                ):
                    self._mark_update_failed_locked(memory_id)
                    return
                generation = self._update_generations.get(memory_id, 0) + 1
                self._update_generations[memory_id] = generation
                self._pending_updates.pop(memory_id, None)
                self._pending_updates[memory_id] = _PendingSemanticMemoryUpdate(
                    memory_id=memory_id,
                    operation=operation,
                    content=content,
                    generation=generation,
                )
                worker = self._create_worker_locked()
            if worker is not None:
                worker.start()
        except Exception:
            with self._lock:
                if self._worker is worker:
                    self._worker = None
                self._updating = False
                if not self._stopped:
                    self._mark_update_failed_locked(memory_id)
                    if self._rebuilding:
                        self._rebuilding = False
                        self._rebuild_manager = None
                        self._last_rebuild_error = "Semantic index rebuild failed."
