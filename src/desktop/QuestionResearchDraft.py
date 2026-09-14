"""Presentation-only handoff of an exact question-opening preview."""

from __future__ import annotations

from dataclasses import dataclass

from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput


@dataclass(frozen=True, slots=True)
class QuestionResearchDraft:
    """Keep typed steps intact; never reconstruct capabilities from display text."""

    plan: ResearchPlan

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ResearchPlan) or len(self.plan.steps) != 2:
            raise ValueError("An opening requires the exact two-step preview.")
        provider = self.plan.steps[1].discovery_provider
        if provider is None:
            raise ValueError("An opening requires an explicit discovery provider.")
        expected = (
            ResearchPlanDraftService()
            .preview_question(self.plan.question, provider.value)
            .plan
        )
        if expected is None or plan_digest(expected) != plan_digest(self.plan):
            raise ValueError("The opening no longer matches its canonical template.")

    @property
    def instruction_text(self) -> str:
        return "\n".join(step.instruction for step in self.plan.steps)

    def metadata(
        self, question: str, instructions: str, sources: str
    ) -> dict[str, object]:
        if (
            question.strip() != self.plan.question
            or instructions != self.instruction_text
            or sources.strip()
        ):
            raise ValueError(
                "Opening fields changed. Prepare and select a new preview."
            )
        return {
            "research_plan_steps": tuple(
                ResearchPlanStepDraftInput(
                    instruction=step.instruction,
                    capability=step.capability.value,
                    discovery_provider=(
                        step.discovery_provider.value
                        if step.discovery_provider is not None
                        else None
                    ),
                )
                for step in self.plan.steps
            )
        }
