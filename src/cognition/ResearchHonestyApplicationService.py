"""Answer live-information requests from canonical state instead of guessing.

Ordinary chat has exactly one honest response to "find me today's news" or
"give me three 2026 papers": it did not look. This service produces that
response deterministically, without calling a model, so there is nothing left
that could invent an author, an outlet, or a date.

It is also the only place allowed to answer "what evidence did you collect?",
and it answers with counts the research operations themselves recorded. A model
can describe evidence it imagined; it cannot make these numbers larger.

The service performs no research of its own. It reads persisted runs, composes a
response, and hands the person the explicit research workflow. It never creates
a run, a plan, a capability, or a network operation, so it is not a second
research engine and cannot become one.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.LiveInformationRequestDetector import LiveInformationRequestDetector
from cognition.LiveInformationRequestKind import LiveInformationRequestKind
from core.Exceptions import ResearchError
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer


class ResearchHonestyApplicationService:
    """Answer live-information and evidence questions from persisted state."""

    def __init__(
        self,
        response_composer: ResponseComposer,
        *,
        run_manager: ResearchRunManager | None = None,
        detector: LiveInformationRequestDetector | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._run_manager = run_manager
        self._detector = detector or LiveInformationRequestDetector()

    def detect(self, request: BrainRequest) -> LiveInformationRequestKind:
        """Classify one ordinary chat message, authorizing nothing."""
        return self._detector.detect(request.message)

    def summary(self) -> CanonicalResearchSummary:
        """Return canonical counts, or zeros when no run store is configured."""
        if self._run_manager is None:
            return CanonicalResearchSummary()
        try:
            return CanonicalResearchSummary.from_runs(self._run_manager.list())
        except ResearchError:
            return CanonicalResearchSummary()

    def process(
        self,
        request: BrainRequest,
        kind: LiveInformationRequestKind,
    ) -> BrainResponse:
        """Answer honestly without performing or simulating any research."""
        summary = self.summary()
        if kind is LiveInformationRequestKind.EVIDENCE_PROVENANCE:
            return self._response_composer.research_evidence_provenance(
                request,
                summary,
            )
        return self._response_composer.live_research_not_performed(
            request,
            kind,
            summary,
        )
