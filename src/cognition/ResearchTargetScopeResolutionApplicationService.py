"""Brain-facing boundary for reading, never granting, a scope's stance on a host.

Pure read over a caller-supplied, already-validated `ResearchTargetScope`.
Performs no DNS lookup, no fetch, no persistence, no model call and no
authorization check; the result is an explanation, never a grant to proceed.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.ResearchTargetScope import ResearchTargetScope
from response.ResponseComposer import ResponseComposer

RESEARCH_TARGET_SCOPE_RESOLUTION_PREVIEW_INTENT = (
    "research_target_scope_resolution_preview"
)


class ResearchTargetScopeResolutionApplicationService:
    """Classify one caller-supplied hostname against one caller-supplied scope."""

    def __init__(self, response_composer: ResponseComposer) -> None:
        self._response_composer = response_composer

    @staticmethod
    def is_preview_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured resolution-preview intent."""
        return (
            request.metadata.get("intent")
            == RESEARCH_TARGET_SCOPE_RESOLUTION_PREVIEW_INTENT
        )

    def process_preview(self, request: BrainRequest) -> BrainResponse:
        """Resolve one hostname against one scope, or a bounded refusal."""
        try:
            scope = request.metadata.get("research_target_scope")
            if not isinstance(scope, ResearchTargetScope):
                raise ResearchError(
                    "Target scope resolution preview requires a validated scope."
                )
            hostname = request.metadata.get("hostname")
            if not isinstance(hostname, str):
                raise ResearchError(
                    "Target scope resolution preview requires an explicit hostname."
                )
            resolution = scope.resolve_hostname(hostname)
        except ResearchError as error:
            composer = self._response_composer
            return composer.research_target_scope_resolution_preview_failure(
                request, str(error)
            )
        return self._response_composer.research_target_scope_resolution_preview(
            request, resolution
        )
