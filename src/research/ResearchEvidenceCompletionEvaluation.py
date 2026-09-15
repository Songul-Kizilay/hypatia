"""Evidence-only readiness evaluation for a bounded teaching report.

This module reads already-canonical research records.  It does not mutate a
run, close an execution, create a claim, or interpret model prose.  Its small
status is deliberately about whether the *recorded evidence* can support the
bounded report, not whether the question is universally answered.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchRun import ResearchRun
from research.ResearchSourceIndependence import ResearchSourceIndependence


class ResearchEvidenceCompletionStatus(StrEnum):
    """Truthful report-readiness states, distinct from a run lifecycle."""

    SUFFICIENTLY_SUPPORTED = "sufficiently_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    MATERIALLY_UNRESOLVED = "materially_unresolved"
    CONFLICTING = "conflicting"
    SOURCE_LIMITED = "source_limited"
    BUDGET_LIMITED = "budget_limited"
    INCOMPLETE = "incomplete"


class ResearchEvidenceCompletionLimitation(StrEnum):
    """Bounded, non-interpretive gaps visible in canonical records."""

    MISSING_EVIDENCE = "missing_evidence"
    SOURCE_LIMITED = "source_limited"
    MISSING_CORROBORATION = "missing_corroboration"
    GROUNDING_INCOMPLETE = "grounding_incomplete"
    COMPARISON_UNAVAILABLE = "comparison_unavailable"
    BUDGET_LIMITED = "budget_limited"
    EXECUTION_INCOMPLETE = "execution_incomplete"
    RECORDED_CONFLICT = "recorded_conflict"


class ResearchEvidenceCompletionCaveat(StrEnum):
    """Secondary uncertainty that never changes readiness or goal status.

    ``unknown`` source independence is neither proof of independent
    corroboration nor a failure of the bounded mission.  An explicit
    derivative or likely-duplicate judgement is the stronger caveat and is
    never rendered as merely unverified.
    """

    SOURCE_NOT_INDEPENDENT = "source_not_independent"
    SOURCE_INDEPENDENCE_UNVERIFIED = "source_independence_unverified"


@dataclass(frozen=True, slots=True)
class ResearchEvidenceCompletionEvaluation:
    """A derived explanation of report readiness; never a new authority."""

    status: ResearchEvidenceCompletionStatus
    supports_bounded_teaching: bool
    source_count: int
    evidence_count: int
    evidence_source_count: int
    assessed_source_count: int
    comparison_note_count: int
    recorded_claim_contradiction_count: int
    limitations: tuple[ResearchEvidenceCompletionLimitation, ...]
    caveats: tuple[ResearchEvidenceCompletionCaveat, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchEvidenceCompletionStatus):
            raise ResearchError("Research evidence completion status is invalid.")
        if not isinstance(self.supports_bounded_teaching, bool):
            raise ResearchError("Research evidence teaching support is invalid.")
        for value, label in (
            (self.source_count, "source count"),
            (self.evidence_count, "evidence count"),
            (self.evidence_source_count, "evidence source count"),
            (self.assessed_source_count, "assessed source count"),
            (self.comparison_note_count, "comparison note count"),
            (self.recorded_claim_contradiction_count, "contradiction count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Research evidence completion {label} is invalid.")
        if (
            not isinstance(self.limitations, tuple)
            or not all(
                isinstance(value, ResearchEvidenceCompletionLimitation)
                for value in self.limitations
            )
            or len(self.limitations) != len(set(self.limitations))
        ):
            raise ResearchError("Research evidence completion limitations are invalid.")
        if (
            not isinstance(self.caveats, tuple)
            or not all(
                isinstance(value, ResearchEvidenceCompletionCaveat)
                for value in self.caveats
            )
            or len(self.caveats) != len(set(self.caveats))
        ):
            raise ResearchError("Research evidence completion caveats are invalid.")
        if self.status is ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED:
            if not self.supports_bounded_teaching or self.limitations:
                raise ResearchError("Sufficient evidence completion is inconsistent.")
        elif self.supports_bounded_teaching and self.status not in {
            ResearchEvidenceCompletionStatus.CONFLICTING,
        }:
            raise ResearchError("Research evidence teaching support is inconsistent.")

    def summary(self) -> str:
        """Render only derived coverage facts, not a conclusion about truth."""
        labels = {
            ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED: (
                "Sufficiently supported for a bounded teaching answer"
            ),
            ResearchEvidenceCompletionStatus.PARTIALLY_SUPPORTED: "Partially supported",
            ResearchEvidenceCompletionStatus.MATERIALLY_UNRESOLVED: (
                "Materially unresolved"
            ),
            ResearchEvidenceCompletionStatus.CONFLICTING: "Recorded claims conflict",
            ResearchEvidenceCompletionStatus.SOURCE_LIMITED: "Source-limited",
            ResearchEvidenceCompletionStatus.BUDGET_LIMITED: "Budget-limited",
            ResearchEvidenceCompletionStatus.INCOMPLETE: "Incomplete execution",
        }
        return labels[self.status]


_BUDGET_STOPS = {
    AutonomyStopReason.STEP_BUDGET_EXHAUSTED.value,
    AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED.value,
    AutonomyStopReason.LLM_BUDGET_EXHAUSTED.value,
    AutonomyStopReason.TIME_BUDGET_EXHAUSTED.value,
}
_INCOMPLETE_STOPS = {
    AutonomyStopReason.STEP_BLOCKED.value,
    AutonomyStopReason.STEP_INTERRUPTED.value,
    AutonomyStopReason.STEP_FAILED.value,
    AutonomyStopReason.ADVANCE_REFUSED.value,
    AutonomyStopReason.CANCELLED.value,
}


def evaluate_evidence_completion(
    run: ResearchRun,
    stop_reason: AutonomyStopReason | str,
) -> ResearchEvidenceCompletionEvaluation:
    """Evaluate canonical evidence without treating observations as truth.

    The caller's stop reason is execution metadata, not a fresh permission or
    a life-cycle transition.  Unknown text is retained as non-budget and
    non-incomplete metadata rather than guessed into one of those categories.
    """
    if not isinstance(run, ResearchRun):
        raise ResearchError("Research evidence completion requires a research run.")
    if isinstance(stop_reason, AutonomyStopReason):
        normalized_stop = stop_reason.value
    elif isinstance(stop_reason, str) and stop_reason.strip():
        normalized_stop = stop_reason.strip()
    else:
        raise ResearchError("Research evidence completion stop reason is invalid.")

    evidence_source_ids = {record.source_document_id for record in run.evidence}
    assessed_source_ids = {record.source_document_id for record in run.assessments}
    limitations: list[ResearchEvidenceCompletionLimitation] = []
    if not run.evidence:
        limitations.append(ResearchEvidenceCompletionLimitation.MISSING_EVIDENCE)
    if len(run.sources) < 2:
        limitations.append(ResearchEvidenceCompletionLimitation.SOURCE_LIMITED)
    if run.evidence and len(evidence_source_ids) < 2:
        limitations.append(ResearchEvidenceCompletionLimitation.MISSING_CORROBORATION)
    if evidence_source_ids.difference(assessed_source_ids):
        limitations.append(ResearchEvidenceCompletionLimitation.GROUNDING_INCOMPLETE)
    if not run.comparison_notes:
        limitations.append(ResearchEvidenceCompletionLimitation.COMPARISON_UNAVAILABLE)
    if normalized_stop in _BUDGET_STOPS:
        limitations.append(ResearchEvidenceCompletionLimitation.BUDGET_LIMITED)
    if normalized_stop in _INCOMPLETE_STOPS:
        limitations.append(ResearchEvidenceCompletionLimitation.EXECUTION_INCOMPLETE)
    if run.claim_contradictions:
        limitations.append(ResearchEvidenceCompletionLimitation.RECORDED_CONFLICT)

    if normalized_stop in _BUDGET_STOPS:
        status = ResearchEvidenceCompletionStatus.BUDGET_LIMITED
    elif normalized_stop in _INCOMPLETE_STOPS:
        status = ResearchEvidenceCompletionStatus.INCOMPLETE
    elif not run.evidence:
        status = ResearchEvidenceCompletionStatus.MATERIALLY_UNRESOLVED
    elif len(run.sources) < 2:
        status = ResearchEvidenceCompletionStatus.SOURCE_LIMITED
    elif run.claim_contradictions:
        status = ResearchEvidenceCompletionStatus.CONFLICTING
    elif (
        len(evidence_source_ids) >= 2
        and not evidence_source_ids.difference(assessed_source_ids)
        and run.comparison_notes
    ):
        status = ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED
    else:
        status = ResearchEvidenceCompletionStatus.PARTIALLY_SUPPORTED

    return ResearchEvidenceCompletionEvaluation(
        status=status,
        supports_bounded_teaching=status
        in {
            ResearchEvidenceCompletionStatus.SUFFICIENTLY_SUPPORTED,
            ResearchEvidenceCompletionStatus.CONFLICTING,
        },
        source_count=len(run.sources),
        evidence_count=len(run.evidence),
        evidence_source_count=len(evidence_source_ids),
        assessed_source_count=len(assessed_source_ids),
        comparison_note_count=len(run.comparison_notes),
        recorded_claim_contradiction_count=len(run.claim_contradictions),
        limitations=tuple(limitations),
        caveats=source_independence_caveats(run),
    )


_NOT_INDEPENDENT = {
    ResearchSourceIndependence.DERIVATIVE,
    ResearchSourceIndependence.LIKELY_DUPLICATE,
}


def source_independence_caveats(
    run: ResearchRun,
) -> tuple[ResearchEvidenceCompletionCaveat, ...]:
    """Derive independence uncertainty from current canonical assessments.

    Only accepted sources that contributed evidence are relevant.  Explicitly
    superseded assessments no longer speak.  A source with no active
    assessment, or with any ``unknown`` judgement, is unverified: silence is
    never upgraded into independence.
    """
    if not isinstance(run, ResearchRun):
        raise ResearchError("Source independence caveats require a research run.")
    evidence_source_ids = {record.source_document_id for record in run.evidence}
    accepted = {source.document_id for source in run.sources}
    superseded = {
        assessment.supersedes_assessment_id
        for assessment in run.assessments
        if assessment.supersedes_assessment_id
    }
    judgements: dict[str, list[ResearchSourceIndependence]] = {
        document_id: [] for document_id in evidence_source_ids & accepted
    }
    for assessment in run.assessments:
        if (
            assessment.assessment_id not in superseded
            and assessment.source_document_id in judgements
        ):
            judgements[assessment.source_document_id].append(assessment.independence)
    not_independent = False
    unverified = False
    for values in judgements.values():
        if any(value in _NOT_INDEPENDENT for value in values):
            not_independent = True
        elif not values or any(
            value is not ResearchSourceIndependence.INDEPENDENT for value in values
        ):
            unverified = True
    caveats: list[ResearchEvidenceCompletionCaveat] = []
    if not_independent:
        caveats.append(ResearchEvidenceCompletionCaveat.SOURCE_NOT_INDEPENDENT)
    if unverified:
        caveats.append(ResearchEvidenceCompletionCaveat.SOURCE_INDEPENDENCE_UNVERIFIED)
    return tuple(caveats)
