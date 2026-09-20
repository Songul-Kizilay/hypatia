"""A typed, non-authoritative proposal to continue one unresolved mission.

`ResearchMissionOutcome` can already say a bounded mission's goal is
`unresolved` or only `partially_satisfied`.  This module turns exactly that
evidence-grounded fact into a citation and a question — nothing else.  A
`ResearchMissionContinuationProposal` carries no budget, no scope, no target,
no discovery provider and no plan step: the absence of those fields is the
structural guarantee that this type cannot widen authority, not a runtime
check layered on top of one that could.  It cites the run and plan digest it
came from, states the evidence and stop-reason snapshot that explains why it
was proposed, and repeats the run's own question verbatim.  Building one for
any other goal-satisfaction status is not merely discouraged, it is
impossible: `__post_init__` rejects it.  Nothing here executes, fetches,
calls a model or provider, spends, authorizes or persists anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionLimitation,
    ResearchEvidenceCompletionStatus,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchMissionOutcome import ResearchMissionOutcome
from research.ResearchPlanDigest import is_plan_digest
from research.ResearchRun import ResearchRun

#: The two `ResearchMissionGoalSatisfactionStatus` values from which a
#: continuation may ever be proposed.  Every other status — `satisfied`,
#: `blocked`, `budget_limited`, `failed`, `cancelled` — is explicitly
#: ineligible for v1 and cannot construct a proposal.
_ELIGIBLE_GOAL_STATUSES = frozenset(
    {
        ResearchMissionGoalSatisfactionStatus.UNRESOLVED,
        ResearchMissionGoalSatisfactionStatus.PARTIALLY_SATISFIED,
    }
)

#: Mirrors the maximum length `ResearchRun` already enforces on `question`,
#: so a proposal's seed question can never exceed what a fresh plan preview
#: would itself accept.
_MAX_SEED_QUESTION_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchMissionContinuationProposal:
    """Cite one unresolved mission's evidence state; author nothing new."""

    proposal_id: str
    origin_run_id: str
    origin_plan_digest: str
    origin_stop_reason: AutonomyStopReason
    origin_goal_status: ResearchMissionGoalSatisfactionStatus
    origin_evidence_status: ResearchEvidenceCompletionStatus
    origin_evidence_limitations: tuple[ResearchEvidenceCompletionLimitation, ...]
    seed_question: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise ResearchError("Mission continuation proposal ID cannot be empty.")
        if not isinstance(self.origin_run_id, str) or not self.origin_run_id.strip():
            raise ResearchError("Mission continuation origin run ID cannot be empty.")
        if not is_plan_digest(self.origin_plan_digest):
            raise ResearchError("Mission continuation origin plan digest is invalid.")
        if not isinstance(self.origin_stop_reason, AutonomyStopReason):
            raise ResearchError("Mission continuation origin stop reason is invalid.")
        if (
            not isinstance(
                self.origin_goal_status, ResearchMissionGoalSatisfactionStatus
            )
            or self.origin_goal_status not in _ELIGIBLE_GOAL_STATUSES
        ):
            raise ResearchError(
                "Mission continuation is only proposable from an unresolved or "
                "partially satisfied mission goal."
            )
        if not isinstance(
            self.origin_evidence_status, ResearchEvidenceCompletionStatus
        ):
            raise ResearchError(
                "Mission continuation origin evidence status is invalid."
            )
        if not isinstance(self.origin_evidence_limitations, tuple) or not all(
            isinstance(value, ResearchEvidenceCompletionLimitation)
            for value in self.origin_evidence_limitations
        ):
            raise ResearchError(
                "Mission continuation origin evidence limitations are invalid."
            )
        if (
            not isinstance(self.seed_question, str)
            or not self.seed_question.strip()
            or self.seed_question != self.seed_question.strip()
        ):
            raise ResearchError(
                "Mission continuation seed question cannot be empty or padded "
                "with whitespace."
            )
        if len(self.seed_question) > _MAX_SEED_QUESTION_CHARACTERS:
            raise ResearchError("Mission continuation seed question is too long.")
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
        ):
            raise ResearchError(
                "Mission continuation generation time must be timezone-aware."
            )
        if self.generated_at > datetime.now(UTC):
            raise ResearchError(
                "Mission continuation cannot be generated in the future."
            )


def continuation_eligible(status: ResearchMissionGoalSatisfactionStatus) -> bool:
    """Return whether this goal-satisfaction status may ever propose one."""
    return status in _ELIGIBLE_GOAL_STATUSES


def continuation_proposal_for(
    run: ResearchRun,
    outcome: ResearchMissionOutcome,
    origin_plan_digest: str,
    stop_reason: AutonomyStopReason,
    generated_at: datetime | None = None,
) -> ResearchMissionContinuationProposal | None:
    """Derive a continuation proposal from already-canonical mission state.

    A pure function with no network, model or store side effects.  Returns
    ``None`` immediately for every ineligible goal-satisfaction status,
    matching `continuation_eligible`.  ``stop_reason`` is accepted explicitly
    rather than read off ``outcome`` because `ResearchMissionOutcome` retains
    only the derived `BackgroundTaskOutcome`, not the original
    `AutonomyStopReason` a caller already holds; the caller must pass the
    same stop reason it gave `mission_outcome_for` to produce ``outcome``.
    ``seed_question`` always comes from ``run.question`` verbatim — there is
    no parameter to override it.
    """
    if not isinstance(run, ResearchRun):
        raise ResearchError("Mission continuation proposal requires a research run.")
    if not isinstance(outcome, ResearchMissionOutcome):
        raise ResearchError(
            "Mission continuation proposal requires a research mission outcome."
        )
    if not continuation_eligible(outcome.goal_satisfaction.status):
        return None
    return ResearchMissionContinuationProposal(
        proposal_id=str(uuid4()),
        origin_run_id=run.run_id,
        origin_plan_digest=origin_plan_digest,
        origin_stop_reason=stop_reason,
        origin_goal_status=outcome.goal_satisfaction.status,
        origin_evidence_status=outcome.evidence_evaluation.status,
        origin_evidence_limitations=outcome.evidence_evaluation.limitations,
        seed_question=run.question,
        generated_at=generated_at if generated_at is not None else datetime.now(UTC),
    )
