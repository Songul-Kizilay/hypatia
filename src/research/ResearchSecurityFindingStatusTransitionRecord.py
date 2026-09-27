"""One immutable, append-only fact: a security finding's status changed.

Status is never stored as a mutable field on the founding record — it is
always the latest of these transitions (or `CANDIDATE` if none exists),
derived by `research.ResearchSecurityFinding.findings_for_program`, so it can
never drift from the record that produced it. `ResearchSecurityFindingStatus`'s
own closed table (`is_valid_status_transition`) plus the evidence-gate and
linkage rules are enforced by the application service before one of these is
ever constructed; this record does not itself re-check the transition's
legality, only that `status` is a real member, `reason` is bounded, inert,
operator-authored text, and `duplicate_of_finding_id`/
`superseded_by_finding_id` are fail-closed 1:1 bound to `status`.

`duplicate_of_finding_id` is populated exactly when `status is DUPLICATE`,
`None` otherwise; `superseded_by_finding_id` is populated exactly when
`status is SUPERSEDED`, `None` otherwise — mirroring
`ResearchAssetObservationRecord`'s `source_operation_digest`/`provenance`
fail-closed 1:1 binding discipline. This record only validates that binding
and each linkage value's shape; it cannot check that the named finding
actually exists, differs from this one, or shares this program — those
cross-reference checks need the real finding and belong to the application
service.

`reason` may be empty. A status change needs no justification to be an
honest fact about what an operator decided, mirroring
`ResearchSecurityHypothesisStatusTransitionRecord.reason`'s own discipline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_SECURITY_FINDING_STATUS_TRANSITION_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_STATUS_TRANSITION_FINDING_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_STATUS_TRANSITION_PROGRAM_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_STATUS_TRANSITION_REASON_CHARACTERS = 500
MAX_SECURITY_FINDING_STATUS_TRANSITION_LINKED_FINDING_ID_CHARACTERS = 200

_SENSITIVE_INPUT_POLICY = ResearchSensitiveInputPolicy()


def _bounded_identifier(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ResearchError(f"{label} is invalid.")
    normalized = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ResearchError(f"{label} must be single-line text.")
    return normalized


def _refuse_sensitive_input(value: str, label: str) -> None:
    sensitive_class = _SENSITIVE_INPUT_POLICY.classify(value)
    if sensitive_class.refused:
        raise ResearchError(f"{label} was refused as {sensitive_class.operator_label}.")


def _require_bound_linkage(
    status: ResearchSecurityFindingStatus,
    duplicate_of_finding_id: str | None,
    superseded_by_finding_id: str | None,
) -> tuple[str | None, str | None]:
    """Fail closed unless the linkage fields are bound 1:1 to `status`.

    Exactly one of `duplicate_of_finding_id`/`superseded_by_finding_id` is
    non-`None` when `status` is the matching one of `DUPLICATE`/`SUPERSEDED`;
    both are `None` for every other status.
    """
    if status is ResearchSecurityFindingStatus.DUPLICATE:
        if superseded_by_finding_id is not None:
            raise ResearchError(
                "Security finding status transition cannot carry a superseded-by"
                " reference for a duplicate status."
            )
        normalized_duplicate = _bounded_identifier(
            duplicate_of_finding_id,
            "Security finding duplicate-of reference",
            MAX_SECURITY_FINDING_STATUS_TRANSITION_LINKED_FINDING_ID_CHARACTERS,
        )
        return normalized_duplicate, None
    if status is ResearchSecurityFindingStatus.SUPERSEDED:
        if duplicate_of_finding_id is not None:
            raise ResearchError(
                "Security finding status transition cannot carry a duplicate-of"
                " reference for a superseded status."
            )
        normalized_superseded = _bounded_identifier(
            superseded_by_finding_id,
            "Security finding superseded-by reference",
            MAX_SECURITY_FINDING_STATUS_TRANSITION_LINKED_FINDING_ID_CHARACTERS,
        )
        return None, normalized_superseded
    if duplicate_of_finding_id is not None or superseded_by_finding_id is not None:
        raise ResearchError(
            "Security finding status transition linkage is only valid for a"
            " duplicate or superseded status."
        )
    return None, None


@dataclass(frozen=True, slots=True)
class ResearchSecurityFindingStatusTransitionRecord:
    """One recorded fact: this security finding moved to this status."""

    transition_id: str
    finding_id: str
    program_id: str
    status: ResearchSecurityFindingStatus
    reason: str
    duplicate_of_finding_id: str | None
    superseded_by_finding_id: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        transition_id = _bounded_identifier(
            self.transition_id,
            "Security finding status transition ID",
            MAX_SECURITY_FINDING_STATUS_TRANSITION_ID_CHARACTERS,
        )
        finding_id = _bounded_identifier(
            self.finding_id,
            "Security finding status transition finding ID",
            MAX_SECURITY_FINDING_STATUS_TRANSITION_FINDING_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Security finding status transition program ID",
            MAX_SECURITY_FINDING_STATUS_TRANSITION_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.status, ResearchSecurityFindingStatus):
            raise ResearchError("Security finding status is invalid.")
        if not isinstance(self.reason, str):
            raise ResearchError("Security finding status transition reason is invalid.")
        reason = self.reason.strip()
        if len(reason) > MAX_SECURITY_FINDING_STATUS_TRANSITION_REASON_CHARACTERS:
            raise ResearchError(
                "Security finding status transition reason is too long."
            )
        _refuse_sensitive_input(reason, "Security finding status transition reason")
        duplicate_of_finding_id, superseded_by_finding_id = _require_bound_linkage(
            self.status, self.duplicate_of_finding_id, self.superseded_by_finding_id
        )
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security finding status transition recorded time must be"
                " timezone-aware."
            )
        object.__setattr__(self, "transition_id", transition_id)
        object.__setattr__(self, "finding_id", finding_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "duplicate_of_finding_id", duplicate_of_finding_id)
        object.__setattr__(self, "superseded_by_finding_id", superseded_by_finding_id)
