"""One explicit model step over a reviewed transient input. No acceptance."""

from collections.abc import Callable

from core.Exceptions import ResearchError
from llm.LLMEndpointPolicy import is_loopback_llm_endpoint
from llm.OpenAICompatibleProvider import (
    ChatCompletionTransport,
    OpenAICompatibleProvider,
)
from research.LLMSemanticEvidenceProposalProvider import (
    LLMSemanticEvidenceProposalProvider,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.SemanticEvidenceRequest import SemanticEvidenceRequest
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding
from research.SemanticEvidenceStepResult import SemanticEvidenceStepResult


class SemanticEvidenceStepOperation:
    """Trusted composition supplies one destination and transient request lookup.

    The provider is built from that same destination, so a separate endpoint
    label cannot accidentally describe a different model. The existing executor
    owns approval and pre-attempt charging. No fallback or refetch exists here.
    """

    operation_name = "semantic_evidence_proposal"

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str | None,
        transport: ChatCompletionTransport,
        resolve_request: Callable[[str], SemanticEvidenceRequest | None],
    ) -> None:
        SemanticEvidenceStepBinding("0" * 64, endpoint, model)
        self._endpoint = endpoint
        self._model = model
        self._resolve_request = resolve_request
        self._provider = LLMSemanticEvidenceProposalProvider(
            OpenAICompatibleProvider(endpoint, api_key, model, transport)
        )

    def run(
        self, step: ResearchPlanStep, context: ResearchPlanExecutionContext
    ) -> ResearchPlanStepOperationResult:
        binding = step.semantic_evidence_binding
        if (
            step.capability is not ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL
            or binding is None
            or binding.endpoint != self._endpoint
            or binding.model != self._model
            or context.cancelled
            or context.execution_id is None
            or context.target_binding is not None
            or not context.disclosure.permits_model_call
            or (
                not context.disclosure.permits_remote_endpoint
                and not is_loopback_llm_endpoint(self._endpoint)
            )
        ):
            return self._declined("Model permission or exact destination unavailable.")
        request = self._resolve_request(binding.input_fingerprint)
        if (
            not isinstance(request, SemanticEvidenceRequest)
            or request.content_fingerprint != binding.input_fingerprint
            or request.previews[0].run_id != context.research_run_id
            or request.question.strip() != context.research_question
            or context.cancelled
        ):
            return self._declined("Reviewed semantic input is unavailable or changed.")
        try:
            candidates = self._provider.propose_prepared(
                request, binding.input_fingerprint
            )
        except ResearchError:
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail="Model request failed or its proposals failed validation.",
            )
        if context.cancelled:
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail="Model request ended after cancellation; proposals discarded.",
            )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=f"{len(candidates)} unaccepted evidence proposals for review.",
            semantic_evidence=SemanticEvidenceStepResult(
                context.execution_id, step.step_id, request, candidates
            ),
        )

    @staticmethod
    def _declined(detail: str) -> ResearchPlanStepOperationResult:
        return ResearchPlanStepOperationResult(
            performed=False, succeeded=False, detail=detail
        )
