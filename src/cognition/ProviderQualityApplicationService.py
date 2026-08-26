"""Report how each provider's assessed samples turned out. Choose nothing.

Provider statistics are the part of a research system most likely to turn into a
routing policy, so this service is built so that it cannot. It has no store, no
write path, and no hook into provider selection, plan drafting, ranking,
reputation, acceptance, assessment, or claims. It answers a question and returns
text.

Concretely: a provider with a poor showing is still offered in the panel, still
nameable in a plan, still contacted when a person asks for it, and still ranked
exactly as before. Which provider to use stays a decision somebody makes while
looking at the numbers, and the numbers say plainly that they describe sources
the operator chose to look at rather than a measurement of what either provider
returns.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ProviderQualityEvents import ProviderQualityEvents
from eventbus.EventBus import EventBus
from research.ResearchProviderQualityEvaluator import ResearchProviderQualityEvaluator
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

PROVIDER_QUALITY_REPORT_INTENT = "provider_quality_report"


class ProviderQualityApplicationService:
    """Derive and report provider quality from recorded assessments alone."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        evaluator: ResearchProviderQualityEvaluator | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._evaluator = evaluator or ResearchProviderQualityEvaluator()
        self._events = ProviderQualityEvents(event_bus)

    @staticmethod
    def is_report_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == PROVIDER_QUALITY_REPORT_INTENT

    def process_report(self, request: BrainRequest) -> BrainResponse:
        """Describe every provider profile, across every recorded run."""
        report = self._evaluator.evaluate(self._run_manager.list())
        self._events.reported(report)
        return self._response_composer.provider_quality(request, report)
