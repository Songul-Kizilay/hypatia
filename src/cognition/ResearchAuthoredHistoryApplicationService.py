"""Read-only application boundary for authored Research history previews."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer


class ResearchAuthoredHistoryApplicationService:
    """Serve persisted authored-history views without mutation or providers."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        research_run_manager: ResearchRunManager | None,
    ) -> None:
        self._response_composer = response_composer
        self._research_run_manager = research_run_manager

    @staticmethod
    def is_claim_preview_request(request: BrainRequest) -> bool:
        """Recognize one explicit read-only claim-history request."""
        return request.metadata.get("intent") == "research_claim_preview"

    @staticmethod
    def is_source_comparison_preview_request(request: BrainRequest) -> bool:
        """Recognize an explicit read-only multi-source comparison request."""
        return request.metadata.get("intent") == "research_source_comparison_preview"

    @staticmethod
    def is_source_assessment_preview_request(request: BrainRequest) -> bool:
        """Recognize one explicit read-only accepted-source assessment."""
        return request.metadata.get("intent") == "research_source_assessment_preview"

    def process_claim_preview(self, request: BrainRequest) -> BrainResponse:
        """Read persisted claim history without providers or mutation."""
        run_id = request.metadata.get("research_run_id")
        failure = self._response_composer.research_claim_preview_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            preview = self._research_run_manager.preview_claims(run_id)
        except ResearchError:
            return failure(request, "Research run was not found.")
        return self._response_composer.research_claim_preview_success(
            request,
            preview,
        )

    def process_source_comparison_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Display accepted source material without providers or persistence."""
        run_id = request.metadata.get("research_run_id")
        document_ids = request.metadata.get("research_source_document_ids")
        failure = self._response_composer.research_source_comparison_preview_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if (
            not isinstance(document_ids, list)
            or not 2 <= len(document_ids) <= 5
            or not all(
                isinstance(document_id, str) and document_id.strip()
                for document_id in document_ids
            )
            or len({document_id.strip() for document_id in document_ids})
            != len(document_ids)
        ):
            return failure(
                request,
                "Two to five unique research source document IDs are required.",
            )
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            preview = self._research_run_manager.preview_source_comparison(
                run_id,
                document_ids,
            )
        except ResearchError:
            return failure(
                request,
                "Every comparison source must be accepted in the selected run.",
            )
        return self._response_composer.research_source_comparison_preview_success(
            request,
            preview,
        )

    def process_source_assessment_preview(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Read accepted provenance and stored evidence without live lookups."""
        run_id = request.metadata.get("research_run_id")
        document_id = request.metadata.get("research_source_document_id")
        failure = self._response_composer.research_source_assessment_preview_failure
        if not isinstance(run_id, str) or not run_id.strip():
            return failure(request, "A research run ID is required.")
        if not isinstance(document_id, str) or not document_id.strip():
            return failure(request, "A research source document ID is required.")
        if self._research_run_manager is None:
            return failure(request, "Research run persistence is unavailable.")
        try:
            preview = self._research_run_manager.preview_source_assessment(
                run_id,
                document_id,
            )
        except ResearchError:
            return failure(
                request,
                "Research source was not found among this run's accepted sources.",
            )
        return self._response_composer.research_source_assessment_preview_success(
            request,
            preview,
        )
