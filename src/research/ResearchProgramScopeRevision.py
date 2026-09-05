"""One immutable, human-confirmed bug-bounty program scope revision.

The revision records only policy the current target transport can enforce.  Its
scope and audit facts grant no execution authority; a later plan approval must
bind this exact revision identity and check its validity at dispatch.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import MAX_AUTONOMY_SECONDS
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchTargetScope import ResearchTargetScope
from research.ResearchTargetScopeCodec import (
    canonical_target_scope_bytes,
    target_scope_digest,
)

MAX_PROGRAM_SCOPE_REVISION_ID_CHARACTERS = 200
MAX_PROGRAM_SCOPE_PROGRAM_ID_CHARACTERS = 200
MAX_PROGRAM_SCOPE_REVISION_VALIDITY_SECONDS = MAX_AUTONOMY_SECONDS
PROGRAM_SCOPE_TRANSPORT = "https:443"
PROGRAM_SCOPE_CAPABILITIES = frozenset(
    {
        ResearchPlanStepCapability.SOURCE_FETCH,
        ResearchPlanStepCapability.SOURCE_ACCEPT,
    }
)
_REVISION_DIGEST_SCHEMA = "hypatia:research-program-scope-revision:v1"


@dataclass(frozen=True, slots=True)
class ResearchProgramScopeRevision:
    """Preserve exact confirmed scope policy and an immutable revocation."""

    revision_id: str
    program_id: str
    scope: ResearchTargetScope
    confirmed_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    revoked_by: ResearchAuthorizer | None = None
    scope_digest: str = field(init=False)
    revision_digest: str = field(init=False)
    capabilities: frozenset[ResearchPlanStepCapability] = field(
        init=False, default=PROGRAM_SCOPE_CAPABILITIES
    )
    transport: str = field(init=False, default=PROGRAM_SCOPE_TRANSPORT)
    confirmed_by: ResearchAuthorizer = field(
        init=False, default=ResearchAuthorizer.HUMAN
    )

    def __post_init__(self) -> None:
        revision_id = self._bounded_id(
            self.revision_id,
            "Program scope revision ID",
            MAX_PROGRAM_SCOPE_REVISION_ID_CHARACTERS,
        )
        program_id = self._bounded_id(
            self.program_id,
            "Program scope program ID",
            MAX_PROGRAM_SCOPE_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.scope, ResearchTargetScope):
            raise ResearchError("Program scope revision requires a validated scope.")
        self._aware(self.confirmed_at, "confirmation time")
        self._aware(self.expires_at, "expiry time")
        confirmed_instant = self.confirmed_at.astimezone(UTC)
        expires_instant = self.expires_at.astimezone(UTC)
        if expires_instant <= confirmed_instant:
            raise ResearchError(
                "Program scope revision must expire after confirmation."
            )
        if (
            expires_instant - confirmed_instant
        ).total_seconds() > MAX_PROGRAM_SCOPE_REVISION_VALIDITY_SECONDS:
            raise ResearchError(
                "Program scope revision validity exceeds its hard ceiling."
            )
        if (self.revoked_at is None) != (self.revoked_by is None):
            raise ResearchError("Program scope revision revocation is incomplete.")
        if self.revoked_at is not None:
            self._aware(self.revoked_at, "revocation time")
            if self.revoked_at.astimezone(UTC) < confirmed_instant:
                raise ResearchError(
                    "Program scope revision revocation predates confirmation."
                )
            if self.revoked_by is not ResearchAuthorizer.HUMAN:
                raise ResearchError(
                    "Program scope revision revocation requires human provenance."
                )
        object.__setattr__(self, "revision_id", revision_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "scope_digest", target_scope_digest(self.scope))
        object.__setattr__(self, "revision_digest", _revision_digest(self))

    @property
    def active(self) -> bool:
        """Return whether no immutable revocation has been recorded."""
        return self.revoked_at is None

    @property
    def state(self) -> str:
        """Render the bounded persisted lifecycle fact."""
        return "active" if self.active else "revoked"

    def valid_at(self, moment: datetime) -> bool:
        """Require confirmation, non-expiry and no revocation at this moment."""
        self._aware(moment, "validity-check time")
        instant = moment.astimezone(UTC)
        return self.active and self.confirmed_at.astimezone(
            UTC
        ) <= instant < self.expires_at.astimezone(UTC)

    def revoked(
        self,
        at: datetime,
        by: ResearchAuthorizer = ResearchAuthorizer.HUMAN,
    ) -> ResearchProgramScopeRevision:
        """Return a revoked successor while retaining every confirmed fact."""
        if not self.active:
            raise ResearchError("Program scope revision is already revoked.")
        if by is not ResearchAuthorizer.HUMAN:
            raise ResearchError(
                "Program scope revision revocation requires human provenance."
            )
        return replace(self, revoked_at=at, revoked_by=by)

    @staticmethod
    def _bounded_id(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized

    @staticmethod
    def _aware(value: datetime, label: str) -> None:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError(
                f"Program scope revision {label} must be timezone-aware."
            )


def canonical_program_scope_revision_bytes(
    revision: ResearchProgramScopeRevision,
) -> bytes:
    """Encode every authority-relevant fact except the resulting digest."""
    if not isinstance(revision, ResearchProgramScopeRevision):
        raise ResearchError("Program scope revision digest requires a revision.")
    scope_document = json.loads(canonical_target_scope_bytes(revision.scope))
    document = {
        "schema": _REVISION_DIGEST_SCHEMA,
        "revision_id": revision.revision_id,
        "program_id": revision.program_id,
        "scope": scope_document,
        "scope_digest": revision.scope_digest,
        "capabilities": sorted(value.value for value in revision.capabilities),
        "transport": revision.transport,
        "confirmed_at": revision.confirmed_at.isoformat(),
        "confirmed_by": revision.confirmed_by.value,
        "expires_at": revision.expires_at.isoformat(),
        "state": revision.state,
        "revoked_at": (
            revision.revoked_at.isoformat() if revision.revoked_at is not None else None
        ),
        "revoked_by": (
            revision.revoked_by.value if revision.revoked_by is not None else None
        ),
    }
    return json.dumps(
        document,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def program_scope_revision_digest(revision: ResearchProgramScopeRevision) -> str:
    """Identify the full revision, including expiry and revocation."""
    return hashlib.sha256(canonical_program_scope_revision_bytes(revision)).hexdigest()


def _revision_digest(revision: ResearchProgramScopeRevision) -> str:
    return program_scope_revision_digest(revision)
