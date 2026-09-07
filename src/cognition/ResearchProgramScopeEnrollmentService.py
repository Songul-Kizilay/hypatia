"""Explicit, durable enrollment of human-confirmed program target scopes.

This boundary only previews, records, lists, and revokes scope revisions.  It
does not authorize a research plan, start or advance execution, resolve a
hostname, open a connection, run a process, or call a model.

Previews are process-local and bounded.  Confirmation names the exact revision
identity and digest shown by a preview; caller-provided revision objects are
never accepted.  Persistence happens before the new history is published in
memory, so a failed write cannot create authority visible only to this process.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchProgramScopeEnrollmentPreview import (
    PROGRAM_SCOPE_CREATE_ACTION,
    PROGRAM_SCOPE_REVOKE_ACTION,
    ResearchProgramScopeEnrollmentPreview,
)
from research.ResearchProgramScopeExecutionPolicy import (
    DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY,
    ResearchProgramScopeExecutionPolicy,
)
from research.ResearchProgramScopeRevision import (
    MAX_PROGRAM_SCOPE_REVISION_VALIDITY_SECONDS,
    ResearchProgramScopeRevision,
)
from research.ResearchProgramScopeRevisionCodec import (
    MAX_PROGRAM_SCOPE_REVISIONS,
    encode_program_scope_revisions,
)
from research.ResearchProgramScopeRevisionStore import (
    ResearchProgramScopeRevisionStore,
)
from research.ResearchTargetScope import ResearchTargetScope

MAX_PENDING_PROGRAM_SCOPE_PREVIEWS = 20


@dataclass(frozen=True, slots=True)
class _PendingEnrollment:
    preview: ResearchProgramScopeEnrollmentPreview
    predecessor_digest: str | None = None


class ResearchProgramScopeEnrollmentService:
    """Maintain one bounded, monotonic scope-revision history."""

    def __init__(
        self,
        store: ResearchProgramScopeRevisionStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._pending: dict[str, _PendingEnrollment] = {}
        self._revisions = self._restore()

    def revisions(self) -> tuple[ResearchProgramScopeRevision, ...]:
        """Return the bounded durable history in its canonical order."""
        return tuple(self._revisions)

    def preview_create(
        self,
        program_id: str,
        scope: ResearchTargetScope,
        *,
        expires_at: datetime | None = None,
        execution_policy: ResearchProgramScopeExecutionPolicy | None = None,
    ) -> ResearchProgramScopeEnrollmentPreview:
        """Build the exact new revision a later confirmation could append."""
        self._require_pending_capacity()
        if self._active_for_program(program_id) is not None:
            raise ResearchError(
                "This program already has an active scope revision; revoke it first."
            )
        if any(
            pending.preview.action == PROGRAM_SCOPE_CREATE_ACTION
            and pending.preview.revision.program_id == program_id.strip()
            for pending in self._pending.values()
        ):
            raise ResearchError(
                "This program already has a scope creation awaiting confirmation."
            )
        confirmed_at = self._now()
        revision = ResearchProgramScopeRevision(
            revision_id=self._new_revision_id(),
            program_id=program_id,
            scope=scope,
            confirmed_at=confirmed_at,
            expires_at=expires_at
            or confirmed_at
            + timedelta(seconds=MAX_PROGRAM_SCOPE_REVISION_VALIDITY_SECONDS),
            execution_policy=execution_policy or DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY,
        )
        if (
            any(value.revision_id == revision.revision_id for value in self._revisions)
            or revision.revision_id in self._pending
        ):
            raise ResearchError("Program scope revision identity already exists.")
        preview = ResearchProgramScopeEnrollmentPreview.create(revision)
        self._pending[revision.revision_id] = _PendingEnrollment(preview)
        return preview

    def confirm_create(
        self, revision_id: str, revision_digest: str
    ) -> ResearchProgramScopeRevision:
        """Persist the exact pending creation, without rebuilding it."""
        pending = self._exact_pending(
            revision_id, revision_digest, PROGRAM_SCOPE_CREATE_ACTION
        )
        revision = pending.preview.revision
        if not revision.valid_at(self._now()):
            self._pending.pop(revision.revision_id, None)
            raise ResearchError("Program scope creation preview is stale.")
        if self._active_for_program(revision.program_id) is not None:
            self._pending.pop(revision.revision_id, None)
            raise ResearchError("Program scope creation preview is stale.")
        if any(value.revision_id == revision.revision_id for value in self._revisions):
            self._pending.pop(revision.revision_id, None)
            raise ResearchError("Program scope creation preview is stale.")
        proposed = [*self._revisions, revision]
        self._save_then_publish(proposed)
        self._pending.pop(revision.revision_id, None)
        return revision

    def preview_revoke(
        self, revision_id: str, revision_digest: str
    ) -> ResearchProgramScopeEnrollmentPreview:
        """Preview a one-way human revocation of one exact active revision."""
        self._require_pending_capacity()
        active = self._exact_active(revision_id, revision_digest)
        if active.revision_id in self._pending:
            raise ResearchError(
                "This program scope revision already has a pending decision."
            )
        revoked = active.revoked(self._now())
        preview = ResearchProgramScopeEnrollmentPreview.revoke(revoked)
        self._pending[active.revision_id] = _PendingEnrollment(
            preview,
            predecessor_digest=active.revision_digest,
        )
        return preview

    def confirm_revoke(
        self, revision_id: str, revision_digest: str
    ) -> ResearchProgramScopeRevision:
        """Persist exactly the pending revocation, never a caller-built value."""
        pending = self._exact_pending(
            revision_id, revision_digest, PROGRAM_SCOPE_REVOKE_ACTION
        )
        revoked = pending.preview.revision
        try:
            current = next(
                value
                for value in self._revisions
                if value.revision_id == revoked.revision_id
            )
        except StopIteration:
            self._pending.pop(revoked.revision_id, None)
            raise ResearchError("Program scope revocation preview is stale.") from None
        if (
            not current.active
            or current.revision_digest != pending.predecessor_digest
            or current.program_id != revoked.program_id
        ):
            self._pending.pop(revoked.revision_id, None)
            raise ResearchError("Program scope revocation preview is stale.")
        proposed = [
            revoked if value.revision_id == revoked.revision_id else value
            for value in self._revisions
        ]
        self._save_then_publish(proposed)
        self._pending.pop(revoked.revision_id, None)
        return revoked

    def _restore(self) -> list[ResearchProgramScopeRevision]:
        try:
            loaded = self._store.load()
            if not isinstance(loaded, list):
                raise ResearchError("Program scope revision history is invalid.")
            if len(loaded) > MAX_PROGRAM_SCOPE_REVISIONS:
                raise ResearchError("Program scope revision history is too large.")
            # The protocol can be supplied by more than the JSON store.  Run the
            # same strict bounded validation at the application boundary too.
            encode_program_scope_revisions(loaded)
            return list(loaded)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore program scope revisions.") from error

    def _save_then_publish(self, proposed: list[ResearchProgramScopeRevision]) -> None:
        try:
            self._store.save(proposed)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to persist program scope revisions.") from error
        self._revisions = proposed

    def _exact_pending(
        self, revision_id: str, revision_digest: str, action: str
    ) -> _PendingEnrollment:
        normalized_id = self._required_text(revision_id, "revision ID")
        normalized_digest = self._required_text(revision_digest, "revision digest")
        pending = self._pending.get(normalized_id)
        if (
            pending is None
            or pending.preview.action != action
            or pending.preview.revision.revision_digest != normalized_digest
        ):
            raise ResearchError(
                "No exact program scope preview with that identity and digest "
                "awaits this confirmation."
            )
        return pending

    def _exact_active(
        self, revision_id: str, revision_digest: str
    ) -> ResearchProgramScopeRevision:
        normalized_id = self._required_text(revision_id, "revision ID")
        normalized_digest = self._required_text(revision_digest, "revision digest")
        matches = [
            value
            for value in self._revisions
            if value.revision_id == normalized_id
            and value.revision_digest == normalized_digest
            and value.active
        ]
        if len(matches) != 1:
            raise ResearchError(
                "No exact active program scope revision has that identity and digest."
            )
        return matches[0]

    def _active_for_program(
        self, program_id: str
    ) -> ResearchProgramScopeRevision | None:
        normalized = self._required_text(program_id, "program ID")
        matches = [
            value
            for value in self._revisions
            if value.program_id == normalized and value.active
        ]
        if len(matches) > 1:
            raise ResearchError("Program scope revision history is contradictory.")
        return matches[0] if matches else None

    def _require_pending_capacity(self) -> None:
        if len(self._pending) >= MAX_PENDING_PROGRAM_SCOPE_PREVIEWS:
            raise ResearchError(
                "Too many program scope decisions are awaiting confirmation."
            )

    def _new_revision_id(self) -> str:
        value = self._id_factory()
        return self._required_text(value, "revision ID")

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError(
                "Program scope enrollment clock must be timezone-aware."
            )
        return value.astimezone(UTC)

    @staticmethod
    def _required_text(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Program scope enrollment {label} cannot be empty.")
        return value.strip()
