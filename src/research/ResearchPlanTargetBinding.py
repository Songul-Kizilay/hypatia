"""An exact program and target scope, not ownership or permission evidence."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchTargetScope import ResearchTargetScope

MAX_TARGET_PROGRAM_ID_CHARACTERS = 200
MAX_TARGET_SCOPE_REVISION_ID_CHARACTERS = 200
_DIGEST_CHARACTERS = 64


def _bounded_optional_id(
    value: str | None,
    label: str,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ResearchError(f"{label} cannot be empty.")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ResearchError(f"{label} is too long.")
    return normalized


def _is_lower_sha256_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _DIGEST_CHARACTERS
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True, slots=True)
class ResearchPlanTargetBinding:
    """Bind authored program identity to immutable target rules.

    This value grants no authority and records no confirmation or signature.
    The containing plan and its approval must establish execution permission.
    """

    program_id: str
    scope: ResearchTargetScope
    scope_revision_id: str | None = None
    scope_revision_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ResearchError("Target program ID cannot be empty.")
        normalized = self.program_id.strip()
        if len(normalized) > MAX_TARGET_PROGRAM_ID_CHARACTERS:
            raise ResearchError("Target program ID is too long.")
        if not isinstance(self.scope, ResearchTargetScope):
            raise ResearchError("Target plan binding requires a validated scope.")
        if (self.scope_revision_id is None) != (self.scope_revision_digest is None):
            raise ResearchError(
                "Target scope revision binding requires both identity and digest."
            )
        revision_id = _bounded_optional_id(
            self.scope_revision_id,
            "Target scope revision ID",
            MAX_TARGET_SCOPE_REVISION_ID_CHARACTERS,
        )
        if self.scope_revision_digest is not None and not _is_lower_sha256_hex(
            self.scope_revision_digest
        ):
            raise ResearchError("Target scope revision digest is invalid.")
        object.__setattr__(self, "program_id", normalized)
        object.__setattr__(self, "scope_revision_id", revision_id)

    @property
    def has_scope_revision(self) -> bool:
        """Return whether this target is bound to an exact scope revision."""
        return (
            self.scope_revision_id is not None
            and self.scope_revision_digest is not None
        )
