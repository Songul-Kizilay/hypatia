"""Bounded categories of request that ordinary chat must not answer alone.

Each kind names a request whose honest answer depends on work Hypatia can only
do through the explicit research workflow: reaching the network, discovering
candidate sources, accepting them, and recording evidence. A language model
asked such a question will happily produce plausible authors, journals, outlets,
and dates it never read, and that output is indistinguishable from research to
the person reading it.

Detecting a kind authorizes nothing. It cannot create a plan, grant a
capability, accept a source, or spend a network operation. Its only effect is to
make Hypatia say plainly what it did not do, so an over-eager match costs
honesty about absence rather than a dangerous action.
"""

from __future__ import annotations

from enum import StrEnum


class LiveInformationRequestKind(StrEnum):
    """Name one bounded reason ordinary chat cannot answer truthfully."""

    NONE = "none"
    EVIDENCE_PROVENANCE = "evidence_provenance"
    URL_ACCESS = "url_access"
    CURRENT_EVENTS = "current_events"
    ACADEMIC_SOURCES = "academic_sources"
    WEB_SEARCH = "web_search"

    @property
    def requires_live_research(self) -> bool:
        """Return whether answering would need network research that did not run."""
        return self not in (
            LiveInformationRequestKind.NONE,
            LiveInformationRequestKind.EVIDENCE_PROVENANCE,
        )

    @property
    def concerns_one_named_url(self) -> bool:
        """Return whether the person named a specific page to open.

        Kept separate because the honest answer is different. For a topic
        request the answer is that no research ran; for a named link it is that
        the link was not opened, which is not a claim about the site.
        """
        return self is LiveInformationRequestKind.URL_ACCESS

    @property
    def detected(self) -> bool:
        """Return whether this request needs an honesty boundary at all."""
        return self is not LiveInformationRequestKind.NONE
