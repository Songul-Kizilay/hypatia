"""Brain-facing boundary for the first reviewed Kali operation run."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from cognition.KaliToolGateway import KaliToolGateway
from research.KaliToolGatewayFailure import KaliToolGatewayError
from research.ResearchKaliOperationAuthorizationStore import (
    ResearchKaliOperationAuthorizationStore,
)
from research.ResearchKaliOperationExecution import (
    ResearchKaliOperationProcessAdapter,
)
from research.ResearchKaliRuntimeEnvironment import ResearchKaliRuntimeProbe
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
        self._gateway = KaliToolGateway(
            preview_service,
            authorization_store,
            runtime_probe,
            process_adapter,
            clock=clock,
        )

    @staticmethod
    def is_run_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured operation-run intent."""
        return request.metadata.get("intent") == KALI_OPERATION_RUN_INTENT

    def process_run(self, request: BrainRequest) -> BrainResponse:
        """Consume one exact authorization, then run one reviewed operation."""
        try:
            result = self._gateway.run(request)
        except KaliToolGatewayError as error:
            return self._response_composer.kali_operation_run_failure(
                request,
                str(error),
                gateway_failure=error.failure,
            )
        return self._response_composer.kali_operation_run(request, result)
