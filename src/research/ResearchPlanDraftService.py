"""Pure no-write construction of explicit user-authored Research plan drafts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanConstraint import ResearchPlanConstraint
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding

ResearchPlanStepDraft = ResearchPlanStepDraftInput | tuple[object, ...]

#: The metadata key carrying authored constraints. Named once so every
#: place that rebuilds a plan reads the same field: a rebuild that missed
#: it would silently produce a different, constraint-free plan, and the
#: approval would bind a digest for something the operator never saw.
RESEARCH_PLAN_CONSTRAINTS_KEY = "research_plan_constraints"

#: The metadata key carrying the operator's typed restriction selection.
#: Separate from the constraint text on purpose: the text is never read to
#: decide whether anything is enforced.
RESEARCH_PLAN_RESTRICTION_KEY = "research_plan_restriction"
RESEARCH_PLAN_TARGET_BINDING_KEY = "research_plan_target_binding"


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
        constraint_drafts: tuple[str, ...] = (),
        restriction: ResearchPlanRestriction | None = None,
        target_binding: ResearchPlanTargetBinding | None = None,
    ) -> ResearchPlanDraftPreview:
        """Return a complete inert plan or one bounded validation failure.

        Steps and constraints arrive already separated, because the author
        decided which is which. Nothing here reads the text to guess, and the
        restriction is a value the operator selected rather than anything
        inferred from what a constraint happens to say.
        """
        try:
            steps = self._build_steps(step_drafts)
            constraints = self._build_constraints(constraint_drafts, restriction)
            plan = ResearchPlan(
                plan_id=self._id_factory(),
                question=question,
                steps=steps,
                created_at=self._clock(),
                constraints=constraints,
                target_binding=target_binding,
            )
        except ResearchError as error:
            return ResearchPlanDraftPreview.rejected(str(error))
        return ResearchPlanDraftPreview.ready(plan)

    def preview_question(
        self, question: str, provider: str
    ) -> ResearchPlanDraftPreview:
        """Draft a fixed research opening; question prose cannot add capabilities."""
        try:
            selected = self._provider(provider)
            if selected is None:
                raise ResearchError("Choose a research discovery provider.")
        except ResearchError as error:
            return ResearchPlanDraftPreview.rejected(str(error))
        return self.preview(
            question,
            (
                ResearchPlanStepDraftInput(
                    instruction=question,
                    capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH.value,
                ),
                ResearchPlanStepDraftInput(
                    instruction="Discover candidate sources for the research question.",
                    capability=ResearchPlanStepCapability.SOURCE_DISCOVERY.value,
                    discovery_provider=selected.value,
                ),
            ),
        )

    @staticmethod
    def _build_constraints(
        constraint_drafts: tuple[str, ...],
        restriction: ResearchPlanRestriction | None = None,
    ) -> tuple[ResearchPlanConstraint, ...]:
        """Preserve exact authored text, in order, with the chosen restriction.

        The restriction is applied as given. No line is read to decide whether
        it deserves one.
        """
        if not isinstance(constraint_drafts, tuple):
            raise ResearchError(
                "Research plan draft constraints must be an immutable tuple."
            )
        return tuple(
            ResearchPlanConstraint(text=cast(str, draft), restriction=restriction)
            for draft in constraint_drafts
        )

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
                    discovery_provider=ResearchPlanDraftService._provider(
                        normalized.discovery_provider
                    ),
                    evidence_authorization=normalized.evidence_authorization,
                    assessment_authorization=normalized.assessment_authorization,
                    claim_authorization=normalized.claim_authorization,
                    contradiction_authorization=(
                        normalized.contradiction_authorization
                    ),
                    comparison_authorization=(normalized.comparison_authorization),
                    completion_authorization=(normalized.completion_authorization),
                    semantic_evidence_binding=normalized.semantic_evidence_binding,
                    semantic_comparison_binding=normalized.semantic_comparison_binding,
                    source_revalidation_binding=(
                        normalized.source_revalidation_binding
                    ),
                )
            )
        return tuple(steps)

    @staticmethod
    def _provider(value: object) -> ResearchDiscoveryProviderName | None:
        """Resolve one named provider from a closed vocabulary, or nothing.

        Never a URL and never free text. Provider choice decides which host the
        approved step will contact, so an unrecognised name is refused rather
        than defaulted — silently falling back to a provider the operator did
        not choose would authorize a network target nobody approved.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ResearchError("Research plan discovery provider must be text.")
        try:
            return ResearchDiscoveryProviderName(value)
        except ValueError as error:
            raise ResearchError(
                "Research plan discovery provider is not a known provider."
            ) from error

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
