"""Pure, bounded security-finding view derived from recorded facts only.

Modeled directly on `research.ResearchSecurityHypothesis.py`'s type-plus-
builder shape: fields mirroring the founding `ResearchSecurityFindingRecord`
plus the evidence links and status transitions recorded against it, derived
fresh from already-persisted data on every read. `ResearchSecurityFinding` is
never itself persisted — there is no "find an existing finding and mutate
it" persistence logic anywhere; `findings_for_program` recomputes identical
output from the same three flat logs on every call.

`status` is the latest of `status_history` by `recorded_at` (ties broken by
`transition_id`), or `CANDIDATE` if none has ever been recorded — never a
stored, independently-settable field, so it can never drift from the
transitions that produced it. No value `status` can take asserts a confirmed
vulnerability (see
`ResearchSecurityFindingStatus.means_confirmed_vulnerability`), including
`VALIDATED`.

`supporting_evidence`/`contradicting_evidence`/`validation_evidence` are
three disjoint tuples, never netted against each other, mirroring
`ResearchSecurityHypothesis`'s own supporting/contradicting discipline plus
one addition: `validation_evidence` is the one and only real gate for the
`VALIDATED` status.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingRecord import ResearchSecurityFindingRecord
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind

_ALLOWED_SUBJECT_KINDS = (ResearchAssetKind.HOSTNAME, ResearchAssetKind.IP_ADDRESS)


@dataclass(frozen=True, slots=True)
class ResearchSecurityFinding:
    """One security finding, its cited evidence, and its status history."""

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
    supporting_evidence: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...]
    contradicting_evidence: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...]
    validation_evidence: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...]
    status: ResearchSecurityFindingStatus
    status_history: tuple[ResearchSecurityFindingStatusTransitionRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.finding_id, str) or not self.finding_id.strip():
            raise ResearchError("Security finding ID is invalid.")
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ResearchError("Security finding program ID is invalid.")
        if (
            not isinstance(self.source_hypothesis_id, str)
            or not self.source_hypothesis_id.strip()
        ):
            raise ResearchError("Security finding source hypothesis ID is invalid.")
        if not isinstance(self.finding_kind, ResearchSecurityHypothesisKind):
            raise ResearchError("Security finding kind is invalid.")
        if (
            not isinstance(self.subject_kind, ResearchAssetKind)
            or self.subject_kind not in _ALLOWED_SUBJECT_KINDS
        ):
            raise ResearchError("Security finding subject kind is invalid.")
        if (
            not isinstance(self.subject_canonical_value, str)
            or not self.subject_canonical_value
        ):
            raise ResearchError("Security finding subject value is invalid.")
        for value, label in (
            (self.title, "title"),
            (self.description, "description"),
            (self.required_followup, "required followup"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Security finding {label} is invalid.")
        if not isinstance(self.origin, ResearchSecurityFindingOrigin):
            raise ResearchError("Security finding origin is invalid.")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security finding creation time must be timezone-aware."
            )
        for values, label in (
            (self.supporting_evidence, "supporting"),
            (self.contradicting_evidence, "contradicting"),
            (self.validation_evidence, "validation"),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(value, ResearchSecurityFindingEvidenceLinkRecord)
                for value in values
            ):
                raise ResearchError(f"Security finding {label} evidence is invalid.")
            identity = (self.finding_id, self.program_id)
            if any(
                (value.finding_id, value.program_id) != identity for value in values
            ):
                raise ResearchError(
                    f"Security finding {label} evidence does not belong to"
                    " this finding."
                )
        if not isinstance(self.status, ResearchSecurityFindingStatus):
            raise ResearchError("Security finding status is invalid.")
        if not isinstance(self.status_history, tuple) or any(
            not isinstance(value, ResearchSecurityFindingStatusTransitionRecord)
            for value in self.status_history
        ):
            raise ResearchError("Security finding status history is invalid.")
        if any(
            (value.finding_id, value.program_id) != (self.finding_id, self.program_id)
            for value in self.status_history
        ):
            raise ResearchError(
                "Security finding status history does not belong to this finding."
            )


def _latest_status(
    transitions: tuple[ResearchSecurityFindingStatusTransitionRecord, ...],
) -> ResearchSecurityFindingStatus:
    if not transitions:
        return ResearchSecurityFindingStatus.CANDIDATE
    latest = max(
        transitions, key=lambda entry: (entry.recorded_at, entry.transition_id)
    )
    return latest.status


def findings_for_program(
    program_id: str,
    findings: tuple[ResearchSecurityFindingRecord, ...],
    evidence_links: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...],
    status_transitions: tuple[ResearchSecurityFindingStatusTransitionRecord, ...],
) -> tuple[ResearchSecurityFinding, ...]:
    """Derive one program's security findings fresh from the flat persisted logs.

    Preserves each finding's persisted order. Deterministic: identical input
    always produces byte-identical output, so restart/reload can never
    fabricate a fresher status than the recorded transitions support.
    """
    if not isinstance(program_id, str) or not program_id.strip():
        raise ResearchError("Security finding program ID cannot be empty.")
    normalized_program_id = program_id.strip()
    if not isinstance(findings, tuple) or any(
        not isinstance(value, ResearchSecurityFindingRecord) for value in findings
    ):
        raise ResearchError("Security findings are invalid.")
    if not isinstance(evidence_links, tuple) or any(
        not isinstance(value, ResearchSecurityFindingEvidenceLinkRecord)
        for value in evidence_links
    ):
        raise ResearchError("Security finding evidence links are invalid.")
    if not isinstance(status_transitions, tuple) or any(
        not isinstance(value, ResearchSecurityFindingStatusTransitionRecord)
        for value in status_transitions
    ):
        raise ResearchError("Security finding status transitions are invalid.")
    results: list[ResearchSecurityFinding] = []
    for record in findings:
        if record.program_id != normalized_program_id:
            continue
        supporting = tuple(
            link
            for link in evidence_links
            if link.finding_id == record.finding_id
            and link.program_id == record.program_id
            and link.relation is ResearchSecurityFindingEvidenceRelation.SUPPORTS
        )
        contradicting = tuple(
            link
            for link in evidence_links
            if link.finding_id == record.finding_id
            and link.program_id == record.program_id
            and link.relation is ResearchSecurityFindingEvidenceRelation.CONTRADICTS
        )
        validation = tuple(
            link
            for link in evidence_links
            if link.finding_id == record.finding_id
            and link.program_id == record.program_id
            and link.relation is ResearchSecurityFindingEvidenceRelation.VALIDATES
        )
        transitions = tuple(
            sorted(
                (
                    transition
                    for transition in status_transitions
                    if transition.finding_id == record.finding_id
                    and transition.program_id == record.program_id
                ),
                key=lambda entry: (entry.recorded_at, entry.transition_id),
            )
        )
        results.append(
            ResearchSecurityFinding(
                finding_id=record.finding_id,
                program_id=record.program_id,
                source_hypothesis_id=record.source_hypothesis_id,
                finding_kind=record.finding_kind,
                subject_kind=record.subject_kind,
                subject_canonical_value=record.subject_canonical_value,
                title=record.title,
                description=record.description,
                required_followup=record.required_followup,
                origin=record.origin,
                created_at=record.created_at,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                validation_evidence=validation,
                status=_latest_status(transitions),
                status_history=transitions,
            )
        )
    return tuple(results)
