"""Show one question's two provider results side by side. Contact nobody.

This service reads. It holds no provider, so it cannot query one; it holds no
store, so it cannot write one; and it has no path to plan drafting, approval or
execution, so opening a comparison can never become the act of running one.
Everything it renders already happened, through two ordinary approved discovery
steps that a person advanced one at a time.

What it deliberately refuses to do is conclude. It reports both sides and the
notice that neither was preferred, and the judgement stays with whoever asked.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ProviderComparisonEvents import ProviderComparisonEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchProviderComparisonBuilder import (
    ResearchProviderComparisonBuilder,
)
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

PROVIDER_COMPARISON_REPORT_INTENT = "provider_comparison_report"


class ProviderComparisonApplicationService:
    """Render one run's two provider result sets, judging neither."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        builder: ResearchProviderComparisonBuilder | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._builder = builder or ResearchProviderComparisonBuilder()
        self._events = ProviderComparisonEvents(event_bus)

    @staticmethod
    def is_report_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == PROVIDER_COMPARISON_REPORT_INTENT

    def process_report(self, request: BrainRequest) -> BrainResponse:
        """Report both sides for one run, or say why there is nothing to show."""
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            return self._response_composer.provider_comparison_rejected(
                request,
                "A research run ID is required.",
            )
        try:
            run = self._run_manager.get(run_id.strip())
        except ResearchError:
            return self._response_composer.provider_comparison_rejected(
                request,
                "Research run was not found.",
            )
        report = self._builder.build(run)
        self._events.reported(report)
        return self._response_composer.provider_comparison(request, report)
