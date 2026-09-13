"""Digest-bound permission for one provider-derived reference evidence slice.

This describes permitted derivation, not another authorization or planner.
Concrete URLs/chunks must come from approved predecessors. Explicit scope chooses
one source/evidence, lexical comparison, or an explicit semantic learning policy.
No targets. Model permission exists only in the explicit digest-bound policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.SemanticMissionPolicy import SemanticMissionPolicy

if TYPE_CHECKING:
    from research.ResearchPlanStep import ResearchPlanStep

MISSION_CAPABILITIES = (
    Cap.LOCAL_KNOWLEDGE_SEARCH,
    Cap.SOURCE_DISCOVERY,
    Cap.SOURCE_FETCH,
    Cap.SOURCE_ACCEPT,
    Cap.EVIDENCE_RECORDING,
)
COMPARISON_POLICY = "selected_provider_two_reference_comparison"
SEMANTIC_POLICY = "selected_provider_bounded_learning_research"
COMPARISON_CAPABILITIES = (
    *MISSION_CAPABILITIES[:2],
    *MISSION_CAPABILITIES[2:],
    Cap.SOURCE_ASSESSMENT,
    *MISSION_CAPABILITIES[2:],
    Cap.SOURCE_ASSESSMENT,
    Cap.SOURCE_COMPARISON,
)


@dataclass(frozen=True, slots=True)
class ResearchMissionScope:
    provider: ResearchDiscoveryProviderName
    source_policy: str = "selected_provider_public_https_reference"
    max_source_bytes: int = 16_384
    max_sources: int = 1
    semantic_policy: SemanticMissionPolicy | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.provider, ResearchDiscoveryProviderName)
            or not isinstance(self.source_policy, str)
            or type(self.max_sources) is not int
            or (self.source_policy, self.max_sources)
            not in {
                ("selected_provider_public_https_reference", 1),
                (COMPARISON_POLICY, 2),
                (SEMANTIC_POLICY, 3),
            }
            or type(self.max_source_bytes) is not int
            or not 1 <= self.max_source_bytes <= 16_384
        ):
            raise ResearchError("Invalid bounded reference mission scope.")
        if (
            self.source_policy == SEMANTIC_POLICY
            and not isinstance(self.semantic_policy, SemanticMissionPolicy)
        ) or (
            self.source_policy != SEMANTIC_POLICY and self.semantic_policy is not None
        ):
            raise ResearchError("Semantic mission must bind its disclosure policy.")

    def validate_steps(self, steps: tuple[ResearchPlanStep, ...]) -> None:
        if tuple(s.capability for s in steps) != self.capabilities:
            raise ResearchError(
                "Mission capabilities must retain their approved order."
            )
        if steps[1].discovery_provider is not self.provider:
            raise ResearchError("Mission cannot substitute its discovery provider.")
        for step in steps:
            expected_policy = (
                self.semantic_policy
                if step.capability is Cap.SEMANTIC_EVIDENCE_COMPARISON
                else None
            )
            if step.semantic_mission_policy != expected_policy:
                raise ResearchError("Mission model policy cannot be substituted.")
            if (
                step.authorized_source_url
                or step.selected_source_document_ids
                or any(
                    value is not None
                    for value in (
                        step.evidence_authorization,
                        step.assessment_authorization,
                        step.claim_authorization,
                        step.contradiction_authorization,
                        step.comparison_authorization,
                        step.completion_authorization,
                        step.semantic_evidence_binding,
                        step.semantic_comparison_binding,
                    )
                )
            ):
                raise ResearchError(
                    "Mission inputs must derive from their predecessors."
                )

    @property
    def capabilities(self) -> tuple[Cap, ...]:
        if self.semantic_policy is not None:
            return (
                *COMPARISON_CAPABILITIES[:-1],
                Cap.SEMANTIC_EVIDENCE_COMPARISON,
                Cap.SOURCE_COMPARISON,
                *MISSION_CAPABILITIES[2:],
                Cap.SOURCE_ASSESSMENT,
                Cap.SEMANTIC_EVIDENCE_COMPARISON,
                Cap.SOURCE_COMPARISON,
            )
        return (
            COMPARISON_CAPABILITIES if self.max_sources == 2 else MISSION_CAPABILITIES
        )
