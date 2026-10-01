"""Single dispatch gate for the two existing reviewed Kali operations.

Preserves the current preview/scope/policy, exact authorization, runtime and
consume-before-dispatch checks. This is not a general-purpose tool registry.
No retry, grant creation, new operation kind or budget is introduced here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from core.Exceptions import ResearchError
from research.KaliToolGatewayFailure import (
    KaliToolGatewayError,
    KaliToolGatewayFailure,
    KaliToolGatewayStage,
)
from research.ResearchKaliOperationAuthorizationStore import (
    ResearchKaliOperationAuthorizationStore,
)
from research.ResearchKaliOperationExecution import (
    MAX_KALI_OPERATION_TIMEOUT_SECONDS,
    ResearchKaliOperationProcessAdapter,
    ResearchKaliOperationRun,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationKind,
    is_kali_operation_digest,
)
from research.ResearchKaliRuntimeEnvironment import (
    EXPECTED_CURL_EXECUTABLE,
    EXPECTED_CURL_VERSION_PREFIX,
    EXPECTED_DIG_EXECUTABLE,
    EXPECTED_DIG_VERSION_PREFIX,
    ResearchKaliRuntimeProbe,
    ResearchKaliRuntimeRequirement,
)


class KaliToolGateway:
    """Run one reviewed operation only after all explicit gates pass."""

    def __init__(
        self,
        preview_service: KaliOperationPreviewApplicationService,
        authorization_store: ResearchKaliOperationAuthorizationStore,
        runtime_probe: ResearchKaliRuntimeProbe,
        process_adapter: ResearchKaliOperationProcessAdapter,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._preview_service = preview_service
        self._authorization_store = authorization_store
        self._runtime_probe = runtime_probe
        self._process_adapter = process_adapter
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(self, request: BrainRequest) -> ResearchKaliOperationRun:
        """Check every gate anew; consume once, dispatch once, never retry."""
        stage = KaliToolGatewayStage.REQUEST
        try:
            if request.metadata.get("operator_opt_in") is not True:
                raise ResearchError("Kali operation run requires explicit run opt-in.")
            authorization_id = self._required_text(
                request.metadata.get("authorization_id"),
                "Kali operation run authorization ID",
            )
            expected_digest = request.metadata.get("operation_digest")
            if not is_kali_operation_digest(expected_digest):
                raise ResearchError("Kali operation run digest is invalid.")
            stage = KaliToolGatewayStage.SCOPE_POLICY
            preview = self._preview_service.preview_for_request(request)
            if preview.operation_digest != expected_digest:
                raise ResearchError(
                    "Kali operation run digest does not match the preview."
                )
            if not isinstance(preview.operation_kind, ResearchKaliOperationKind):
                raise ResearchError("Kali operation run kind is not supported.")

            stage = KaliToolGatewayStage.AUTHORIZATION
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
                or authorization.execution_policy_digest
                != preview.execution_policy_digest
            ):
                raise ResearchError(
                    "Kali operation run authorization binding is stale."
                )

            stage = KaliToolGatewayStage.RUNTIME_READINESS
            readiness = self._runtime_probe.readiness(
                self._runtime_requirement(preview.operation_kind)
            )
            if not readiness.ready:
                raise ResearchError(f"Kali runtime is not ready: {readiness.reason}")

            remaining = [
                entry
                for entry in authorizations
                if entry.authorization_id != authorization.authorization_id
            ]
            stage = KaliToolGatewayStage.AUTHORIZATION_CONSUMPTION
            self._authorization_store.save(remaining)
            stage = KaliToolGatewayStage.DISPATCH
            process_result = self._process_adapter.run(
                preview.command_plan,
                timeout_seconds=min(
                    preview.max_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS
                ),
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
                resolved_address=preview.resolved_address,
            )
        except (ResearchError, OSError) as error:
            # Store/adapter errors may contain paths or external output. Their
            # text is not an operator instruction or a trustworthy receipt.
            if stage is KaliToolGatewayStage.DISPATCH:
                reason = "The adapter did not return a validated operation result."
            elif stage is KaliToolGatewayStage.AUTHORIZATION_CONSUMPTION:
                reason = "Authorization consumption could not be confirmed."
            elif isinstance(error, OSError):
                reason = "A required local resource could not be read."
            else:
                reason = str(error)
            raise KaliToolGatewayError(
                KaliToolGatewayFailure(stage=stage, reason=reason)
            ) from error

    @staticmethod
    def _runtime_requirement(
        operation_kind: ResearchKaliOperationKind,
    ) -> ResearchKaliRuntimeRequirement:
        if operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
            return ResearchKaliRuntimeRequirement(
                executable_path=EXPECTED_DIG_EXECUTABLE,
                version_prefix=EXPECTED_DIG_VERSION_PREFIX,
                version_arguments=("-v",),
            )
        if operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
            return ResearchKaliRuntimeRequirement(
                executable_path=EXPECTED_CURL_EXECUTABLE,
                version_prefix=EXPECTED_CURL_VERSION_PREFIX,
                version_arguments=("--version",),
            )
        raise ResearchError("Kali operation run kind is not supported.")

    @staticmethod
    def _required_text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} cannot be empty.")
        return value.strip()
