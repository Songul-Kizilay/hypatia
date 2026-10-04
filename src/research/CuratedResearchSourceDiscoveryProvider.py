"""Discovery from a small, hand-reviewed catalog of fixed authoritative URLs.

Crossref and NVD each speak to a live API and can be asked almost anything.
This provider speaks to nothing. It holds a short, literal, code-reviewed list
of specific URLs at a small number of recognized security-teaching sources
(PortSwigger Web Security Academy, the OWASP Cheat Sheet Series) and returns
entries from that list only when the question names a topic the catalog
actually covers. There is no search, no network call, no model call, and no
way for the question text to produce a URL that is not already written here:
a provider whose candidate list could be influenced by its input is exactly
the SSRF-shaped mistake `PublicHttpsUrlValidator` and `PinnedHttpsTransport`
exist to prevent downstream, and the cheapest way to keep this provider out
of that category is to let it return literal constants and nothing else.

Matching is deliberately shallow, reusing the same `ResearchQueryTerms`
normalization NVD uses for its keyword route, so punctuation and case never
change the result. A topic matches when its required terms are all present or
one of its short aliases is present; a question matching no topic returns an
empty list rather than a guessed nearest topic, because an empty result is an
honest "this catalog has nothing for that" and a guessed one is not.

Every candidate URL still passes through the same `ResearchSourceCandidate`
validation (credential-free HTTPS, bounded lengths) as every other provider's
candidates, and still has to be explicitly accepted and fetched afterwards
through the ordinary, unmodified `HttpResearchSourceFetcher` — pinned address,
redirect revalidation, content-type and size bounds included. This provider
only ever shortens "which URL", never "is the URL safe to fetch".

Adding a topic later means adding a catalog entry by hand and reviewing it
like any other code change — not teaching this provider to search, infer, or
accept a URL from a caller. `GENERAL_DISCOVERY_PROVIDERS` in
`ResearchDiscoveryProviderName` deliberately excludes this provider: curiosity
and knowledge-gap "ask the provider(s) this run has not asked" logic must
never auto-propose asking a catalog that was never meant to answer every
question.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchQueryTerms import ResearchQueryTerms
from research.ResearchSourceCandidate import ResearchSourceCandidate

CURATED_PROVIDER_NAME = ResearchDiscoveryProviderName.CURATED.value

_MAXIMUM_LIMIT = 10


@dataclass(frozen=True, slots=True)
class _CuratedTopic:
    """One catalog entry: how a question is recognized, and what it returns."""

    #: Every one of these terms must appear for a match (order-independent).
    required_terms: frozenset[str]
    #: Any single one of these terms alone is also a match (short aliases).
    alias_terms: frozenset[str]
    candidates: tuple[ResearchSourceCandidate, ...]


#: The fixed, hand-reviewed catalog. Each URL was checked by hand to resolve
#: directly (no redirect) to a live, official page at the time it was added;
#: the fetcher still revalidates everything itself at fetch time regardless.
_CATALOG: tuple[_CuratedTopic, ...] = (
    _CuratedTopic(
        required_terms=frozenset({"sql", "injection"}),
        alias_terms=frozenset({"sqli"}),
        candidates=(
            ResearchSourceCandidate(
                url="https://portswigger.net/web-security/sql-injection",
                title="SQL injection | Web Security Academy",
                snippet=(
                    "PortSwigger Web Security Academy's topic page on SQL "
                    "injection: what it is, how it arises, and how to find "
                    "and exploit it in a lab."
                ),
                container="PortSwigger Web Security Academy",
            ),
            ResearchSourceCandidate(
                url="https://portswigger.net/web-security/sql-injection/cheat-sheet",
                title="SQL injection cheat sheet | Web Security Academy",
                snippet=(
                    "PortSwigger's reference tables of SQL injection syntax "
                    "and techniques across common database engines."
                ),
                container="PortSwigger Web Security Academy",
            ),
            ResearchSourceCandidate(
                url=(
                    "https://cheatsheetseries.owasp.org/cheatsheets/"
                    "SQL_Injection_Prevention_Cheat_Sheet.html"
                ),
                title="SQL Injection Prevention Cheat Sheet",
                snippet=(
                    "OWASP's official guidance on preventing SQL injection, "
                    "centered on parameterized queries and safe query "
                    "construction."
                ),
                container="OWASP Cheat Sheet Series",
            ),
        ),
    ),
)


class CuratedResearchSourceDiscoveryProvider:
    """Return catalog entries for a recognized topic; nothing for anything else."""

    provider_name = CURATED_PROVIDER_NAME

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        """Return at most ``limit`` fixed candidates for a catalog topic.

        No network call is made and none could be: every candidate already
        exists as a literal constant above, built before this method is ever
        called. The query only ever selects among constants; it never shapes
        one.
        """
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise ResearchError("Curated discovery query cannot be empty.")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > _MAXIMUM_LIMIT
        ):
            raise ResearchError(
                f"Curated discovery limit must be between 1 and {_MAXIMUM_LIMIT}."
            )
        topic = _matching_topic(normalized_query)
        if topic is None:
            return []
        return list(topic.candidates[:limit])


def _matching_topic(query: str) -> _CuratedTopic | None:
    """Return the one catalog topic this query names, or none at all."""
    try:
        terms = frozenset(ResearchQueryTerms.of(query).terms)
    except ResearchError:
        return None
    for topic in _CATALOG:
        if topic.alias_terms & terms or topic.required_terms <= terms:
            return topic
    return None
