"""Exact approved pair only; canonical executor owns charging and authority."""

from core.Exceptions import ResearchError
from llm.OpenAICompatibleProvider import (
    ChatCompletionTransport,
    OpenAICompatibleProvider,
)
from research.LLMSemanticComparisonProposalProvider import (
    LLMSemanticComparisonProposalProvider,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager
from research.SemanticComparisonStepResult import SemanticComparisonStepResult
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding


class SemanticComparisonStepOperation:
    """Trusted composition pins destination; no fallback, selection or retries."""

    operation_name = "semantic_evidence_comparison"

    @property
    def destination(self) -> tuple[str, str]:
        return self._endpoint, self._model

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str | None,
        transport: ChatCompletionTransport,
        run_manager: ResearchRunManager,
    ):
        SemanticEvidenceStepBinding("0" * 64, endpoint, model)
        self._endpoint = endpoint
        self._model = model
        self._runs = run_manager
        self._provider = LLMSemanticComparisonProposalProvider(
            OpenAICompatibleProvider(endpoint, api_key, model, transport)
        )

    def run(
        self, step: ResearchPlanStep, context: ResearchPlanExecutionContext
    ) -> ResearchPlanStepOperationResult:
        binding = step.semantic_comparison_binding
        if (
            step.capability is not Cap.SEMANTIC_EVIDENCE_COMPARISON
            or binding is None
            or binding.endpoint != self._endpoint
            or binding.model != self._model
            or context.disclosure is not binding.disclosure
            or context.execution_id is None
            or context.research_run_id is None
            or context.target_binding is not None
            or context.cancelled
        ):
            return self._declined(
                "Exact comparison destination or permission unavailable."
            )
        try:
            binding.__post_init__()
            request = binding.request
            run = self._runs.get(context.research_run_id)
            if (
                run.status.terminal
                or run.run_id != context.research_run_id
                or request.run_id != context.research_run_id
                or request.question != context.research_question
                or run.question != request.question
                or any(
                    e not in run.evidence
                    or not any(
                        s.document_id == e.source_document_id for s in run.sources
                    )
                    for e in request.evidence
                )
                or context.cancelled
            ):
                return self._declined(
                    "Exact comparison evidence is missing or changed."
                )
        except ResearchError:
            return self._declined("Exact comparison evidence or binding unavailable.")
        try:
            candidates = self._provider.propose_prepared(
                request, request.content_fingerprint
            )
        except ResearchError:
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail="Comparison request failed or output failed validation.",
            )
        if context.cancelled:
            return ResearchPlanStepOperationResult(
                performed=True,
                succeeded=False,
                detail="Comparison ended after cancellation; output discarded.",
            )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=f"{len(candidates)} tentative semantic comparisons returned; "
            "not established truth or recorded evidence.",
            semantic_comparison=SemanticComparisonStepResult(
                context.execution_id, step.step_id, request, candidates
            ),
        )

    @staticmethod
    def _declined(detail: str) -> ResearchPlanStepOperationResult:
        return ResearchPlanStepOperationResult(
            performed=False, succeeded=False, detail=detail
        )
