"""Exact typed desktop handoff of a recorded-candidate acquisition preview."""

from dataclasses import dataclass

from research.ResearchAcquisitionBatchDraft import preview_acquisition_batch
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRun import ResearchRun


@dataclass(frozen=True, slots=True)
class AcquisitionResearchDraft:
    run: ResearchRun
    discovery_id: str
    selected_urls: tuple[str, ...]
    plan: ResearchPlan

    def __post_init__(self) -> None:
        expected = preview_acquisition_batch(
            self.run, self.discovery_id, self.selected_urls
        ).plan
        if (
            expected is None
            or not isinstance(self.plan, ResearchPlan)
            or plan_digest(expected) != plan_digest(self.plan)
        ):
            raise ValueError(
                "Acquisition preview no longer matches the recorded selection."
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
            raise ValueError("Acquisition fields changed. Review a new batch.")
        return {
            "research_plan_steps": tuple(
                ResearchPlanStepDraftInput(
                    instruction=step.instruction,
                    capability=step.capability.value,
                    authorized_source_url=step.authorized_source_url,
                )
                for step in self.plan.steps
            )
        }
