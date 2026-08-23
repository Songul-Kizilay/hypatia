"""Pure no-write construction of explicit user-authored Research plan drafts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

ResearchPlanStepDraft = (
    tuple[str, tuple[str, ...]]
    | tuple[str, tuple[str, ...], str]
    | tuple[str, tuple[str, ...], str, str]
    | tuple[str, tuple[str, ...], str, str, tuple[str, int, str]]
)


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
            if not isinstance(draft, tuple) or len(draft) not in (2, 3, 4, 5):
                raise ResearchError("Research plan draft step is invalid.")
            capability = ResearchPlanDraftService._capability(
                draft[2] if len(draft) >= 3 else None
            )
            authorized_source_url = draft[3] if len(draft) >= 4 else ""
            evidence_authorization = ResearchPlanDraftService._evidence_authorization(
                draft[4] if len(draft) == 5 else None
            )
            if not isinstance(authorized_source_url, str):
                raise ResearchError("Research plan authorized source URL must be text.")
            steps.append(
                ResearchPlanStep(
                    step_id=f"step-{index}",
                    instruction=draft[0],
                    selected_source_document_ids=draft[1],
                    capability=capability,
                    authorized_source_url=authorized_source_url,
                    evidence_authorization=evidence_authorization,
                )
            )
        return tuple(steps)

    @staticmethod
    def _evidence_authorization(
        value: object,
    ) -> ResearchEvidenceAuthorization | None:
        """Build one explicit evidence authorization without inferring it."""
        if value is None:
            return None
        if not isinstance(value, tuple) or len(value) != 3:
            raise ResearchError("Research plan evidence authorization is invalid.")
        document_id, chunk_index, note = value
        return ResearchEvidenceAuthorization(
            document_id=document_id,
            chunk_index=chunk_index,
            note=note,
        )

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
