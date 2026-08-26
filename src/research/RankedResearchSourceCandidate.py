"""A candidate with its two positions kept side by side.

Ranking rewrites order, and rewritten order is the easiest place in a research
tool to lose track of what actually happened. If only the new position survives,
the provider's own answer — which results it returned, and in what order — is
unrecoverable, and a fault in the ranking becomes indistinguishable from a fault
at the provider.

So both are kept. `provider_rank` is what the provider returned, unchanged and
never recomputed. `relevance_rank` is this system's ordering of the same
records, and it is derived: recomputing it changes nothing about where the
result came from. The candidate itself is carried untouched, so nothing here can
alter a URL, a title, or a snippet on its way to being displayed.

A duplicate is marked rather than removed. Two records of one resource are worth
seeing, because they are how a provider's own answer gets checked, but counting
them as two results is how one source starts to look like two.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceRelevance import ResearchSourceRelevance


@dataclass(frozen=True, slots=True)
class RankedResearchSourceCandidate:
    """Hold one candidate, where the provider put it, and where relevance puts it."""

    candidate: ResearchSourceCandidate
    provider_rank: int
    relevance_rank: int
    relevance: ResearchSourceRelevance
    duplicate_of_rank: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, ResearchSourceCandidate):
            raise ResearchError("A ranked result must carry its candidate.")
        for name in ("provider_rank", "relevance_rank"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ResearchError("A rank must be a position starting at one.")
        if not isinstance(self.relevance, ResearchSourceRelevance):
            raise ResearchError("A ranked result must carry its relevance.")
        if self.duplicate_of_rank is not None:
            if (
                isinstance(self.duplicate_of_rank, bool)
                or not isinstance(self.duplicate_of_rank, int)
                or self.duplicate_of_rank < 1
            ):
                raise ResearchError("A duplicate must name an earlier position.")
            if self.duplicate_of_rank >= self.provider_rank:
                raise ResearchError("A duplicate must follow what it duplicates.")

    @property
    def is_duplicate(self) -> bool:
        """Say whether an earlier result is the same resource as this one."""
        return self.duplicate_of_rank is not None
