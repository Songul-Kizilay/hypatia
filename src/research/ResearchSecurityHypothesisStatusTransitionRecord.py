"""One immutable, append-only fact: a security hypothesis's status changed.

Status is never stored as a mutable field on the founding record — it is
always the latest of these transitions (or `OPEN` if none exists), derived by
`research.ResearchSecurityHypothesis.hypotheses_for_program`, so it can never
drift from the record that produced it. `ResearchSecurityHypothesisStatus`'s
own closed table (`is_valid_status_transition`) is enforced by the
application service before one of these is ever constructed; this record
does not itself re-check the transition's legality, only that `status` is a
real member and `reason` is bounded, inert, operator-authored text.

`reason` may be empty. A status change needs no justification to be an
honest fact about what an operator decided — requiring one here would only
produce boilerplate that trivially passes the sensitive-input check anyway,
mirroring every other optional `note`/reason field already in this codebase
(e.g. `ResearchAssetObservationRecord.note`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_ID_CHARACTERS = 200
MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_HYPOTHESIS_ID_CHARACTERS = 200
MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_PROGRAM_ID_CHARACTERS = 200
MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_REASON_CHARACTERS = 500

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


@dataclass(frozen=True, slots=True)
class ResearchSecurityHypothesisStatusTransitionRecord:
    """One recorded fact: this security hypothesis moved to this status."""

    transition_id: str
    hypothesis_id: str
    program_id: str
    status: ResearchSecurityHypothesisStatus
    reason: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        transition_id = _bounded_identifier(
            self.transition_id,
            "Security hypothesis status transition ID",
            MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_ID_CHARACTERS,
        )
        hypothesis_id = _bounded_identifier(
            self.hypothesis_id,
            "Security hypothesis status transition hypothesis ID",
            MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_HYPOTHESIS_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Security hypothesis status transition program ID",
            MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.status, ResearchSecurityHypothesisStatus):
            raise ResearchError("Security hypothesis status is invalid.")
        if not isinstance(self.reason, str):
            raise ResearchError(
                "Security hypothesis status transition reason is invalid."
            )
        reason = self.reason.strip()
        if len(reason) > MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITION_REASON_CHARACTERS:
            raise ResearchError(
                "Security hypothesis status transition reason is too long."
            )
        _refuse_sensitive_input(reason, "Security hypothesis status transition reason")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security hypothesis status transition recorded time must be"
                " timezone-aware."
            )
        object.__setattr__(self, "transition_id", transition_id)
        object.__setattr__(self, "hypothesis_id", hypothesis_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "reason", reason)
