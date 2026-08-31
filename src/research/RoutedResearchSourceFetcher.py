"""Send each accepted source to the one loader that can actually read it.

There is exactly one provider-specific route and it exists because one provider
publishes its records somewhere other than the URL that names them. Everything
else — every DOI, every article, every ordinary page — takes the generic HTTPS
path it always took, unchanged and unaware that this class exists.

The route is chosen by the URL and by nothing else. Not by the provider named in
the discovery, not by a flag on the request, and not by trying one loader and
falling back to the other: a fallback is how a Crossref DOI ends up asking the
NVD API about it, and how an NVD record that legitimately failed gets quietly
replaced by whatever the web page happened to serve. One URL selects one loader,
and if that loader refuses, the load has failed.

Routing on the URL rather than on the discovery's provider is also what keeps
the two honest with each other. The candidate's URL is written by the provider
that returned it and revalidated against that discovery before acceptance, so a
candidate cannot arrive here under another provider's name without having failed
that check first.
"""

from __future__ import annotations

from research.NvdResearchSourceFetcher import NvdResearchSourceFetcher, cve_id_for
from research.ResearchSource import ResearchSource
from research.ResearchSourceFetcher import ResearchSourceFetcher


class RoutedResearchSourceFetcher:
    """Dispatch one accepted URL to the loader that understands it."""

    def __init__(
        self,
        default_fetcher: ResearchSourceFetcher,
        nvd_fetcher: ResearchSourceFetcher | None = None,
    ) -> None:
        self._default_fetcher = default_fetcher
        self._nvd_fetcher = nvd_fetcher or NvdResearchSourceFetcher()

    def fetch(self, url: str) -> ResearchSource:
        """Return the source, loaded by whichever route this URL belongs to."""
        if cve_id_for(url):
            return self._nvd_fetcher.fetch(url)
        return self._default_fetcher.fetch(url)
