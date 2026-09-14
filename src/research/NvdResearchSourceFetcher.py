"""Materialize an accepted NVD candidate from the API it was discovered through.

The generic fetcher cannot read `nvd.nist.gov/vuln/detail/CVE-...`, and no
amount of improving it will. That page is an application shell: the bytes it
serves contain an empty `<app-root>` element and a script loader, and the CVE
appears only after a browser executes the application behind a bot check. The
answer to that is not a browser, a renderer, or a way around the check — it is
to stop asking the page for something the API already publishes properly.

So an accepted NVD candidate is read from the NVD CVE API 2.0, through the same
pinned transport, the same fixed host and the same one-request discipline the
discovery provider already uses. Nothing new talks to the network.

What this does not do is change what acceptance means. It runs only when a
person has explicitly confirmed one candidate; it materializes exactly the
record that candidate names and refuses anything else; and it produces a source
and nothing more — no evidence, no assessment, no claim, and no reference
followed. The references in the record are text in a document.

The URL keeps its meaning. A materialized record is still named by its detail
page, because that is the resource a person opens, cites, and recognises, and
because the accepted source has to join back to the candidate it came from. The
API endpoint is recorded beside it as where the bytes were actually read.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.NvdResearchSourceDiscoveryProvider import (
    NVD_DETAIL_PREFIX,
    NvdResearchSourceDiscoveryProvider,
)
from research.ResearchSource import ResearchSource
from research.ResearchVulnerabilityRecord import is_cve_id

#: Named so that a person reading a document's provenance can tell at a glance
#: that it was not scraped from the rendered page.
NVD_API_ACQUISITION = "nvd_cve_api_2.0"

NVD_SOURCE_CONTENT_TYPE = "text/plain"


def cve_id_for(url: str) -> str:
    """Return the CVE an NVD detail URL names, or nothing at all.

    Deliberately exact. Only the canonical detail prefix and only a well-formed
    identifier after it — a lookalike host, an extra path segment or a malformed
    identifier is not this route's business, and guessing at a correction would
    materialize a vulnerability nobody accepted.
    """
    if not isinstance(url, str):
        return ""
    candidate = url.strip()
    if not candidate.startswith(NVD_DETAIL_PREFIX):
        return ""
    identifier = candidate[len(NVD_DETAIL_PREFIX) :].strip().upper()
    return identifier if is_cve_id(identifier) else ""


class NvdResearchSourceFetcher:
    """Read one accepted CVE from the NVD API rather than from its web page."""

    def __init__(
        self,
        provider: NvdResearchSourceDiscoveryProvider | None = None,
        clock: object = None,
    ) -> None:
        self._provider = provider or NvdResearchSourceDiscoveryProvider()
        self._clock = clock if callable(clock) else (lambda: datetime.now(UTC))

    def fetch(self, url: str) -> ResearchSource:
        """Return one CVE's authoritative record as a bounded local source."""
        cve_id = cve_id_for(url)
        if not cve_id:
            raise ResearchError("This is not an NVD vulnerability record URL.")
        document = self._provider.materialize(cve_id)
        # The provider already refuses a mismatched identifier. Checked again
        # here because this is the boundary that decides what the source is
        # named, and a source named by one CVE holding another's facts is the
        # one outcome no downstream reader could detect.
        if document.cve_id != cve_id:
            raise ResearchError("NVD returned a different vulnerability record.")
        fetched_at = self._clock()
        if not isinstance(fetched_at, datetime) or fetched_at.utcoffset() is None:
            raise ResearchError("NVD source fetch time must be timezone-aware.")
        return ResearchSource(
            url=f"{NVD_DETAIL_PREFIX}{cve_id}",
            title=document.title(),
            content=document.content(),
            content_type=NVD_SOURCE_CONTENT_TYPE,
            fetched_at=fetched_at,
            content_resource=document.api_resource,
            acquisition=NVD_API_ACQUISITION,
        )
