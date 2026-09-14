"""Rank one discovery's candidates, the same way for every view that shows them.

Two panels display the same discovery, and if each ranked it for itself they
would eventually rank it differently — a second ranker instance, a second set of
weights, a second decision about what to do when ranking cannot run. A person
comparing the simple list against the audit list would then be comparing two
orderings and have no way to tell which one was the system's answer.

So there is one ranker and one fallback. When a query cannot be reduced to terms
at all, the provider's order is kept and every result is marked as not compared,
which is the truthful thing to say: no judgement was made, rather than a
judgement that everything is irrelevant. A view that raised instead would take
the whole panel down and leave a person unable to see sources that were found.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.RankedResearchSourceCandidate import RankedResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRelevance import UNRANKED_RELEVANCE
from research.ResearchSourceRelevanceRanker import ResearchSourceRelevanceRanker

#: One shared ranker. It holds nothing but its fixed weights, so a single
#: instance is safe, and it is shared precisely so the weights cannot differ
#: between two lists a person is comparing.
RANKER = ResearchSourceRelevanceRanker()


def ranked_candidates(
    discovery: ResearchSourceDiscoveryRecord,
) -> tuple[RankedResearchSourceCandidate, ...]:
    """Return one discovery's candidates in relevance order, or as they came."""
    if not isinstance(discovery, ResearchSourceDiscoveryRecord):
        raise ResearchError("A discovery record is required to rank candidates.")
    try:
        return RANKER.rank(discovery.query, discovery.candidates)
    except ResearchError:
        return unranked(discovery)


def unranked(
    discovery: ResearchSourceDiscoveryRecord,
) -> tuple[RankedResearchSourceCandidate, ...]:
    """Return the candidates in provider order, marked as never compared."""
    return tuple(
        RankedResearchSourceCandidate(
            candidate=candidate,
            provider_rank=position,
            relevance_rank=position,
            relevance=UNRANKED_RELEVANCE,
        )
        for position, candidate in enumerate(discovery.candidates, start=1)
    )
