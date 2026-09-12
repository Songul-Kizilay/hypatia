"""One bounded user-authored step in an inert Research plan.

The authored instruction is descriptive text for a human reader. It never
selects an executable capability. ``capability`` is the separate explicit
authorization, defaulting to none so an unauthorized step cannot run anything.

``authorized_source_url`` is the one exact source this step may acquire. It is
empty by default and never inferred from instruction text. A digest-bound
reference mission may resolve it from its own provider observation under its
original scope; ordinary manual plans still require the exact authored URL.
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
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.SemanticComparisonStepBinding import SemanticComparisonStepBinding
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding

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
    discovery_provider: ResearchDiscoveryProviderName | None = None
    evidence_authorization: ResearchEvidenceAuthorization | None = None
    assessment_authorization: ResearchAssessmentAuthorization | None = None
    claim_authorization: ResearchClaimAuthorization | None = None
    contradiction_authorization: ResearchContradictionAuthorization | None = None
    comparison_authorization: ResearchComparisonAuthorization | None = None
    completion_authorization: ResearchCompletionAuthorization | None = None
    semantic_evidence_binding: SemanticEvidenceStepBinding | None = None
    semantic_comparison_binding: SemanticComparisonStepBinding | None = None

    def __post_init__(self) -> None:
        if self.capability is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_COMPARISON:
            if not isinstance(
                self.semantic_comparison_binding, SemanticComparisonStepBinding
            ):
                raise ResearchError(
                    "Semantic comparison requires an exact pair binding."
                )
            if (
                self.selected_source_document_ids
                or self.authorized_source_url
                or any(
                    v is not None
                    for v in (
                        self.evidence_authorization,
                        self.assessment_authorization,
                        self.claim_authorization,
                        self.contradiction_authorization,
                        self.comparison_authorization,
                        self.completion_authorization,
                        self.discovery_provider,
                        self.semantic_evidence_binding,
                    )
                )
            ):
                raise ResearchError("Semantic comparison cannot carry other authority.")
        elif self.semantic_comparison_binding is not None:
            raise ResearchError("Only semantic comparison may carry a pair binding.")
        if self.capability is ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL:
            if not isinstance(
                self.semantic_evidence_binding, SemanticEvidenceStepBinding
            ):
                raise ResearchError(
                    "Semantic step requires an exact model/input binding."
                )
            if (
                self.selected_source_document_ids
                or self.authorized_source_url
                or any(
                    v is not None
                    for v in (
                        self.evidence_authorization,
                        self.assessment_authorization,
                        self.claim_authorization,
                        self.contradiction_authorization,
                        self.comparison_authorization,
                        self.completion_authorization,
                        self.discovery_provider,
                    )
                )
            ):
                raise ResearchError("Semantic proposal cannot carry other authority.")
        elif self.semantic_evidence_binding is not None:
            raise ResearchError(
                "Only semantic proposals may carry model/input binding."
            )
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
        if self.discovery_provider is not None and not isinstance(
            self.discovery_provider, ResearchDiscoveryProviderName
        ):
            raise ResearchError("Research plan discovery provider is invalid.")
        # A provider named on a step that will never discover anything would be
        # an authorization for a network target the step cannot reach, which is
        # exactly the kind of approval nobody can reason about.
        if (
            self.discovery_provider is not None
            and self.capability is not ResearchPlanStepCapability.SOURCE_DISCOVERY
        ):
            raise ResearchError(
                "Only a source discovery step may name a discovery provider."
            )
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
