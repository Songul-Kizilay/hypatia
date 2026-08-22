"""One bounded user-authored step in an inert Research plan.

The authored instruction is descriptive text for a human reader. It never
selects an executable capability. ``capability`` is the separate explicit
authorization, defaulting to none so an unauthorized step cannot run anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_RESEARCH_PLAN_STEP_ID_CHARACTERS = 200
MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS = 2_000
MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES = 20
MAX_RESEARCH_PLAN_SOURCE_DOCUMENT_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class ResearchPlanStep:
    """Keep one explicit instruction and its exact user-selected sources."""

    step_id: str
    instruction: str
    selected_source_document_ids: tuple[str, ...] = ()
    capability: ResearchPlanStepCapability = ResearchPlanStepCapability.NONE

    def __post_init__(self) -> None:
        step_id = self._normalize_bounded_text(
            self.step_id,
            "Research plan step ID",
            MAX_RESEARCH_PLAN_STEP_ID_CHARACTERS,
        )
        instruction = self._normalize_bounded_text(
            self.instruction,
            "Research plan step instruction",
            MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS,
        )
        if not isinstance(self.capability, ResearchPlanStepCapability):
            raise ResearchError("Research plan step capability is invalid.")
        source_ids = self.selected_source_document_ids
        if not isinstance(source_ids, tuple):
            raise ResearchError(
                "Research plan selected source IDs must be an immutable tuple."
            )
        if len(source_ids) > MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES:
            raise ResearchError("Research plan step has too many selected sources.")
        normalized_source_ids = tuple(
            self._normalize_bounded_text(
                source_id,
                "Research plan selected source document ID",
                MAX_RESEARCH_PLAN_SOURCE_DOCUMENT_ID_CHARACTERS,
            )
            for source_id in source_ids
        )
        if len(normalized_source_ids) != len(set(normalized_source_ids)):
            raise ResearchError(
                "Research plan step contains duplicate selected sources."
            )
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "instruction", instruction)
        object.__setattr__(
            self,
            "selected_source_document_ids",
            normalized_source_ids,
        )

    @staticmethod
    def _normalize_bounded_text(value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        normalized = value.strip()
        if len(normalized) > maximum:
            raise ResearchError(f"{label} is too long.")
        return normalized
