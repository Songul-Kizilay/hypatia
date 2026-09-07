"""Human approval for one exact Kali operation preview.

This is not execution authority for a shell, terminal or process runner. It
only records that a person approved the exact inert operation digest that was
shown to them. A later runner must still prove that it consumes this exact
record before any child process exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationPreview,
    is_kali_operation_digest,
)

MAX_KALI_OPERATION_AUTHORIZATION_ID_CHARACTERS = 200
MAX_KALI_OPERATION_AUTHORIZATION_VALIDITY_SECONDS = 300


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationAuthorization:
    """Bind one human approval to one exact inert Kali operation preview."""

    authorization_id: str
    operation_digest: str
    program_id: str
    scope_revision_id: str
    scope_revision_digest: str
    execution_policy_digest: str
    authorized_at: datetime
    expires_at: datetime
    authorized_by: ResearchAuthorizer = ResearchAuthorizer.HUMAN

    def __post_init__(self) -> None:
        authorization_id = self._bounded_text(
            self.authorization_id,
            "Kali operation authorization ID",
            MAX_KALI_OPERATION_AUTHORIZATION_ID_CHARACTERS,
        )
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("Kali operation authorization digest is invalid.")
        for value, label in (
            (self.program_id, "program ID"),
            (self.scope_revision_id, "scope revision ID"),
            (self.scope_revision_digest, "scope revision digest"),
            (self.execution_policy_digest, "execution policy digest"),
        ):
            self._bounded_text(value, f"Kali operation authorization {label}", 500)
        if not isinstance(self.authorized_by, ResearchAuthorizer):
            raise ResearchError("Kali operation authorization authority is invalid.")
        self._validate_window()
        object.__setattr__(self, "authorization_id", authorization_id)

    @classmethod
    def for_preview(
        cls,
        *,
        authorization_id: str,
        preview: ResearchKaliOperationPreview,
        authorized_at: datetime,
    ) -> ResearchKaliOperationAuthorization:
        """Approve exactly the displayed preview, deriving every binding fact."""
        if not isinstance(preview, ResearchKaliOperationPreview):
            raise ResearchError(
                "Kali operation authorization requires a validated preview."
            )
        return cls(
            authorization_id=authorization_id,
            operation_digest=preview.operation_digest,
            program_id=preview.program_id,
            scope_revision_id=preview.scope_revision_id,
            scope_revision_digest=preview.scope_revision_digest,
            execution_policy_digest=preview.execution_policy_digest,
            authorized_at=authorized_at,
            expires_at=authorized_at
            + timedelta(seconds=MAX_KALI_OPERATION_AUTHORIZATION_VALIDITY_SECONDS),
        )

    def has_expired_at(self, moment: datetime) -> bool:
        """Return whether this operation approval is no longer valid."""
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise ResearchError(
                "Kali operation authorization expiry check requires an aware time."
            )
        return moment >= self.expires_at

    def _validate_window(self) -> None:
        for value, label in (
            (self.authorized_at, "authorization time"),
            (self.expires_at, "expiry time"),
        ):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ResearchError(f"Kali operation {label} must be timezone-aware.")
        if self.expires_at <= self.authorized_at:
            raise ResearchError(
                "Kali operation authorization must expire after it was given."
            )
        if (
            self.expires_at - self.authorized_at
        ).total_seconds() > MAX_KALI_OPERATION_AUTHORIZATION_VALIDITY_SECONDS:
            raise ResearchError(
                "Kali operation authorization validity exceeds its hard ceiling."
            )

    @staticmethod
    def _bounded_text(value: object, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized
