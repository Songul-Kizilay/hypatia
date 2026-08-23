"""Report what our assessments say about each origin. Gate nothing.

Reputation is the part of a research system most likely to turn into prejudice,
so this service is built to make that impossible rather than merely unlikely. It
has no store, no write path, and no hook into fetching, acceptance, assessment,
or claims. It answers a question and returns text.

Concretely: a low standing does not refuse a fetch, does not discount evidence,
does not pre-assess a new source from that host, and does not change any
existing assessment. Whether a source is worth reading stays a judgement someone
makes while looking at it.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.SourceReputationEvents import SourceReputationEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchRunManager import ResearchRunManager
from research.SourceReputation import SourceReputation
from research.SourceReputationLedger import SourceReputationLedger
from response.ResponseComposer import ResponseComposer

SOURCE_REPUTATION_REPORT_INTENT = "source_reputation_report"


class SourceReputationApplicationService:
    """Derive and report per-origin reputation, deciding nothing."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        ledger: SourceReputationLedger | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._ledger = ledger or SourceReputationLedger()
        self._events = SourceReputationEvents(event_bus)

    @staticmethod
    def is_report_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == SOURCE_REPUTATION_REPORT_INTENT

    def process_report(self, request: BrainRequest) -> BrainResponse:
        """Report every origin, or one named origin, from assessments alone."""
        reputations = self._ledger.build(self._run_manager.list())
        origin = request.metadata.get("source_origin")
        if origin is not None:
            reputations = self._single(origin, reputations)
        self._events.reported(reputations)
        return self._response_composer.source_reputation(request, reputations)

    @staticmethod
    def _single(
        origin: object,
        reputations: tuple[SourceReputation, ...],
    ) -> tuple[SourceReputation, ...]:
        if not isinstance(origin, str) or not origin.strip():
            raise ResearchError("Source origin cannot be empty.")
        wanted = origin.strip().casefold().removeprefix("www.")
        return tuple(entry for entry in reputations if entry.origin == wanted)
