"""Pure, bounded security-finding view derived from recorded facts only.

Modeled directly on `research.ResearchSecurityHypothesis.py`'s type-plus-
builder shape: fields mirroring the founding `ResearchSecurityFindingRecord`
plus the evidence links and status transitions recorded against it, derived
fresh from already-persisted data on every read. `ResearchSecurityFinding` is
never itself persisted — there is no "find an existing finding and mutate
it" persistence logic anywhere; `findings_for_program` recomputes identical
output from the same three flat logs on every call.

`status` is the latest of `status_history` by persisted append order (the
store's own append-only write discipline already guarantees this order is
causal and tamper-evident; wall-clock `recorded_at` is kept only as a
displayed field, never as an ordering key, so a clock regression or two
same-instant transitions can never misorder the derived status), or
`CANDIDATE` if none has ever been recorded — never a stored,
independently-settable field, so it can never drift from the transitions
that produced it. No value `status` can take asserts a confirmed
vulnerability (see
`ResearchSecurityFindingStatus.means_confirmed_vulnerability`), including
`VALIDATED`.

`supporting_evidence`/`contradicting_evidence`/`validation_evidence` are
three disjoint tuples, never netted against each other, mirroring
`ResearchSecurityHypothesis`'s own supporting/contradicting discipline plus
one addition: `validation_evidence` is the one and only real gate for the
`VALIDATED` status.

`needs_attention` is a second derived-read property, purely a function of
the two facts above (current `status`, current `contradicting_evidence`).
It is a current-state observation only: `attach_evidence` has no gate of
its own (see `cognition.ResearchSecurityFindingApplicationService`), so a
legitimate history can record `CONTRADICTS` evidence after an
already-recorded `VALIDATED` transition, and `evidence_links`/
`status_transitions` are two independently-append-ordered lists with no
interleaving field between them — replay cannot and does not attempt to
say which came first (the identical limitation
`research.ResearchSecurityFindingLifecycleIntegrity` already documents and
deliberately declines to check). `needs_attention` therefore never claims
the contradiction predates the validation, that the validation was
historically invalid, or that the finding is refuted — it names only that
a human should look again. CONTRADICTING EVIDENCE != AUTOMATIC REFUTATION.

`evidence_ceiling` is a third derived-read property, returning a
`ResearchSecurityFindingEvidenceCeiling`: what the recorded evidence
*structure* can defensibly support, never a truth-confidence. See that
property's own docstring for the exact rule and why `HIGH` is
permanently unreachable from today's finding evidence model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchSecurityFindingEvidenceCeiling import (
    ResearchSecurityFindingEvidenceCeiling,
)
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

    @property
    def needs_attention(self) -> bool:
        """Return whether this finding's *current* state needs a human look.

        `True` only when `status` is currently `VALIDATED` and one or more
        `CONTRADICTS` evidence links currently exist for this finding.
        Current state only: makes no claim about when the contradiction was
        recorded relative to the `VALIDATED` transition, whether validation
        was historically invalid, or that the finding is refuted. See the
        class docstring's `needs_attention` paragraph.
        """
        return (
            self.status is ResearchSecurityFindingStatus.VALIDATED
            and len(self.contradicting_evidence) > 0
        )

    @property
    def evidence_ceiling(self) -> ResearchSecurityFindingEvidenceCeiling:
        """Return what this finding's *current* evidence structure can
        defensibly support -- never a probability, never a truth-confidence.

        Presence/absence only, never a count: `MEDIUM` is reached by one
        `VALIDATES` link exactly as readily as by ten, mirroring
        `_require_validation_gate`'s own existing rule ("at least one
        validating evidence citation") rather than inventing a new
        magnitude concept. Two links citing the same `evidence_id` are two
        recorded facts, never counted as two independent ones -- this
        property counts neither, so a repeated citation cannot move the
        ceiling at all.

        Reachable tiers, in order of precedence:

        1. `UNASSESSED` -- `status` is currently `REFUTED`. `REFUTED` is
           reachable from any non-terminal status by a bare operator
           judgement (`_require_linkage`/`is_valid_status_transition` gate
           only the *linkage* fields for `DUPLICATE`/`SUPERSEDED`; no
           analogous `_require_refutation_gate` exists), so a finding can
           be `REFUTED` with strong-looking `VALIDATES` evidence still on
           record. A ceiling naming that evidence `MEDIUM` right next to an
           explicit operator refutation would misdescribe the record more
           than it would inform a reader; the operator's own explicit
           terminal judgement dominates.
        2. `UNASSESSED` -- one or more `CONTRADICTS` links currently exist,
           regardless of what else is recorded. Mirrors
           `ResearchClaimCalibrator._ceilings`'s own identical rule for the
           unrelated claim subsystem (`if profile.contradicted: return
           ..., ResearchClaimConfidence.UNASSESSED`) -- the same pattern,
           not the same code, applied to this type's own evidence shape.
           This is a ceiling constraint only: it changes nothing about
           `status` or `needs_attention`. CONTRADICTING EVIDENCE !=
           AUTOMATIC REFUTATION.
        3. `MEDIUM` -- one or more `VALIDATES` links currently exist (and
           none of the above applied).
        4. `LOW` -- one or more `SUPPORTS` links currently exist (and none
           of the above applied).
        5. `UNASSESSED` -- no evidence links of any kind are currently
           recorded.

        `HIGH` is never returned: reaching it would require an
        independence or trust judgement over the cited evidence that this
        record does not carry (see
        `research.ResearchSecurityFindingEvidenceCeiling`'s module
        docstring). `DUPLICATE`/`SUPERSEDED` are administrative
        dispositions, not evidentiary judgements, and are deliberately
        given no special case here -- the ceiling for those statuses still
        reflects the evidence structure exactly as it would for any other
        non-`REFUTED` status. Reproduction Record history plays no part in
        this property at all: an operator's own manual observation is not
        independent corroboration and `REPRODUCED` is never confirmed
        vulnerability truth (see `research.ResearchReproductionOutcome`).
        """
        if self.status is ResearchSecurityFindingStatus.REFUTED:
            return ResearchSecurityFindingEvidenceCeiling.UNASSESSED
        if len(self.contradicting_evidence) > 0:
            return ResearchSecurityFindingEvidenceCeiling.UNASSESSED
        if len(self.validation_evidence) > 0:
            return ResearchSecurityFindingEvidenceCeiling.MEDIUM
        if len(self.supporting_evidence) > 0:
            return ResearchSecurityFindingEvidenceCeiling.LOW
        return ResearchSecurityFindingEvidenceCeiling.UNASSESSED


def _latest_status(
    transitions: tuple[ResearchSecurityFindingStatusTransitionRecord, ...],
) -> ResearchSecurityFindingStatus:
    """Return the causally-latest status: the last entry in append order.

    `transitions` must already be in the store's own persisted append order
    (see `findings_for_program` below) — never re-sorted by `recorded_at`,
    which is a wall-clock display value, not a causal ordering signal.
    """
    if not transitions:
        return ResearchSecurityFindingStatus.CANDIDATE
    return transitions[-1].status


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
        # Preserve `status_transitions`' own persisted append order rather
        # than re-sorting by `recorded_at` — the store's append-only write
        # discipline already makes that order causal and tamper-evident; a
        # wall-clock regression must never be able to reorder it.
        transitions = tuple(
            transition
            for transition in status_transitions
            if transition.finding_id == record.finding_id
            and transition.program_id == record.program_id
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
