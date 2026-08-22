"""Read-only application boundary for Research overview requests."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchEvidenceIntegrityAuditor import ResearchEvidenceIntegrityAuditor
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)
from response.ResponseComposer import ResponseComposer


class ResearchOverviewApplicationService:
    """Serve bounded Research catalogs and diagnostics without mutation."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        research_run_manager: ResearchRunManager | None,
        source_content_restoration_status: (
            ResearchSourceContentRestorationStatus | None
        ),
        evidence_integrity_auditor: ResearchEvidenceIntegrityAuditor | None,
    ) -> None:
        self._response_composer = response_composer
        self._research_run_manager = research_run_manager
        self._source_content_restoration_status = source_content_restoration_status
        self._evidence_integrity_auditor = evidence_integrity_auditor

    @staticmethod
    def is_run_list_request(request: BrainRequest) -> bool:
        """Recognize the explicit structured research-run catalog request."""
        return request.metadata.get("intent") == "research_run_list"

    @staticmethod
    def is_evidence_list_request(request: BrainRequest) -> bool:
        """Recognize one explicit read-only research evidence catalog request."""
        return request.metadata.get("intent") == "research_evidence_list"

    @staticmethod
    def is_source_content_restoration_status_request(
        request: BrainRequest,
    ) -> bool:
        """Recognize the bounded read-only accepted-content startup status."""
        return (
            request.metadata.get("intent")
            == "research_source_content_restoration_status"
            or request.message.casefold().strip() == "research content status"
        )

    @staticmethod
    def is_evidence_integrity_status_request(request: BrainRequest) -> bool:
        """Recognize the bounded read-only evidence integrity audit."""
        return (
            request.metadata.get("intent") == "research_evidence_integrity_status"
            or request.message.casefold().strip() == "research evidence status"
        )

    def process_run_list(self, request: BrainRequest) -> BrainResponse:
        """Return the complete immutable research-run catalog."""
        if self._research_run_manager is None:
            return self._response_composer.research_run_failure(
                request,
                "Research run persistence is unavailable.",
                intent="research_run_list",
            )
        return self._response_composer.research_run_list_success(
            request,
            self._research_run_manager.list(),
        )

    def process_evidence_list(self, request: BrainRequest) -> BrainResponse:
        """Return persisted evidence from one exact research run."""
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return self._response_composer.research_evidence_list_failure(
                request,
                "A research run ID is required.",
            )
        if self._research_run_manager is None:
            return self._response_composer.research_evidence_list_failure(
                request,
                "Research run persistence is unavailable.",
            )
        try:
            run = self._research_run_manager.get(run_id)
        except ResearchError:
            return self._response_composer.research_evidence_list_failure(
                request,
                "Research run was not found.",
            )
        return self._response_composer.research_evidence_list_success(request, run)

    def process_source_content_restoration_status(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Return the captured startup aggregate without reading persistence."""
        status = self._source_content_restoration_status
        if status is None:
            status = ResearchSourceContentRestorationStatus.unavailable()
        return self._response_composer.research_source_content_restoration_status(
            request,
            status,
        )

    def process_evidence_integrity_status(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Audit in-memory runs and chunks without persistence or mutation."""
        status = ResearchEvidenceIntegrityStatus.unavailable()
        if (
            self._research_run_manager is not None
            and self._evidence_integrity_auditor is not None
        ):
            try:
                status = self._evidence_integrity_auditor.audit(
                    self._research_run_manager.list()
                )
            except ResearchError:
                pass
        return self._response_composer.research_evidence_integrity_status(
            request,
            status,
        )
