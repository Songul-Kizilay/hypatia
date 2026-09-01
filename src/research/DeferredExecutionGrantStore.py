"""Persistence boundaries for deferred execution grants."""

from typing import Protocol

from research.DeferredExecutionGrant import DeferredExecutionGrant


class DeferredExecutionGrantStore(Protocol):
    def load(self) -> list[DeferredExecutionGrant]: ...

    def save(self, grants: list[DeferredExecutionGrant]) -> None: ...


class ReadsDeferredExecutionGrants(Protocol):
    def active_for_task(self, task_id: str) -> DeferredExecutionGrant | None: ...


class DeferredExecutionGrantReader:
    """Expose only reads to scheduler selection code."""

    def __init__(self, store: DeferredExecutionGrantStore) -> None:
        self._store = store

    def active_for_task(self, task_id: str) -> DeferredExecutionGrant | None:
        matches = [
            grant
            for grant in self._store.load()
            if grant.task_id == task_id and grant.active
        ]
        return matches[0] if len(matches) == 1 else None
