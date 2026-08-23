"""One bounded user-authored step in an inert Research plan.

The authored instruction is descriptive text for a human reader. It never
selects an executable capability. ``capability`` is the separate explicit
authorization, defaulting to none so an unauthorized step cannot run anything.

``authorized_source_url`` is the one exact source this step may acquire. It is
empty by default, is never inferred from instruction text, and is never taken
from a discovery result, so no step can fetch a source nobody authorized.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssessmentAuthorization import (
    ResearchAssessmentAuthorization,
)
from research.ResearchClaimAuthorization import ResearchClaimAuthorization
from research.ResearchComparisonAuthorization import (
    ResearchComparisonAuthorization,
)
from research.ResearchCompletionAuthorization import (
    ResearchCompletionAuthorization,
)
from research.ResearchContradictionAuthorization import (
    ResearchContradictionAuthorization,
)
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_RESEARCH_PLAN_STEP_ID_CHARACTERS = 200
MAX_RESEARCH_PLAN_STEP_INSTRUCTION_CHARACTERS = 2_000
MAX_RESEARCH_PLAN_STEP_SELECTED_SOURCES = 20
MAX_RESEARCH_PLAN_SOURCE_DOCUMENT_ID_CHARACTERS = 200
MAX_RESEARCH_PLAN_AUTHORIZED_URL_CHARACTERS = 2_048


@dataclass(frozen=True, slots=True)
class ResearchPlanStep:
    """Keep one explicit instruction and its exact user-selected sources."""

    step_id: str
    instruction: str
    selected_source_document_ids: tuple[str, ...] = ()
    capability: ResearchPlanStepCapability = ResearchPlanStepCapability.NONE
    authorized_source_url: str = ""
    evidence_authorization: ResearchEvidenceAuthorization | None = None
    assessment_authorization: ResearchAssessmentAuthorization | None = None
    claim_authorization: ResearchClaimAuthorization | None = None
    contradiction_authorization: ResearchContradictionAuthorization | None = None
    comparison_authorization: ResearchComparisonAuthorization | None = None
    completion_authorization: ResearchCompletionAuthorization | None = None

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
        if self.evidence_authorization is not None and not isinstance(
            self.evidence_authorization, ResearchEvidenceAuthorization
        ):
            raise ResearchError("Research plan evidence authorization is invalid.")
        if self.assessment_authorization is not None and not isinstance(
            self.assessment_authorization, ResearchAssessmentAuthorization
        ):
            raise ResearchError("Research plan assessment authorization is invalid.")
        if self.claim_authorization is not None and not isinstance(
            self.claim_authorization, ResearchClaimAuthorization
        ):
            raise ResearchError("Research plan claim authorization is invalid.")
        if self.contradiction_authorization is not None and not isinstance(
            self.contradiction_authorization, ResearchContradictionAuthorization
        ):
            raise ResearchError("Research plan contradiction authorization is invalid.")
        if self.comparison_authorization is not None and not isinstance(
            self.comparison_authorization, ResearchComparisonAuthorization
        ):
            raise ResearchError("Research plan comparison authorization is invalid.")
        if self.completion_authorization is not None and not isinstance(
            self.completion_authorization, ResearchCompletionAuthorization
        ):
            raise ResearchError("Research plan completion authorization is invalid.")
        if not isinstance(self.authorized_source_url, str):
            raise ResearchError("Research plan authorized source URL must be text.")
        authorized_source_url = self.authorized_source_url.strip()
        if len(authorized_source_url) > MAX_RESEARCH_PLAN_AUTHORIZED_URL_CHARACTERS:
            raise ResearchError("Research plan authorized source URL is too long.")
        if any(
            character in authorized_source_url
            for character in (chr(13), chr(10), chr(9))
        ):
            raise ResearchError("Research plan authorized source URL is invalid.")
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
            "authorized_source_url",
            authorized_source_url,
        )
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
