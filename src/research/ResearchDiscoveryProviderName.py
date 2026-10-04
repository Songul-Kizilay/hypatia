"""Which source of sources a discovery step is allowed to contact.

A closed vocabulary rather than a name or a URL. Provider choice decides which
host is contacted, which query language is spoken, and what kind of record comes
back, so it is exactly the kind of value that must never arrive as free text: a
provider field accepting arbitrary strings is a provider field that eventually
accepts one somebody else wrote.

Three members, and they are not interchangeable. Crossref indexes scholarly
literature; NVD publishes vulnerability records; CURATED returns a small,
hand-reviewed catalog of specific, fixed URLs at recognized authoritative
teaching sources (PortSwigger Web Security Academy, OWASP) for a closed set of
named topics. A question about a CVE asked of Crossref returns papers that
happen to share its tokens, and the same question asked of NVD returns the
vulnerability itself; a topic asked of CURATED returns only URLs an engineer
put in the catalog by hand, never a search result and never a URL assembled
from the question text. Neither is a better provider in general, which is why
the choice is the operator's and is written into the plan they approve rather
than decided for them at execution time.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchDiscoveryProviderName(StrEnum):
    """Name one discovery provider the operator may authorize a step to use."""

    CROSSREF = "crossref"
    NVD = "nvd"
    CURATED = "curated"

    @property
    def label(self) -> str:
        """Return the name a person reads when approving a plan."""
        return _LABELS[self]


_LABELS = {
    ResearchDiscoveryProviderName.CROSSREF: "Crossref (scholarly literature)",
    ResearchDiscoveryProviderName.NVD: "NVD (vulnerability records)",
    ResearchDiscoveryProviderName.CURATED: "Curated (fixed authoritative catalog)",
}

#: The two general-purpose, any-topic providers: each can be asked an arbitrary
#: question and may or may not have something to say about it. CURATED is
#: deliberately excluded — it only ever answers for the small, named set of
#: topics an engineer put in its catalog, so "every other run asked Crossref
#: and NVD, therefore also propose asking Curated" is not a valid inference.
#: Code that proposes "ask the provider(s) this run has not asked yet" (for
#: example, curiosity's provider-coverage-gap detection and proposal) must
#: iterate this tuple, not the full enum, or it will propose Curated for
#: questions its catalog was never meant to answer.
GENERAL_DISCOVERY_PROVIDERS: tuple[ResearchDiscoveryProviderName, ...] = (
    ResearchDiscoveryProviderName.CROSSREF,
    ResearchDiscoveryProviderName.NVD,
)
