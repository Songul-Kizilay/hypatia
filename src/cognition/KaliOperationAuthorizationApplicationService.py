"""Brain-facing boundary for human approval of inert Kali operation previews."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationPreview import is_kali_operation_digest
from response.ResponseComposer import ResponseComposer

KALI_OPERATION_AUTHORIZATION_INTENT = "kali_operation_authorization"


class KaliOperationAuthorizationApplicationService:
    """Approve one exact preview digest without starting a process."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        preview_service: KaliOperationPreviewApplicationService,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._preview_service = preview_service
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    @staticmethod
    def is_authorization_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured authorization intent."""
        return request.metadata.get("intent") == KALI_OPERATION_AUTHORIZATION_INTENT

    def process_authorization(self, request: BrainRequest) -> BrainResponse:
        """Approve the exact preview digest or fail closed."""
        try:
            authorization = self._authorize(request)
        except ResearchError as error:
            return self._response_composer.kali_operation_authorization_failure(
                request, str(error)
            )
        return self._response_composer.kali_operation_authorization(
            request,
            authorization,
        )

    def _authorize(self, request: BrainRequest) -> ResearchKaliOperationAuthorization:
        expected_digest = request.metadata.get("operation_digest")
        if not is_kali_operation_digest(expected_digest):
            raise ResearchError("Kali operation authorization digest is invalid.")
        preview = self._preview_service.preview_for_request(request)
        if preview.operation_digest != expected_digest:
            raise ResearchError(
                "Kali operation authorization digest does not match the preview."
            )
        return ResearchKaliOperationAuthorization.for_preview(
            authorization_id=self._id_factory(),
            preview=preview,
            authorized_at=self._clock(),
        )
