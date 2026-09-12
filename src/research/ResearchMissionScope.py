"""Digest-bound permission for one provider-derived reference evidence slice.

This describes permitted derivation, not another authorization or planner.
Concrete URLs/chunks must come from the approved predecessors. One source and
one evidence record are the hard bounds; no target testing or model permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap

if TYPE_CHECKING:
    from research.ResearchPlanStep import ResearchPlanStep

MISSION_CAPABILITIES = (
    Cap.LOCAL_KNOWLEDGE_SEARCH,
    Cap.SOURCE_DISCOVERY,
    Cap.SOURCE_FETCH,
    Cap.SOURCE_ACCEPT,
    Cap.EVIDENCE_RECORDING,
)


@dataclass(frozen=True, slots=True)
class ResearchMissionScope:
    provider: ResearchDiscoveryProviderName
    source_policy: str = "selected_provider_public_https_reference"
    max_source_bytes: int = 16_384
    max_sources: int = 1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.provider, ResearchDiscoveryProviderName)
            or self.source_policy != "selected_provider_public_https_reference"
            or type(self.max_sources) is not int
            or self.max_sources != 1
            or type(self.max_source_bytes) is not int
            or not 1 <= self.max_source_bytes <= 16_384
        ):
            raise ResearchError("Invalid bounded reference mission scope.")

    def validate_steps(self, steps: tuple[ResearchPlanStep, ...]) -> None:
        if tuple(s.capability for s in steps) != MISSION_CAPABILITIES:
            raise ResearchError(
                "Mission capabilities must retain their approved order."
            )
        if steps[1].discovery_provider is not self.provider:
            raise ResearchError("Mission cannot substitute its discovery provider.")
        for step in steps:
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
                    )
                )
            ):
                raise ResearchError(
                    "Mission inputs must derive from their predecessors."
                )
