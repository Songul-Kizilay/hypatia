"""Pure, bounded security-hypothesis view derived from recorded facts only.

Modeled directly on `ResearchAsset.py`'s type-plus-builder shape: fields
mirroring the founding `ResearchSecurityHypothesisRecord` plus the evidence
links and status transitions recorded against it, derived fresh from
already-persisted data on every read. `ResearchSecurityHypothesis` is never
itself persisted — there is no "find an existing hypothesis and mutate it"
persistence logic anywhere; `hypotheses_for_program` recomputes identical
output from the same three flat logs on every call.

`status` is the latest of `status_history` by `recorded_at` (ties broken by
`transition_id`), or `OPEN` if none has ever been recorded — never a stored,
independently-settable field, so it can never drift from the transitions that
produced it. No value `status` can take asserts a validated vulnerability
(see `ResearchSecurityHypothesisStatus.means_validated_vulnerability`): this
is reasoning over evidence, not a finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchSecurityHypothesisEvidenceLinkRecord import (
    ResearchSecurityHypothesisEvidenceLinkRecord,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSecurityHypothesisRecord import ResearchSecurityHypothesisRecord
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from research.ResearchSecurityHypothesisStatusTransitionRecord import (
    ResearchSecurityHypothesisStatusTransitionRecord,
)

_ALLOWED_SUBJECT_KINDS = (ResearchAssetKind.HOSTNAME, ResearchAssetKind.IP_ADDRESS)


@dataclass(frozen=True, slots=True)
class ResearchSecurityHypothesis:
    """One security hypothesis, its cited evidence, and its status history."""

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
    supporting_evidence: tuple[ResearchSecurityHypothesisEvidenceLinkRecord, ...]
    contradicting_evidence: tuple[ResearchSecurityHypothesisEvidenceLinkRecord, ...]
    status: ResearchSecurityHypothesisStatus
    status_history: tuple[ResearchSecurityHypothesisStatusTransitionRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis_id, str) or not self.hypothesis_id.strip():
            raise ResearchError("Security hypothesis ID is invalid.")
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ResearchError("Security hypothesis program ID is invalid.")
        if not isinstance(self.hypothesis_kind, ResearchSecurityHypothesisKind):
            raise ResearchError("Security hypothesis kind is invalid.")
        if (
            not isinstance(self.subject_kind, ResearchAssetKind)
            or self.subject_kind not in _ALLOWED_SUBJECT_KINDS
        ):
            raise ResearchError("Security hypothesis subject kind is invalid.")
        if (
            not isinstance(self.subject_canonical_value, str)
            or not self.subject_canonical_value
        ):
            raise ResearchError("Security hypothesis subject value is invalid.")
        for value, label in (
            (self.statement, "statement"),
            (self.rationale, "rationale"),
            (self.required_validation, "required validation"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Security hypothesis {label} is invalid.")
        if not isinstance(self.origin, ResearchSecurityHypothesisOrigin):
            raise ResearchError("Security hypothesis origin is invalid.")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security hypothesis creation time must be timezone-aware."
            )
        for values, label in (
            (self.supporting_evidence, "supporting"),
            (self.contradicting_evidence, "contradicting"),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(value, ResearchSecurityHypothesisEvidenceLinkRecord)
                for value in values
            ):
                raise ResearchError(f"Security hypothesis {label} evidence is invalid.")
            if any(
                (value.hypothesis_id, value.program_id)
                != (self.hypothesis_id, self.program_id)
                for value in values
            ):
                raise ResearchError(
                    f"Security hypothesis {label} evidence does not belong to"
                    " this hypothesis."
                )
        if not isinstance(self.status, ResearchSecurityHypothesisStatus):
            raise ResearchError("Security hypothesis status is invalid.")
        if not isinstance(self.status_history, tuple) or any(
            not isinstance(value, ResearchSecurityHypothesisStatusTransitionRecord)
            for value in self.status_history
        ):
            raise ResearchError("Security hypothesis status history is invalid.")
        if any(
            (value.hypothesis_id, value.program_id)
            != (self.hypothesis_id, self.program_id)
            for value in self.status_history
        ):
            raise ResearchError(
                "Security hypothesis status history does not belong to this"
                " hypothesis."
            )


def _latest_status(
    transitions: tuple[ResearchSecurityHypothesisStatusTransitionRecord, ...],
) -> ResearchSecurityHypothesisStatus:
    if not transitions:
        return ResearchSecurityHypothesisStatus.OPEN
    latest = max(
        transitions, key=lambda entry: (entry.recorded_at, entry.transition_id)
    )
    return latest.status


def hypotheses_for_program(
    program_id: str,
    hypotheses: tuple[ResearchSecurityHypothesisRecord, ...],
    evidence_links: tuple[ResearchSecurityHypothesisEvidenceLinkRecord, ...],
    status_transitions: tuple[ResearchSecurityHypothesisStatusTransitionRecord, ...],
) -> tuple[ResearchSecurityHypothesis, ...]:
    """Derive one program's security hypotheses fresh from the flat persisted logs.

    Preserves each hypothesis's persisted order. Deterministic: identical
    input always produces byte-identical output, so restart/reload can never
    fabricate a fresher status than the recorded transitions support.
    """
    if not isinstance(program_id, str) or not program_id.strip():
        raise ResearchError("Security hypothesis program ID cannot be empty.")
    normalized_program_id = program_id.strip()
    if not isinstance(hypotheses, tuple) or any(
        not isinstance(value, ResearchSecurityHypothesisRecord) for value in hypotheses
    ):
        raise ResearchError("Security hypotheses are invalid.")
    if not isinstance(evidence_links, tuple) or any(
        not isinstance(value, ResearchSecurityHypothesisEvidenceLinkRecord)
        for value in evidence_links
    ):
        raise ResearchError("Security hypothesis evidence links are invalid.")
    if not isinstance(status_transitions, tuple) or any(
        not isinstance(value, ResearchSecurityHypothesisStatusTransitionRecord)
        for value in status_transitions
    ):
        raise ResearchError("Security hypothesis status transitions are invalid.")
    results: list[ResearchSecurityHypothesis] = []
    for record in hypotheses:
        if record.program_id != normalized_program_id:
            continue
        supporting = tuple(
            link
            for link in evidence_links
            if link.hypothesis_id == record.hypothesis_id
            and link.program_id == record.program_id
            and link.relation is ResearchSecurityHypothesisEvidenceRelation.SUPPORTS
        )
        contradicting = tuple(
            link
            for link in evidence_links
            if link.hypothesis_id == record.hypothesis_id
            and link.program_id == record.program_id
            and link.relation is ResearchSecurityHypothesisEvidenceRelation.CONTRADICTS
        )
        transitions = tuple(
            sorted(
                (
                    transition
                    for transition in status_transitions
                    if transition.hypothesis_id == record.hypothesis_id
                    and transition.program_id == record.program_id
                ),
                key=lambda entry: (entry.recorded_at, entry.transition_id),
            )
        )
        results.append(
            ResearchSecurityHypothesis(
                hypothesis_id=record.hypothesis_id,
                program_id=record.program_id,
                hypothesis_kind=record.hypothesis_kind,
                subject_kind=record.subject_kind,
                subject_canonical_value=record.subject_canonical_value,
                statement=record.statement,
                rationale=record.rationale,
                required_validation=record.required_validation,
                origin=record.origin,
                created_at=record.created_at,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                status=_latest_status(transitions),
                status_history=transitions,
            )
        )
    return tuple(results)
