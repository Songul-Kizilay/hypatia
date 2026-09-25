"""One immutable, operator-authored security hypothesis about a program's target.

A hypothesis names a subject (`subject_kind`/`subject_canonical_value`,
restricted to `HOSTNAME`/`IP_ADDRESS` and reusing
`research.ResearchAssetKind`/`canonicalize_asset_value` directly — no new
subject-identity machinery), what is inferred about it (`statement`), why the
evidence gathered so far suggests it (`rationale`), and what would still have
to be tested to move past inference (`required_validation`, descriptive
strategy text only — never itself permission to run anything). It is never
mutated after creation: evidence citations and status changes are separate,
append-only fact records (`ResearchSecurityHypothesisEvidenceLinkRecord`,
`ResearchSecurityHypothesisStatusTransitionRecord`) layered over this one by
`research.ResearchSecurityHypothesis.hypotheses_for_program`.

`subject_canonical_value` must already be canonical at construction, exactly
like `ResearchAssetObservationRecord` — this fails closed rather than
silently normalizing, so hostname/address canonicalization is always decided
once, by whichever caller already holds raw operator input.

This is reasoning over already-recorded evidence, not a finding: nothing
here claims a vulnerability was confirmed, and no status value derived from
these records ever will (see `ResearchSecurityHypothesisStatus`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_SECURITY_HYPOTHESIS_ID_CHARACTERS = 200
MAX_SECURITY_HYPOTHESIS_PROGRAM_ID_CHARACTERS = 200
MAX_SECURITY_HYPOTHESIS_STATEMENT_CHARACTERS = 500
MAX_SECURITY_HYPOTHESIS_RATIONALE_CHARACTERS = 2_000
MAX_SECURITY_HYPOTHESIS_REQUIRED_VALIDATION_CHARACTERS = 1_000

#: Only these two kinds have any honest producer today
#: (`ResearchHttpEvidenceRecord.target_kind` is always `HOSTNAME`, and a
#: future evidence kind may reasonably name an `IP_ADDRESS` subject). `URL`/
#: `SERVICE`/`ENDPOINT` do not exist on `ResearchAssetKind` at all yet, so
#: there is nothing further to exclude here.
_ALLOWED_SUBJECT_KINDS = (ResearchAssetKind.HOSTNAME, ResearchAssetKind.IP_ADDRESS)

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


def _bounded_required_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ResearchError(f"{label} is invalid.")
    normalized = value.strip()
    if not normalized:
        raise ResearchError(f"{label} cannot be empty.")
    if len(normalized) > maximum:
        raise ResearchError(f"{label} is too long.")
    _refuse_sensitive_input(normalized, label)
    return normalized


@dataclass(frozen=True, slots=True)
class ResearchSecurityHypothesisRecord:
    """One operator-authored conjecture about one program's named subject."""

    hypothesis_id: str
    program_id: str
    hypothesis_kind: ResearchSecurityHypothesisKind
    subject_kind: ResearchAssetKind
    subject_canonical_value: str
    statement: str
    rationale: str
    required_validation: str
    origin: ResearchSecurityHypothesisOrigin
    created_at: datetime

    def __post_init__(self) -> None:
        hypothesis_id = _bounded_identifier(
            self.hypothesis_id,
            "Security hypothesis ID",
            MAX_SECURITY_HYPOTHESIS_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Security hypothesis program ID",
            MAX_SECURITY_HYPOTHESIS_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(self.hypothesis_kind, ResearchSecurityHypothesisKind):
            raise ResearchError("Security hypothesis kind is invalid.")
        if (
            not isinstance(self.subject_kind, ResearchAssetKind)
            or self.subject_kind not in _ALLOWED_SUBJECT_KINDS
        ):
            raise ResearchError("Security hypothesis subject kind is invalid.")
        self._require_already_canonical(self.subject_kind, self.subject_canonical_value)
        statement = _bounded_required_text(
            self.statement,
            "Security hypothesis statement",
            MAX_SECURITY_HYPOTHESIS_STATEMENT_CHARACTERS,
        )
        rationale = _bounded_required_text(
            self.rationale,
            "Security hypothesis rationale",
            MAX_SECURITY_HYPOTHESIS_RATIONALE_CHARACTERS,
        )
        required_validation = _bounded_required_text(
            self.required_validation,
            "Security hypothesis required validation",
            MAX_SECURITY_HYPOTHESIS_REQUIRED_VALIDATION_CHARACTERS,
        )
        if not isinstance(self.origin, ResearchSecurityHypothesisOrigin):
            raise ResearchError("Security hypothesis origin is invalid.")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security hypothesis creation time must be timezone-aware."
            )
        object.__setattr__(self, "hypothesis_id", hypothesis_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "rationale", rationale)
        object.__setattr__(self, "required_validation", required_validation)

    @staticmethod
    def _require_already_canonical(kind: ResearchAssetKind, value: str) -> None:
        """Fail closed unless `value` is already the kind-appropriate canonical form."""
        if not isinstance(value, str) or not value:
            raise ResearchError("Security hypothesis subject value is invalid.")
        try:
            expected = canonicalize_asset_value(kind, value)
        except ResearchError as error:
            raise ResearchError(
                "Security hypothesis subject value is not canonical."
            ) from error
        if expected != value:
            raise ResearchError("Security hypothesis subject value is not canonical.")
