"""Exact typed desktop handoff of a recorded-observation revalidation preview."""

from dataclasses import dataclass

from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRevalidationDraft import preview_source_revalidation
from research.ResearchRun import ResearchRun


@dataclass(frozen=True, slots=True)
class RevalidationResearchDraft:
    run: ResearchRun
    prior_observation_id: str
    plan: ResearchPlan

    def __post_init__(self) -> None:
        expected = preview_source_revalidation(self.run, self.prior_observation_id).plan
        if (
            expected is None
            or not isinstance(self.plan, ResearchPlan)
            or plan_digest(expected) != plan_digest(self.plan)
        ):
            raise ValueError(
                "Revalidation preview no longer matches the recorded selection."
            )

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
            raise ValueError("Revalidation fields changed. Review a new proposal.")
        return {
            "research_plan_steps": tuple(
                ResearchPlanStepDraftInput(
                    instruction=step.instruction,
                    capability=step.capability.value,
                    source_revalidation_binding=step.source_revalidation_binding,
                )
                for step in self.plan.steps
            )
        }
