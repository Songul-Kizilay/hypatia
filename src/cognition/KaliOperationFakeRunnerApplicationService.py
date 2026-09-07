"""Deterministic no-process runner gate for authorized Kali operation previews."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchKaliOperationAuthorizationStore import (
    ResearchKaliOperationAuthorizationStore,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationFakeRun,
    ResearchKaliOperationKind,
    is_kali_operation_digest,
)
from response.ResponseComposer import ResponseComposer

KALI_OPERATION_FAKE_RUN_INTENT = "kali_operation_fake_run"


class KaliOperationFakeRunnerApplicationService:
    """Exercise the future runner boundary without creating a child process."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        preview_service: KaliOperationPreviewApplicationService,
        authorization_store: ResearchKaliOperationAuthorizationStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._preview_service = preview_service
        self._authorization_store = authorization_store
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def is_fake_run_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured fake-run intent."""
        return request.metadata.get("intent") == KALI_OPERATION_FAKE_RUN_INTENT

    def process_fake_run(self, request: BrainRequest) -> BrainResponse:
        """Return a deterministic fixture result or fail closed."""
        try:
            result = self._fake_run(request)
        except ResearchError as error:
            return self._response_composer.kali_operation_fake_run_failure(
                request,
                str(error),
            )
        return self._response_composer.kali_operation_fake_run(request, result)

    def _fake_run(self, request: BrainRequest) -> ResearchKaliOperationFakeRun:
        authorization_id = self._required_text(
            request.metadata.get("authorization_id"),
            "Kali fake run authorization ID",
        )
        expected_digest = request.metadata.get("operation_digest")
        if not is_kali_operation_digest(expected_digest):
            raise ResearchError("Kali fake run operation digest is invalid.")
        preview = self._preview_service.preview_for_request(request)
        if preview.operation_digest != expected_digest:
            raise ResearchError("Kali fake run digest does not match the preview.")
        matches = tuple(
            authorization
            for authorization in self._authorization_store.load()
            if authorization.authorization_id == authorization_id
        )
        if len(matches) != 1:
            raise ResearchError("Kali fake run requires one recorded authorization.")
        authorization = matches[0]
        if authorization.has_expired_at(self._clock()):
            raise ResearchError("Kali fake run authorization has expired.")
        if authorization.operation_digest != preview.operation_digest:
            raise ResearchError("Kali fake run authorization digest does not match.")
        if (
            authorization.program_id != preview.program_id
            or authorization.scope_revision_id != preview.scope_revision_id
            or authorization.scope_revision_digest != preview.scope_revision_digest
            or authorization.execution_policy_digest != preview.execution_policy_digest
        ):
            raise ResearchError("Kali fake run authorization binding is stale.")
        if preview.operation_kind is not ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
            raise ResearchError("Kali fake run operation kind is not supported.")
        return ResearchKaliOperationFakeRun(
            authorization_id=authorization.authorization_id,
            operation_digest=preview.operation_digest,
            program_id=preview.program_id,
            scope_revision_id=preview.scope_revision_id,
            scope_revision_digest=preview.scope_revision_digest,
            execution_policy_digest=preview.execution_policy_digest,
            operation_kind=preview.operation_kind,
            command_plan=preview.command_plan,
            simulated_stdout=(
                f"{preview.hostname} {preview.dns_record_type.value} "
                "simulated; no DNS query performed",
            ),
        )

    @staticmethod
    def _required_text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        return value.strip()
