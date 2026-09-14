"""Persistence boundaries for deferred execution grants."""

from typing import Protocol

from research.DeferredExecutionGrant import DeferredExecutionGrant


class DeferredExecutionGrantStore(Protocol):
    def load(self) -> list[DeferredExecutionGrant]: ...

    def save(self, grants: list[DeferredExecutionGrant]) -> None: ...


class ReadsDeferredExecutionGrants(Protocol):
    def active_for_task(self, task_id: str) -> DeferredExecutionGrant | None: ...

    def for_grant_id(self, grant_id: str) -> DeferredExecutionGrant | None: ...


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

    def for_grant_id(self, grant_id: str) -> DeferredExecutionGrant | None:
        """Return the one grant with this exact ID, or nothing.

        Not filtered by active. A schedule names one grant, and if that grant
        was revoked after the schedule was armed then the revoked record is
        still the honest answer to "what was this armed under". Substituting
        whichever grant is currently active would describe a different
        authority than the one the schedule actually references.
        """
        matches = [grant for grant in self._store.load() if grant.grant_id == grant_id]
        return matches[0] if len(matches) == 1 else None
