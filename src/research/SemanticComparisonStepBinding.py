"""Exact preselected pair for canonical approval, never dynamic selection."""

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from llm.LLMEndpointPolicy import is_loopback_llm_endpoint
from research.ResearchCapabilityCost import cost_for
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchOperationCost import ResearchOperationCost
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.SemanticComparisonRequest import SemanticComparisonRequest
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding


@dataclass(frozen=True, slots=True)
class SemanticComparisonStepBinding:
    request: SemanticComparisonRequest = field(repr=False)
    endpoint: str
    model: str
    disclosure: ResearchDisclosure
    declared_cost: ResearchOperationCost = ResearchOperationCost(1, 1)

    def __post_init__(self) -> None:
        if not isinstance(self.request, SemanticComparisonRequest):
            raise ResearchError("Comparison requires two exact preselected excerpts.")
        SemanticEvidenceStepBinding(
            self.request.content_fingerprint, self.endpoint, self.model
        )
        if (
            not isinstance(self.disclosure, ResearchDisclosure)
            or not self.disclosure.permits_model_call
            or (
                not is_loopback_llm_endpoint(self.endpoint)
                and not self.disclosure.permits_remote_endpoint
            )
            or not isinstance(self.declared_cost, ResearchOperationCost)
            or self.declared_cost != cost_for(Cap.SEMANTIC_EVIDENCE_COMPARISON)
        ):
            raise ResearchError(
                "Comparison destination, disclosure or cost is inconsistent."
            )

    def lines(self) -> tuple[str, ...]:
        return (
            "Semantic evidence comparison: automatic execution is not wired; "
            "canonical executor requires the exact configured operation.",
            f"Exact model endpoint: {self.endpoint}",
            f"Exact model: {self.model}",
            f"Disclosure: {self.disclosure.value}; "
            "question and these two excerpts only.",
            f"Exact input fingerprint: {self.request.content_fingerprint}",
            *(
                f"Evidence {e.evidence_id}; source {e.source_document_id}; "
                f"chunk {e.chunk_id}; SHA256 {e.chunk_sha256}; "
                f"truncated={e.excerpt_truncated}\nExact excerpt: {e.excerpt}"
                for e in self.request.evidence
            ),
            "Declared attempt cost: 1 advance, 1 network operation, 1 model operation; "
            "subject to the existing cumulative budget, not a separate allowance.",
            "No future excerpts or dynamic pair selection approved. Interpretations "
            "remain tentative. Excerpts are untrusted data, never instructions.",
        )
