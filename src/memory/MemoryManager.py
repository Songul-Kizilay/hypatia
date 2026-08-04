"""Thread-safe in-memory memory manager for the Hypatia runtime."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from core.Exceptions import MemoryError
from eventbus.EventBus import EventBus
from memory.MemoryRecord import MemoryRecord
from memory.MemoryStore import MemoryStore


class _Unset:
    """Marks a field that must retain its current stored value."""


_UNSET = _Unset()


class MemoryManager:
    """Stores immutable memory records and publishes lifecycle events."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        store: MemoryStore | None = None,
    ) -> None:
        self._records: dict[str, MemoryRecord] = {}
        self._event_bus = event_bus
        self._store = store
        self._lock = RLock()

    def load(self) -> None:
        """Replace memory with the active records from the persistent snapshot."""
        if self._store is None:
            return

        records = self._store.load()
        now = self._now()
        active_records = {
            record.memory_id: record
            for record in records
            if record.expires_at is None or record.expires_at > now
        }

        with self._lock:
            self._records = active_records

    def add(
        self,
        content: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryRecord:
        """Create and store a memory record."""
        content = self._validate_content(content)
        expires_at = self._validate_expiration(expires_at)
        now = self._now()
        record = MemoryRecord(
            memory_id=str(uuid4()),
            content=content,
            metadata=self._freeze_metadata(metadata),
            tags=self._freeze_tags(tags),
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

        with self._lock:
            candidate_records = dict(self._records)
            candidate_records[record.memory_id] = record
            self._persist(candidate_records)
            self._records = candidate_records

        self._emit("memory.record.added", record)
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        """Return a record by ID, or None when absent or expired."""
        expired = self._purge_expired()
        self._emit_expired(expired)
        with self._lock:
            return self._records.get(memory_id)

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        expires_at: datetime | None | _Unset = _UNSET,
    ) -> MemoryRecord | None:
        """Replace selected fields of a stored record."""
        expired = self._purge_expired()
        self._emit_expired(expired)

        if content is not None:
            content = self._validate_content(content)
        if not isinstance(expires_at, _Unset):
            expires_at = self._validate_expiration(expires_at)

        with self._lock:
            current = self._records.get(memory_id)
            if current is None:
                return None

            record = MemoryRecord(
                memory_id=current.memory_id,
                content=current.content if content is None else content,
                metadata=(
                    current.metadata
                    if metadata is None
                    else self._freeze_metadata(metadata)
                ),
                tags=current.tags if tags is None else self._freeze_tags(tags),
                created_at=current.created_at,
                updated_at=self._now(),
                expires_at=(
                    current.expires_at if isinstance(expires_at, _Unset) else expires_at
                ),
            )
            candidate_records = dict(self._records)
            candidate_records[memory_id] = record
            self._persist(candidate_records)
            self._records = candidate_records

        self._emit("memory.record.updated", record)
        return record

    def delete(self, memory_id: str) -> bool:
        """Delete one record and return whether it existed."""
        with self._lock:
            record = self._records.get(memory_id)
            if record is None:
                return False

            candidate_records = dict(self._records)
            candidate_records.pop(memory_id)
            self._persist(candidate_records)
            self._records = candidate_records

        self._emit("memory.record.deleted", record)
        return True

    def search(
        self,
        query: str,
        *,
        tags: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]:
        """Find non-expired records by case-insensitive content and tags."""
        if limit is not None and limit < 1:
            raise MemoryError("Search limit must be at least 1.")

        expired = self._purge_expired()
        self._emit_expired(expired)
        normalized_query = query.casefold().strip()
        required_tags = self._freeze_tags(tags)

        with self._lock:
            matches = [
                record
                for record in self._records.values()
                if normalized_query in record.content.casefold()
                and required_tags.issubset(record.tags)
            ]

        return matches if limit is None else matches[:limit]

    def all(self) -> list[MemoryRecord]:
        """Return every non-expired record in creation order."""
        expired = self._purge_expired()
        self._emit_expired(expired)
        with self._lock:
            return list(self._records.values())

    def count(self) -> int:
        """Return the number of non-expired records."""
        return len(self.all())

    def clear(self) -> int:
        """Remove all records and return the number removed."""
        with self._lock:
            removed = tuple(self._records.values())
            self._persist({})
            self._records.clear()

        for record in removed:
            self._emit("memory.record.deleted", record)
        self._emit("memory.store.cleared", {"count": len(removed)})
        return len(removed)

    def _purge_expired(self) -> tuple[MemoryRecord, ...]:
        now = self._now()
        with self._lock:
            expired_ids = [
                memory_id
                for memory_id, record in self._records.items()
                if record.expires_at is not None and record.expires_at <= now
            ]
            return tuple(self._records.pop(memory_id) for memory_id in expired_ids)

    def _emit_expired(self, records: Iterable[MemoryRecord]) -> None:
        for record in records:
            self._emit("memory.record.expired", record)

    def _persist(self, records: dict[str, MemoryRecord]) -> None:
        if self._store is None:
            return

        self._store.save(list(records.values()))

    def _emit(self, name: str, record: MemoryRecord | dict[str, object]) -> None:
        if self._event_bus is None:
            return
        if isinstance(record, MemoryRecord):
            payload: dict[str, object] = {
                "memory_id": record.memory_id,
                "content": record.content,
                "tags": sorted(record.tags),
            }
        else:
            payload = record
        self._event_bus.emit(name, payload, source="memory_manager")

    @staticmethod
    def _freeze_metadata(metadata: Mapping[str, Any] | None) -> Mapping[str, Any]:
        return MappingProxyType(dict(metadata or {}))

    @staticmethod
    def _freeze_tags(tags: Iterable[str] | None) -> frozenset[str]:
        return frozenset(tag.strip() for tag in (tags or ()) if tag.strip())

    @staticmethod
    def _validate_content(content: str) -> str:
        if not isinstance(content, str) or not content.strip():
            raise MemoryError("Memory content cannot be empty.")
        return content.strip()

    @staticmethod
    def _validate_expiration(expires_at: datetime | None) -> datetime | None:
        if expires_at is None:
            return None
        if not isinstance(expires_at, datetime):
            raise MemoryError("expires_at must be a datetime or None.")
        if expires_at.tzinfo is None:
            raise MemoryError("expires_at must include timezone information.")
        return expires_at.astimezone(UTC)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
