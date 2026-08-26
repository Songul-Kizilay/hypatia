"""Which source of sources a discovery step is allowed to contact.

A closed vocabulary rather than a name or a URL. Provider choice decides which
host is contacted, which query language is spoken, and what kind of record comes
back, so it is exactly the kind of value that must never arrive as free text: a
provider field accepting arbitrary strings is a provider field that eventually
accepts one somebody else wrote.

Two members, and they are not interchangeable. Crossref indexes scholarly
literature; NVD publishes vulnerability records. A question about a CVE asked of
Crossref returns papers that happen to share its tokens, and the same question
asked of NVD returns the vulnerability itself. Neither is a better provider in
general, which is why the choice is the operator's and is written into the plan
they approve rather than decided for them at execution time.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchDiscoveryProviderName(StrEnum):
    """Name one discovery provider the operator may authorize a step to use."""

    CROSSREF = "crossref"
    NVD = "nvd"

    @property
    def label(self) -> str:
        """Return the name a person reads when approving a plan."""
        return _LABELS[self]


_LABELS = {
    ResearchDiscoveryProviderName.CROSSREF: "Crossref (scholarly literature)",
    ResearchDiscoveryProviderName.NVD: "NVD (vulnerability records)",
}
