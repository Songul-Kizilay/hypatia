"""What kind of question a discovery was asked, decided from the question alone.

Two categories, and the small number is the point. A question naming exactly one
well-formed CVE identifier is an exact lookup; everything else is a keyword
search. Both are decided by the same strict parser the NVD provider uses, so a
question is classified identically no matter which provider was asked — the
category describes the question, never the answer.

A `SECURITY_KEYWORD` category was considered and left out. Nothing in this domain
can deterministically tell a security question from any other one: it would need
a keyword list somebody invented, and the list would decide the statistics. Two
honest categories beat three where the third is a guess.

The distinction earns its place because the providers differ sharply across it.
An exact CVE lookup returns the vulnerability itself; a keyword search against a
publication-ordered index returns whatever was published, which is how a live
search for a content-management flaw surfaced an unrelated colour-management bug
from 2009. Averaging those two into one number per provider would hide the only
thing the data actually shows.
"""

from __future__ import annotations

from enum import StrEnum

from research.ResearchVulnerabilityRecord import is_cve_id


class ResearchQueryCategory(StrEnum):
    """Name what kind of question one discovery asked."""

    EXACT_CVE = "exact_cve"
    KEYWORD = "keyword"

    @property
    def label(self) -> str:
        """Return the words a person reads in the report."""
        return _LABELS[self]


_LABELS = {
    ResearchQueryCategory.EXACT_CVE: "Exact CVE lookup",
    ResearchQueryCategory.KEYWORD: "Keyword search",
}

_TRIM = ".,;:!?()[]{}<>\"'"


def category_of(query: object) -> ResearchQueryCategory:
    """Classify one stored query, using the question and nothing else.

    Exactly one identifier makes it exact. Two are ambiguous and none is a
    keyword search, and both fall to `KEYWORD` rather than being guessed at,
    which is the same rule the provider applies when deciding how to ask.
    """
    if not isinstance(query, str):
        return ResearchQueryCategory.KEYWORD
    identifiers = {
        token
        for raw in query.split()
        if is_cve_id(token := raw.strip(_TRIM).upper())
    }
    return (
        ResearchQueryCategory.EXACT_CVE
        if len(identifiers) == 1
        else ResearchQueryCategory.KEYWORD
    )
