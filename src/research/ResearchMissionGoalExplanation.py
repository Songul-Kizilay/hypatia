"""Typed, bounded explanation of a mission's evidence-grounded result.

This projection makes an existing mission result legible to an operator.  It
does not interpret source/model prose, mutate canonical records, or grant any
new authority.  The reason codes deliberately describe only recorded execution
and evidence conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionCaveat,
    ResearchEvidenceCompletionLimitation,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchMissionOutcome import ResearchMissionOutcome
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


class ResearchMissionGoalExplanationReason(StrEnum):
    """Bounded operator-facing reasons derived from canonical typed state."""

    SUPPORTED_CURRENT_EVIDENCE = "supported_current_evidence"
    MISSING_EVIDENCE = "missing_evidence"
    SOURCE_LIMITED = "source_limited"
    MISSING_CORROBORATION = "missing_corroboration"
    GROUNDING_INCOMPLETE = "grounding_incomplete"
    COMPARISON_UNAVAILABLE = "comparison_unavailable"
    RECORDED_CLAIM_CONFLICT = "recorded_claim_conflict"
    UNRESOLVED_TENTATIVE_CONTRADICTION = "unresolved_tentative_contradiction"
    TENTATIVE_CONFLICT_STRUCTURALLY_CLARIFIED = (
        "tentative_conflict_structurally_clarified"
    )
    CONTRADICTION_FOLLOWUP_CONFLICT = "contradiction_followup_conflict"
    CONTRADICTION_FOLLOWUP_NOT_COMPARABLE = "contradiction_followup_not_comparable"
    CONTRADICTION_FOLLOWUP_NO_SUPPORT = "contradiction_followup_no_supported_comparison"
    SOURCES_NOT_COMPARABLE = "sources_not_comparable"
    TENTATIVE_AGREEMENT_UNSUPPORTED = "tentative_agreement_unsupported"
    AGREEMENT_SUPPORTED_BY_REVIEW = "agreement_supported_by_review"
    COMPARISON_RELATION_UNRECORDED = "comparison_relation_unrecorded"
    NO_SUPPORTED_COMPARISON = "no_supported_comparison"
    NO_SUPPORTED_COMPARISON_AFTER_FOLLOWUP = "no_supported_comparison_after_followup"
    FOLLOWUP_COMPARISON_WITHOUT_INITIAL_SUPPORT = (
        "followup_comparison_without_initial_support"
    )
    EXECUTION_INCOMPLETE = "execution_incomplete"
    SCOPE_OR_AUTHORITY_BLOCKED = "scope_or_authority_blocked"
    EXECUTOR_REFUSED = "executor_refused"
    CUMULATIVE_BUDGET_EXHAUSTED = "cumulative_budget_exhausted"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_INTERRUPTED = "execution_interrupted"


_LIMITATION_REASONS = {
    ResearchEvidenceCompletionLimitation.MISSING_EVIDENCE: (
        ResearchMissionGoalExplanationReason.MISSING_EVIDENCE
    ),
    ResearchEvidenceCompletionLimitation.SOURCE_LIMITED: (
        ResearchMissionGoalExplanationReason.SOURCE_LIMITED
    ),
    ResearchEvidenceCompletionLimitation.MISSING_CORROBORATION: (
        ResearchMissionGoalExplanationReason.MISSING_CORROBORATION
    ),
    ResearchEvidenceCompletionLimitation.GROUNDING_INCOMPLETE: (
        ResearchMissionGoalExplanationReason.GROUNDING_INCOMPLETE
    ),
    ResearchEvidenceCompletionLimitation.COMPARISON_UNAVAILABLE: (
        ResearchMissionGoalExplanationReason.COMPARISON_UNAVAILABLE
    ),
    ResearchEvidenceCompletionLimitation.EXECUTION_INCOMPLETE: (
        ResearchMissionGoalExplanationReason.EXECUTION_INCOMPLETE
    ),
    ResearchEvidenceCompletionLimitation.RECORDED_CONFLICT: (
        ResearchMissionGoalExplanationReason.RECORDED_CLAIM_CONFLICT
    ),
}

_REASON_TEXT = {
    ResearchMissionGoalExplanationReason.SUPPORTED_CURRENT_EVIDENCE: (
        "Current retained evidence supports the bounded teaching deliverable"
    ),
    ResearchMissionGoalExplanationReason.MISSING_EVIDENCE: (
        "Recorded evidence is missing"
    ),
    ResearchMissionGoalExplanationReason.SOURCE_LIMITED: (
        "Too few accepted sources were retained"
    ),
    ResearchMissionGoalExplanationReason.MISSING_CORROBORATION: (
        "Evidence is not corroborated across retained sources"
    ),
    ResearchMissionGoalExplanationReason.GROUNDING_INCOMPLETE: (
        "Some evidence lacks a retained grounding assessment"
    ),
    ResearchMissionGoalExplanationReason.COMPARISON_UNAVAILABLE: (
        "No retained comparison is available"
    ),
    ResearchMissionGoalExplanationReason.RECORDED_CLAIM_CONFLICT: (
        "A canonical claim contradiction remains recorded"
    ),
    ResearchMissionGoalExplanationReason.UNRESOLVED_TENTATIVE_CONTRADICTION: (
        "The bounded tentative contradiction remains unresolved"
    ),
    ResearchMissionGoalExplanationReason.TENTATIVE_CONFLICT_STRUCTURALLY_CLARIFIED: (
        "A tentative conflict between the first two sources led to one follow-up "
        "comparison of the first source with a new source, which tentatively "
        "agreed; this clarifies the conflict structure but does not establish a "
        "verified resolution of the original disputed comparison or claim, and "
        "does not show either source wrong"
    ),
    ResearchMissionGoalExplanationReason.CONTRADICTION_FOLLOWUP_CONFLICT: (
        "The one authorized follow-up comparison with a new source also returned "
        "a tentative conflict; this neither resolves the contradiction nor shows "
        "either source wrong"
    ),
    ResearchMissionGoalExplanationReason.CONTRADICTION_FOLLOWUP_NOT_COMPARABLE: (
        "The one authorized follow-up comparison with a new source was judged not "
        "comparable, so it neither supports nor resolves the tentative "
        "contradiction"
    ),
    ResearchMissionGoalExplanationReason.CONTRADICTION_FOLLOWUP_NO_SUPPORT: (
        "The one authorized follow-up comparison with a new source returned no "
        "supported comparison, so the tentative contradiction is not resolved"
    ),
    ResearchMissionGoalExplanationReason.SOURCES_NOT_COMPARABLE: (
        "The selected sources were judged not comparable, so no supported "
        "comparison was established. That is a valid finding, not a supported "
        "comparison, and it does not satisfy a comparison goal"
    ),
    ResearchMissionGoalExplanationReason.TENTATIVE_AGREEMENT_UNSUPPORTED: (
        "The selected sources tentatively agree, but the available evidence does "
        "not establish a sufficiently supported comparison: the agreement is a "
        "tentative model interpretation and no retained record verifies it"
    ),
    ResearchMissionGoalExplanationReason.AGREEMENT_SUPPORTED_BY_REVIEW: (
        "The retained agreement comparison has an explicit operator comparison "
        "review marked supported, so the bounded comparison objective is met; that "
        "review is a recorded human judgement, not model output, and was not "
        "inferred from note text"
    ),
    ResearchMissionGoalExplanationReason.COMPARISON_RELATION_UNRECORDED: (
        "No durable comparison relation is recorded for this mission, so the "
        "retained comparison notes cannot establish a supported comparison"
    ),
    ResearchMissionGoalExplanationReason.NO_SUPPORTED_COMPARISON: (
        "The retained comparison established no supported comparison between "
        "the sources; the comparison gap remains"
    ),
    ResearchMissionGoalExplanationReason.NO_SUPPORTED_COMPARISON_AFTER_FOLLOWUP: (
        "No supported comparison was established: the initial comparison and the "
        "one authorized follow-up both returned none. This is a comparison gap, "
        "not an execution failure or missing evidence, and nothing was resolved "
        "or verified"
    ),
    ResearchMissionGoalExplanationReason.FOLLOWUP_COMPARISON_WITHOUT_INITIAL_SUPPORT: (
        "The initial comparison returned no supported comparison; the authorized "
        "follow-up produced a tentative comparison with one new source, but it "
        "does not establish the original comparison or resolve the original gap"
    ),
    ResearchMissionGoalExplanationReason.EXECUTION_INCOMPLETE: (
        "Execution stopped before the bounded work completed"
    ),
    ResearchMissionGoalExplanationReason.SCOPE_OR_AUTHORITY_BLOCKED: (
        "An existing scope or authority boundary blocked the next operation"
    ),
    ResearchMissionGoalExplanationReason.EXECUTOR_REFUSED: (
        "The canonical executor refused the next operation"
    ),
    ResearchMissionGoalExplanationReason.CUMULATIVE_BUDGET_EXHAUSTED: (
        "The mission's cumulative approved budget was exhausted"
    ),
    ResearchMissionGoalExplanationReason.EXECUTION_FAILED: "Execution failed",
    ResearchMissionGoalExplanationReason.EXECUTION_CANCELLED: "Execution was cancelled",
    ResearchMissionGoalExplanationReason.EXECUTION_INTERRUPTED: (
        "Execution was interrupted and was not replayed"
    ),
}

_CAVEAT_TEXT = {
    ResearchEvidenceCompletionCaveat.SOURCE_NOT_INDEPENDENT: (
        "at least one retained source was recorded as derivative or a likely "
        "duplicate, so corroboration may not be independent"
    ),
    ResearchEvidenceCompletionCaveat.SOURCE_INDEPENDENCE_UNVERIFIED: (
        "source independence was not established; corroboration independence "
        "remains unverified"
    ),
}

_LIMITATION_GUIDANCE = {
    ResearchEvidenceCompletionLimitation.MISSING_EVIDENCE: (
        "recording at least one relevant piece of evidence"
    ),
    ResearchEvidenceCompletionLimitation.SOURCE_LIMITED: (
        "accepting at least one additional source"
    ),
    ResearchEvidenceCompletionLimitation.MISSING_CORROBORATION: (
        "evidence from a second, distinct source"
    ),
    ResearchEvidenceCompletionLimitation.GROUNDING_INCOMPLETE: (
        "a retained grounding assessment for the currently ungrounded evidence"
    ),
    ResearchEvidenceCompletionLimitation.COMPARISON_UNAVAILABLE: (
        "a retained comparison note between the sources"
    ),
    ResearchEvidenceCompletionLimitation.BUDGET_LIMITED: (
        "additional approved budget to continue the bounded execution"
    ),
    ResearchEvidenceCompletionLimitation.EXECUTION_INCOMPLETE: (
        "completing the blocked, interrupted, or refused step"
    ),
    ResearchEvidenceCompletionLimitation.RECORDED_CONFLICT: (
        "resolving or reviewing the recorded claim contradiction"
    ),
}


@dataclass(frozen=True, slots=True)
class ResearchMissionGoalExplanation:
    """Non-authoritative explanation of coverage, gaps and stopping reasons."""

    status: ResearchMissionGoalSatisfactionStatus
    stop_reason: AutonomyStopReason
    source_count: int
    evidence_count: int
    evidence_source_count: int
    reasons: tuple[ResearchMissionGoalExplanationReason, ...]
    caveats: tuple[ResearchEvidenceCompletionCaveat, ...] = ()
    limitations: tuple[ResearchEvidenceCompletionLimitation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ResearchMissionGoalSatisfactionStatus):
            raise ResearchError("Research mission goal explanation status is invalid.")
        if not isinstance(self.stop_reason, AutonomyStopReason):
            raise ResearchError(
                "Research mission goal explanation stop reason is invalid."
            )
        for value, label in (
            (self.source_count, "source count"),
            (self.evidence_count, "evidence count"),
            (self.evidence_source_count, "evidence source count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(
                    f"Research mission goal explanation {label} is invalid."
                )
        if (
            not isinstance(self.reasons, tuple)
            or not self.reasons
            or not all(
                isinstance(reason, ResearchMissionGoalExplanationReason)
                for reason in self.reasons
            )
            or len(self.reasons) != len(set(self.reasons))
        ):
            raise ResearchError(
                "Research mission goal explanation reasons are invalid."
            )
        if (
            not isinstance(self.caveats, tuple)
            or not all(
                isinstance(caveat, ResearchEvidenceCompletionCaveat)
                for caveat in self.caveats
            )
            or len(self.caveats) != len(set(self.caveats))
        ):
            raise ResearchError(
                "Research mission goal explanation caveats are invalid."
            )
        if (
            not isinstance(self.limitations, tuple)
            or not all(
                isinstance(limitation, ResearchEvidenceCompletionLimitation)
                for limitation in self.limitations
            )
            or len(self.limitations) != len(set(self.limitations))
        ):
            raise ResearchError(
                "Research mission goal explanation limitations are invalid."
            )

    def summary(self) -> str:
        """Render bounded wording from typed state, never source/model prose."""
        reasons = "; ".join(_REASON_TEXT[reason] for reason in self.reasons)
        rendered = (
            "Goal-satisfaction explanation: "
            f"Goal status: {self.status.value.replace('_', ' ')}. "
            "Recorded coverage, not factual completeness: "
            f"{self.source_count} accepted source(s), {self.evidence_count} "
            f"evidence record(s) from {self.evidence_source_count} source(s). "
            f"Why the mission stopped or remains limited: {reasons}."
        )
        if self.caveats:
            caveats = "; ".join(_CAVEAT_TEXT[caveat] for caveat in self.caveats)
            rendered += f" Caveat (secondary; does not change goal status): {caveats}."
        if self.limitations:
            guidance = "; ".join(
                _LIMITATION_GUIDANCE[limitation] for limitation in self.limitations
            )
            rendered += (
                " What would help close this gap (explanatory only; not a "
                f"pending action or a grant of budget/authority): {guidance}."
            )
        return rendered


def explain_mission_goal_satisfaction(
    outcome: ResearchMissionOutcome,
    stop_reason: AutonomyStopReason | str,
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> ResearchMissionGoalExplanation:
    """Project typed mission state into a deterministic bounded explanation."""
    if not isinstance(outcome, ResearchMissionOutcome):
        raise ResearchError(
            "Research mission goal explanation requires a mission outcome."
        )
    if isinstance(stop_reason, AutonomyStopReason):
        normalized_stop = stop_reason
    elif isinstance(stop_reason, str) and stop_reason.strip():
        try:
            normalized_stop = AutonomyStopReason(stop_reason.strip())
        except ValueError as error:
            raise ResearchError(
                "Research mission goal explanation stop reason is invalid."
            ) from error
    else:
        raise ResearchError("Research mission goal explanation stop reason is invalid.")
    if checkpoint is not None and not isinstance(
        checkpoint, ResearchMissionRecoveryCheckpoint
    ):
        raise ResearchError("Research mission goal explanation checkpoint is invalid.")

    satisfaction = outcome.goal_satisfaction
    evaluation = outcome.evidence_evaluation
    if satisfaction.evidence_status is not evaluation.status:
        raise ResearchError(
            "Research mission goal explanation evidence state mismatches."
        )
    if satisfaction.execution_outcome is not outcome.execution_outcome:
        raise ResearchError(
            "Research mission goal explanation execution state mismatches."
        )
    if checkpoint is not None and (
        satisfaction.contradiction_outcome != checkpoint.contradiction_outcome
    ):
        raise ResearchError(
            "Research mission goal explanation contradiction state mismatches."
        )

    reasons: list[ResearchMissionGoalExplanationReason] = []
    if satisfaction.status is ResearchMissionGoalSatisfactionStatus.SATISFIED:
        reasons.append(ResearchMissionGoalExplanationReason.SUPPORTED_CURRENT_EVIDENCE)
    for limitation in evaluation.limitations:
        reason = _LIMITATION_REASONS.get(limitation)
        if reason is not None:
            reasons.append(reason)
    if checkpoint is not None and (
        (
            checkpoint.contradiction_initial_relation == "possible_conflict"
            and checkpoint.contradiction_outcome != "structurally_clarified"
        )
        or (
            # A legacy checkpoint records the conflict only here.
            checkpoint.semantic_relation == "possible_conflict"
            and not checkpoint.contradiction_initial_relation
        )
    ):
        reasons.append(
            ResearchMissionGoalExplanationReason.UNRESOLVED_TENTATIVE_CONTRADICTION
        )
        # Name what the durable follow-up relation actually was, so an
        # unresolved contradiction is not read as a repeated conflict alone.
        followup_reason = {
            "possible_conflict": (
                ResearchMissionGoalExplanationReason.CONTRADICTION_FOLLOWUP_CONFLICT
            ),
            "not_comparable": (
                ResearchMissionGoalExplanationReason.CONTRADICTION_FOLLOWUP_NOT_COMPARABLE
            ),
            "no_supported_comparison": (
                ResearchMissionGoalExplanationReason.CONTRADICTION_FOLLOWUP_NO_SUPPORT
            ),
        }.get(checkpoint.contradiction_followup_relation)
        if (
            checkpoint.contradiction_outcome == "unresolved"
            and followup_reason is not None
        ):
            reasons.append(followup_reason)
    elif checkpoint is not None and (
        checkpoint.semantic_relation == "not_comparable"
        and not checkpoint.contradiction_initial_relation
    ):
        reasons.append(ResearchMissionGoalExplanationReason.SOURCES_NOT_COMPARABLE)
    elif checkpoint is not None and (
        checkpoint.semantic_relation == "possible_agreement"
        and not checkpoint.contradiction_initial_relation
    ):
        reasons.append(
            ResearchMissionGoalExplanationReason.AGREEMENT_SUPPORTED_BY_REVIEW
            if satisfaction.supported_by_review_id
            and satisfaction.status is ResearchMissionGoalSatisfactionStatus.SATISFIED
            else ResearchMissionGoalExplanationReason.TENTATIVE_AGREEMENT_UNSUPPORTED
        )
    elif (
        checkpoint is not None
        and not checkpoint.semantic_relation
        and evaluation.comparison_note_count > 0
    ):
        reasons.append(
            ResearchMissionGoalExplanationReason.COMPARISON_RELATION_UNRECORDED
        )
    elif checkpoint is not None and (
        checkpoint.contradiction_initial_relation == "possible_conflict"
        and checkpoint.contradiction_outcome == "structurally_clarified"
    ):
        # The goal stays unresolved: the follow-up clarified structure; it did
        # not verify a resolution of the original pair.
        reasons.append(
            ResearchMissionGoalExplanationReason.TENTATIVE_CONFLICT_STRUCTURALLY_CLARIFIED
        )
    elif checkpoint is not None and (
        checkpoint.semantic_relation == "no_supported_comparison"
        and not checkpoint.contradiction_initial_relation
    ):
        reasons.append(
            {
                "no_supported_comparison": (
                    ResearchMissionGoalExplanationReason.NO_SUPPORTED_COMPARISON_AFTER_FOLLOWUP
                ),
                "followup_comparison_recorded": (
                    ResearchMissionGoalExplanationReason.FOLLOWUP_COMPARISON_WITHOUT_INITIAL_SUPPORT
                ),
            }.get(
                checkpoint.evidence_gap_outcome,
                ResearchMissionGoalExplanationReason.NO_SUPPORTED_COMPARISON,
            )
        )

    if satisfaction.status is ResearchMissionGoalSatisfactionStatus.BUDGET_LIMITED:
        reasons.append(ResearchMissionGoalExplanationReason.CUMULATIVE_BUDGET_EXHAUSTED)
    elif satisfaction.status is ResearchMissionGoalSatisfactionStatus.BLOCKED:
        if normalized_stop is AutonomyStopReason.STEP_BLOCKED:
            reasons.append(
                ResearchMissionGoalExplanationReason.SCOPE_OR_AUTHORITY_BLOCKED
            )
        else:
            reasons.append(ResearchMissionGoalExplanationReason.EXECUTOR_REFUSED)
    elif satisfaction.status is ResearchMissionGoalSatisfactionStatus.FAILED:
        reasons.append(ResearchMissionGoalExplanationReason.EXECUTION_FAILED)
    elif satisfaction.status is ResearchMissionGoalSatisfactionStatus.CANCELLED:
        reasons.append(ResearchMissionGoalExplanationReason.EXECUTION_CANCELLED)
    elif normalized_stop is AutonomyStopReason.STEP_INTERRUPTED:
        reasons.append(ResearchMissionGoalExplanationReason.EXECUTION_INTERRUPTED)

    if not reasons:
        reasons.append(ResearchMissionGoalExplanationReason.EXECUTION_INCOMPLETE)
    return ResearchMissionGoalExplanation(
        status=satisfaction.status,
        stop_reason=normalized_stop,
        source_count=evaluation.source_count,
        evidence_count=evaluation.evidence_count,
        evidence_source_count=evaluation.evidence_source_count,
        reasons=tuple(dict.fromkeys(reasons)),
        caveats=evaluation.caveats,
        limitations=evaluation.limitations,
    )
