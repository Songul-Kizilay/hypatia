"""Report same-question provider observations without choosing a provider."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.PairedProviderQualityEvents import PairedProviderQualityEvents
from eventbus.EventBus import EventBus
from research.ResearchPairedProviderQualityEvaluator import (
    ResearchPairedProviderQualityEvaluator,
)
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

PAIRED_PROVIDER_QUALITY_REPORT_INTENT = "paired_provider_quality_report"


class PairedProviderQualityApplicationService:
    """Read persisted runs and produce an aligned descriptive report only."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        evaluator: ResearchPairedProviderQualityEvaluator | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._evaluator = evaluator or ResearchPairedProviderQualityEvaluator()
        self._events = PairedProviderQualityEvents(event_bus)

    @staticmethod
    def is_report_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == PAIRED_PROVIDER_QUALITY_REPORT_INTENT

    def process_report(self, request: BrainRequest) -> BrainResponse:
        report = self._evaluator.evaluate(self._run_manager.list())
        self._events.reported(report)
        return self._response_composer.paired_provider_quality(request, report)
