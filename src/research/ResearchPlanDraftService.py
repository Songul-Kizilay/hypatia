"""Pure no-write construction of explicit user-authored Research plan drafts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput

ResearchPlanStepDraft = ResearchPlanStepDraftInput | tuple[object, ...]


class ResearchPlanDraftService:
    """Validate explicit draft inputs without persistence or execution."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def preview(
        self,
        question: str,
        step_drafts: tuple[ResearchPlanStepDraft, ...],
    ) -> ResearchPlanDraftPreview:
        """Return a complete inert plan or one bounded validation failure."""
        try:
            steps = self._build_steps(step_drafts)
            plan = ResearchPlan(
                plan_id=self._id_factory(),
                question=question,
                steps=steps,
                created_at=self._clock(),
            )
        except ResearchError as error:
            return ResearchPlanDraftPreview.rejected(str(error))
        return ResearchPlanDraftPreview.ready(plan)

    @staticmethod
    def _build_steps(
        step_drafts: tuple[ResearchPlanStepDraft, ...],
    ) -> tuple[ResearchPlanStep, ...]:
        if not isinstance(step_drafts, tuple):
            raise ResearchError("Research plan draft steps must be an immutable tuple.")
        steps: list[ResearchPlanStep] = []
        for index, draft in enumerate(step_drafts, start=1):
            normalized = ResearchPlanStepDraftInput.from_value(draft)
            steps.append(
                ResearchPlanStep(
                    step_id=f"step-{index}",
                    instruction=normalized.instruction,
                    selected_source_document_ids=(
                        normalized.selected_source_document_ids
                    ),
                    capability=ResearchPlanDraftService._capability(
                        normalized.capability
                    ),
                    authorized_source_url=normalized.authorized_source_url,
                    evidence_authorization=normalized.evidence_authorization,
                    assessment_authorization=normalized.assessment_authorization,
                    claim_authorization=normalized.claim_authorization,
                )
            )
        return tuple(steps)

    @staticmethod
    def _capability(value: object) -> ResearchPlanStepCapability:
        """Resolve one explicit capability name without guessing from text."""
        if value is None:
            return ResearchPlanStepCapability.NONE
        if not isinstance(value, str):
            raise ResearchError("Research plan step capability must be text.")
        try:
            return ResearchPlanStepCapability(value)
        except ValueError as error:
            raise ResearchError(
                "Research plan step capability is not recognized."
            ) from error
