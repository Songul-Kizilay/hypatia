"""Brain-facing boundary for the first reviewed Kali operation run."""

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
from research.ResearchKaliOperationExecution import (
    ResearchKaliOperationProcessAdapter,
    ResearchKaliOperationRun,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationKind,
    is_kali_operation_digest,
)
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeProbe,
    ResearchKaliRuntimeRequirement,
)
from response.ResponseComposer import ResponseComposer

KALI_OPERATION_RUN_INTENT = "kali_operation_run"


class KaliOperationRunApplicationService:
    """Run one reviewed operation only after all explicit gates pass."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        preview_service: KaliOperationPreviewApplicationService,
        authorization_store: ResearchKaliOperationAuthorizationStore,
        runtime_probe: ResearchKaliRuntimeProbe,
        process_adapter: ResearchKaliOperationProcessAdapter,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._preview_service = preview_service
        self._authorization_store = authorization_store
        self._runtime_probe = runtime_probe
        self._process_adapter = process_adapter
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def is_run_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured operation-run intent."""
        return request.metadata.get("intent") == KALI_OPERATION_RUN_INTENT

    def process_run(self, request: BrainRequest) -> BrainResponse:
        """Consume one exact authorization, then run one reviewed operation."""
        try:
            result = self._run(request)
        except ResearchError as error:
            return self._response_composer.kali_operation_run_failure(
                request,
                str(error),
            )
        return self._response_composer.kali_operation_run(request, result)

    def _run(self, request: BrainRequest) -> ResearchKaliOperationRun:
        if request.metadata.get("operator_opt_in") is not True:
            raise ResearchError("Kali operation run requires explicit run opt-in.")
        authorization_id = self._required_text(
            request.metadata.get("authorization_id"),
            "Kali operation run authorization ID",
        )
        expected_digest = request.metadata.get("operation_digest")
        if not is_kali_operation_digest(expected_digest):
            raise ResearchError("Kali operation run digest is invalid.")
        preview = self._preview_service.preview_for_request(request)
        if preview.operation_digest != expected_digest:
            raise ResearchError("Kali operation run digest does not match the preview.")
        if preview.operation_kind is not ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
            raise ResearchError("Kali operation run kind is not supported.")

        authorizations = self._authorization_store.load()
        matches = tuple(
            authorization
            for authorization in authorizations
            if authorization.authorization_id == authorization_id
        )
        if len(matches) != 1:
            raise ResearchError(
                "Kali operation run requires one recorded authorization."
            )
        authorization = matches[0]
        if authorization.has_expired_at(self._clock()):
            raise ResearchError("Kali operation run authorization has expired.")
        if authorization.operation_digest != preview.operation_digest:
            raise ResearchError(
                "Kali operation run authorization digest does not match."
            )
        if (
            authorization.program_id != preview.program_id
            or authorization.scope_revision_id != preview.scope_revision_id
            or authorization.scope_revision_digest != preview.scope_revision_digest
            or authorization.execution_policy_digest != preview.execution_policy_digest
        ):
            raise ResearchError("Kali operation run authorization binding is stale.")

        readiness = self._runtime_probe.readiness(ResearchKaliRuntimeRequirement())
        if not readiness.ready:
            raise ResearchError(f"Kali runtime is not ready: {readiness.reason}")

        remaining = [
            entry
            for entry in authorizations
            if entry.authorization_id != authorization.authorization_id
        ]
        self._authorization_store.save(remaining)
        process_result = self._process_adapter.run(
            preview.command_plan,
            timeout_seconds=preview.max_seconds,
        )
        return ResearchKaliOperationRun(
            authorization_id=authorization.authorization_id,
            operation_digest=preview.operation_digest,
            program_id=preview.program_id,
            scope_revision_id=preview.scope_revision_id,
            scope_revision_digest=preview.scope_revision_digest,
            execution_policy_digest=preview.execution_policy_digest,
            operation_kind=preview.operation_kind,
            command_plan=preview.command_plan,
            process_result=process_result,
        )

    @staticmethod
    def _required_text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        return value.strip()
