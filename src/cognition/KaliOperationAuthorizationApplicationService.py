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
from research.ResearchKaliOperationAuthorizationStore import (
    ResearchKaliOperationAuthorizationStore,
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
        authorization_store: ResearchKaliOperationAuthorizationStore | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._preview_service = preview_service
        self._authorization_store = authorization_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._authorizations: dict[str, ResearchKaliOperationAuthorization] = {}
        self._restore()

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
        authorization = ResearchKaliOperationAuthorization.for_preview(
            authorization_id=self._id_factory(),
            preview=preview,
            authorized_at=self._clock(),
        )
        if authorization.authorization_id in self._authorizations:
            raise ResearchError(
                "Kali operation authorization identity is already recorded."
            )
        self._authorizations[authorization.authorization_id] = authorization
        if not self._persist():
            self._authorizations.pop(authorization.authorization_id, None)
            raise ResearchError("Kali operation authorization could not be recorded.")
        return authorization

    def _restore(self) -> None:
        if self._authorization_store is None:
            return
        for authorization in self._authorization_store.load():
            self._authorizations[authorization.authorization_id] = authorization

    def _persist(self) -> bool:
        if self._authorization_store is None:
            return True
        try:
            self._authorization_store.save(list(self._authorizations.values()))
        except ResearchError:
            return False
        return True
