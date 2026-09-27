"""One immutable, operator-authored security finding promoted from a hypothesis.

A finding names a subject (`subject_kind`/`subject_canonical_value`,
restricted to `HOSTNAME`/`IP_ADDRESS` and reusing
`research.ResearchAssetKind`/`canonicalize_asset_value` directly — no new
subject-identity machinery), a `title` and `description` of what was
observed, and `required_followup` — descriptive strategy text about what
would still need doing, never itself permission to run anything. It is never
mutated after creation: evidence citations and status changes are separate,
append-only fact records (`ResearchSecurityFindingEvidenceLinkRecord`,
`ResearchSecurityFindingStatusTransitionRecord`) layered over this one by
`research.ResearchSecurityFinding.findings_for_program`.

`finding_kind` reuses `ResearchSecurityHypothesisKind` unchanged — a finding
may inherit from Security Hypothesis categories, so no new classification
vocabulary is introduced here. `source_hypothesis_id` names the one
`ResearchSecurityHypothesisRecord` this finding was promoted from; the
application service enforces that promotion is gated on that hypothesis's
current status and that at most one finding exists per hypothesis, not this
record (which only validates the ID's shape).

`subject_canonical_value` must already be canonical at construction, exactly
like `ResearchSecurityHypothesisRecord` — this fails closed rather than
silently normalizing.

There is deliberately no `disposition` field: `status` (on the derived read
model `ResearchSecurityFinding`) already names the disposition, and a second
field asserting the same fact would only risk drifting from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_SECURITY_FINDING_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_PROGRAM_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_SOURCE_HYPOTHESIS_ID_CHARACTERS = 200
MAX_SECURITY_FINDING_TITLE_CHARACTERS = 200
MAX_SECURITY_FINDING_DESCRIPTION_CHARACTERS = 2_000
MAX_SECURITY_FINDING_REQUIRED_FOLLOWUP_CHARACTERS = 1_000

#: Only these two kinds have any honest producer today, mirroring
#: `ResearchSecurityHypothesisRecord`'s own restriction exactly (a finding's
#: subject is always copied from its source hypothesis, which is itself
#: restricted this way).
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
class ResearchSecurityFindingRecord:
    """One operator-authored finding promoted from one program's hypothesis."""

    finding_id: str
    program_id: str
    source_hypothesis_id: str
    finding_kind: ResearchSecurityHypothesisKind
    subject_kind: ResearchAssetKind
    subject_canonical_value: str
    title: str
    description: str
    required_followup: str
    origin: ResearchSecurityFindingOrigin
    created_at: datetime

    def __post_init__(self) -> None:
        finding_id = _bounded_identifier(
            self.finding_id,
            "Security finding ID",
            MAX_SECURITY_FINDING_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Security finding program ID",
            MAX_SECURITY_FINDING_PROGRAM_ID_CHARACTERS,
        )
        source_hypothesis_id = _bounded_identifier(
            self.source_hypothesis_id,
            "Security finding source hypothesis ID",
            MAX_SECURITY_FINDING_SOURCE_HYPOTHESIS_ID_CHARACTERS,
        )
        if not isinstance(self.finding_kind, ResearchSecurityHypothesisKind):
            raise ResearchError("Security finding kind is invalid.")
        if (
            not isinstance(self.subject_kind, ResearchAssetKind)
            or self.subject_kind not in _ALLOWED_SUBJECT_KINDS
        ):
            raise ResearchError("Security finding subject kind is invalid.")
        self._require_already_canonical(self.subject_kind, self.subject_canonical_value)
        title = _bounded_required_text(
            self.title,
            "Security finding title",
            MAX_SECURITY_FINDING_TITLE_CHARACTERS,
        )
        description = _bounded_required_text(
            self.description,
            "Security finding description",
            MAX_SECURITY_FINDING_DESCRIPTION_CHARACTERS,
        )
        required_followup = _bounded_required_text(
            self.required_followup,
            "Security finding required followup",
            MAX_SECURITY_FINDING_REQUIRED_FOLLOWUP_CHARACTERS,
        )
        if not isinstance(self.origin, ResearchSecurityFindingOrigin):
            raise ResearchError("Security finding origin is invalid.")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security finding creation time must be timezone-aware."
            )
        object.__setattr__(self, "finding_id", finding_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "source_hypothesis_id", source_hypothesis_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "required_followup", required_followup)

    @staticmethod
    def _require_already_canonical(kind: ResearchAssetKind, value: str) -> None:
        """Fail closed unless `value` is already the kind-appropriate canonical form."""
        if not isinstance(value, str) or not value:
            raise ResearchError("Security finding subject value is invalid.")
        try:
            expected = canonicalize_asset_value(kind, value)
        except ResearchError as error:
            raise ResearchError(
                "Security finding subject value is not canonical."
            ) from error
        if expected != value:
            raise ResearchError("Security finding subject value is not canonical.")
