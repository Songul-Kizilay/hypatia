"""One readable source, and the exact identifiers it is hiding.

A card carries both halves at once on purpose. The visible half is a title, a
site, and a status a person can act on; the hidden half is the run, discovery,
document, and URL that the audit view shows unchanged. Keeping them in one
object means Simple mode cannot display a status it has no identity for, and
Advanced Details cannot show identifiers belonging to some other row.

`accepted` is read from canonical run membership, never from the fact that
someone pressed a button on this card. A candidate whose fetch failed, or
succeeded into local knowledge without the run taking it, is still a discovered
candidate here — because that is what the run says it is.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_CARD_TITLE_LENGTH = 90


@dataclass(frozen=True, slots=True)
class SimpleSourceCard:
    """Present one discovered or accepted source without technical vocabulary."""

    title: str
    site: str
    status_text: str
    accepted: bool
    url: str
    document_id: str = ""
    relevance_text: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ResearchError("A source card needs a title.")
        if not isinstance(self.status_text, str) or not self.status_text.strip():
            raise ResearchError("A source card needs a status.")
        if not isinstance(self.accepted, bool):
            raise ResearchError("A source card acceptance flag must be boolean.")
        if self.accepted and not self.document_id.strip():
            raise ResearchError(
                "An accepted source card must carry its canonical document ID."
            )
        if not self.accepted and self.document_id.strip():
            raise ResearchError(
                "A card that the run did not accept cannot claim a document ID."
            )
        if not isinstance(self.relevance_text, str):
            raise ResearchError("A source card relevance line must be text.")

    @property
    def heading(self) -> str:
        """Return the bounded single-line title a person reads first."""
        title = " ".join(self.title.split())
        if len(title) > MAX_CARD_TITLE_LENGTH:
            return f"{title[: MAX_CARD_TITLE_LENGTH - 3]}..."
        return title

    @property
    def subheading(self) -> str:
        """Return the site line, or nothing when no host could be derived."""
        return self.site
