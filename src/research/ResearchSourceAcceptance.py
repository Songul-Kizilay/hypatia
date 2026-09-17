"""Structural boundary for the canonical source-acceptance transaction.

The concrete service is an application-layer component. Research-layer
operations depend on this protocol instead, so the research layer never
imports the cognition layer and only one acceptance implementation exists.
"""

from typing import Protocol

from research.ResearchSource import ResearchSource
from research.ResearchSourceAcceptanceResult import ResearchSourceAcceptanceResult


class AcceptsResearchSource(Protocol):
    """Run the canonical acceptance transaction for one fetched source."""

    def accept(
        self,
        source: ResearchSource,
        run_id: str = "",
        *,
        requested_url: str = "",
        discovery_candidate_id: str = "",
    ) -> ResearchSourceAcceptanceResult:
        """Index, persist, and record the source, rolling back on failure."""
