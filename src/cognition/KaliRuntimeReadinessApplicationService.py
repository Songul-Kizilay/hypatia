"""Brain-facing boundary for opt-in WSL/Kali runtime readiness checks."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeProbe,
    ResearchKaliRuntimeRequirement,
    UnavailableResearchKaliRuntimeProbe,
)
from response.ResponseComposer import ResponseComposer

KALI_RUNTIME_READINESS_INTENT = "kali_runtime_readiness"


class KaliRuntimeReadinessApplicationService:
    """Report whether reviewed Kali runtime prerequisites are available."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        *,
        probe: ResearchKaliRuntimeProbe | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._probe = probe or UnavailableResearchKaliRuntimeProbe()

    @staticmethod
    def is_readiness_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured readiness intent."""
        return request.metadata.get("intent") == KALI_RUNTIME_READINESS_INTENT

    def process_readiness(self, request: BrainRequest) -> BrainResponse:
        """Return a readiness report only after explicit operator opt-in."""
        try:
            readiness = self._readiness(request)
        except ResearchError as error:
            return self._response_composer.kali_runtime_readiness_failure(
                request,
                str(error),
            )
        return self._response_composer.kali_runtime_readiness(request, readiness)

    def _readiness(self, request: BrainRequest):
        if request.metadata.get("operator_opt_in") is not True:
            raise ResearchError("Kali runtime readiness requires explicit opt-in.")
        return self._probe.readiness(ResearchKaliRuntimeRequirement())
