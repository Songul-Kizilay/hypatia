"""Order discovered candidates by how well they match the question that found them.

Deterministic relevance ranking, and the name is meant literally. This compares
the words of a query against the words of a record: which terms appear in the
title, whether any of them are identifiers rather than common words, whether two
query words appear next to each other, whether the venue mentions the subject,
and — only when the question asked for recent work — how the publication years
compare within this one set of results. Nothing is inferred, nothing is
generated, and nothing is learned.

That means there is no model in this path. Not an optional one, not a fallback
one: ranking runs with no key configured, no endpoint reachable, and no
inference budget, and it returns the same order every time for the same inputs.
It also costs nothing to spend, because it reads records that were already
fetched. A ranking that needed permission to run would be a ranking a person
skips, and a ranking a person skips is provider order wearing a better name.

Two limits are worth stating rather than discovering. Matching is lexical: a
paper about the same vulnerability under a different name will not score for the
name it does not use, so a low score is a reason to look further down, not proof
that nothing below is relevant. And relevance is not truth — the strongest match
in a set can be the least reliable document in it, and this layer has no opinion
about that, by design.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.Exceptions import ResearchError
from research.RankedResearchSourceCandidate import RankedResearchSourceCandidate
from research.ResearchQueryTerms import ResearchQueryTerms, normalized_terms
from research.ResearchRelevanceComponent import ResearchRelevanceComponent
from research.ResearchRelevanceReason import ResearchRelevanceReason
from research.ResearchRelevanceWeights import (
    DEFAULT_RELEVANCE_WEIGHTS,
    ResearchRelevanceWeights,
)
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceRelevance import ResearchSourceRelevance
from research.SourceIdentity import identity_of

MAX_RANKED_CANDIDATES = 10

TITLE_COVERAGE = "title_coverage"
PHRASE_ADJACENCY = "phrase_adjacency"
VENUE_TERMS = "venue_terms"
RECENCY = "recency"


class ResearchSourceRelevanceRanker:
    """Rank candidates against a query using only the words both already have."""

    def __init__(
        self,
        weights: ResearchRelevanceWeights = DEFAULT_RELEVANCE_WEIGHTS,
    ) -> None:
        if not isinstance(weights, ResearchRelevanceWeights):
            raise ResearchError("Relevance weights are invalid.")
        self._weights = weights

    @property
    def weights(self) -> ResearchRelevanceWeights:
        """Return the fixed weights this ranker scores with."""
        return self._weights

    def rank(
        self,
        query: str,
        candidates: Sequence[ResearchSourceCandidate],
    ) -> tuple[RankedResearchSourceCandidate, ...]:
        """Return the candidates in relevance order, each keeping its origin."""
        if not isinstance(candidates, (list, tuple)):
            raise ResearchError("Research candidates must be an ordered sequence.")
        if len(candidates) > MAX_RANKED_CANDIDATES:
            raise ResearchError("Too many research candidates to rank.")
        if not all(
            isinstance(candidate, ResearchSourceCandidate) for candidate in candidates
        ):
            raise ResearchError("A research candidate is invalid.")
        if not candidates:
            return ()
        terms = ResearchQueryTerms.of(query)
        oldest, newest = _year_span(candidates)

        scored: list[
            tuple[ResearchSourceCandidate, int, ResearchSourceRelevance, int | None]
        ] = []
        seen: dict[str, int] = {}
        for position, candidate in enumerate(candidates, start=1):
            identity = identity_of(candidate.url)
            duplicate_of = seen.get(identity)
            if duplicate_of is None:
                seen[identity] = position
            components, reasons = self._measure(
                candidate,
                terms,
                oldest=oldest,
                newest=newest,
                duplicate=duplicate_of is not None,
            )
            scored.append(
                (
                    candidate,
                    position,
                    ResearchSourceRelevance.of(components, reasons, self._weights),
                    duplicate_of,
                )
            )

        # Duplicates sort last regardless of score. They are kept, because a
        # second record of one resource is how a provider's answer gets checked,
        # but a repeat of something already listed is never the better thing to
        # read next. Ties fall back to the provider's own order, so the ordering
        # is total and stable rather than dependent on sort implementation.
        order = sorted(
            scored,
            key=lambda entry: (entry[3] is not None, -entry[2].score, entry[1]),
        )
        return tuple(
            RankedResearchSourceCandidate(
                candidate=candidate,
                provider_rank=provider_rank,
                relevance_rank=relevance_rank,
                relevance=relevance,
                duplicate_of_rank=duplicate_of,
            )
            for relevance_rank, (candidate, provider_rank, relevance, duplicate_of) in (
                enumerate(order, start=1)
            )
        )

    def _weighted_share(
        self,
        matched: list[str],
        terms: ResearchQueryTerms,
    ) -> float:
        """Return how much of the question these terms cover, by specificity."""
        total = sum(self._term_weight(term, terms) for term in terms.terms)
        if total <= 0.0:
            return 0.0
        return sum(self._term_weight(term, terms) for term in matched) / total

    def _term_weight(self, term: str, terms: ResearchQueryTerms) -> float:
        return (
            self._weights.technical_term_specificity
            if term in terms.technical_terms
            else 1.0
        )

    def _measure(
        self,
        candidate: ResearchSourceCandidate,
        terms: ResearchQueryTerms,
        *,
        oldest: int | None,
        newest: int | None,
        duplicate: bool,
    ) -> tuple[
        tuple[ResearchRelevanceComponent, ...], tuple[ResearchRelevanceReason, ...]
    ]:
        title_tokens = normalized_terms(candidate.title)
        title_set = set(title_tokens)
        reasons: list[ResearchRelevanceReason] = []

        # Coverage is weighted by specificity rather than counted. A title that
        # matches `analysis`, `remote` and `code` has covered three words of the
        # question; a title that matches `CVE-2026-12345` has covered the
        # question. Counting both as fractions of five makes the first one win.
        matched = [term for term in terms.terms if _matched(term, title_set)]
        coverage = self._weighted_share(matched, terms)
        if len(matched) == len(terms.terms):
            reasons.append(ResearchRelevanceReason.ALL_QUERY_TERMS_IN_TITLE)
        elif matched:
            reasons.append(ResearchRelevanceReason.SOME_QUERY_TERMS_IN_TITLE)
        else:
            reasons.append(ResearchRelevanceReason.NO_QUERY_TERM_IN_TITLE)

        # Identifiers are reported but not scored a second time. Their weight is
        # already inside coverage, and measuring them again as their own
        # component was enough on its own to lift a paper that shared only the
        # framework name above the papers about the actual attack.
        if terms.technical_terms:
            reasons.append(
                ResearchRelevanceReason.TECHNICAL_IDENTIFIER_MATCHED
                if any(term in matched for term in terms.technical_terms)
                else ResearchRelevanceReason.TECHNICAL_IDENTIFIER_MISSING
            )

        phrase_applicable = bool(terms.phrases)
        phrase_value = 0.0
        if phrase_applicable:
            adjacent = sum(
                1 for phrase in terms.phrases if _adjacent(phrase, title_tokens)
            )
            phrase_value = adjacent / len(terms.phrases)
            if adjacent:
                reasons.append(ResearchRelevanceReason.QUERY_PHRASE_IN_TITLE)

        # The venue only ever adds. A journal named after the subject is weak
        # evidence that a paper is about it, but a journal *not* named after the
        # subject is no evidence at all — most serious work on request smuggling
        # appears in venues called `USENIX Security`, and subtracting for that
        # would systematically favour narrowly named journals over the places
        # the good work is actually published.
        venue_hits: list[str] = []
        if candidate.container.strip():
            venue_set = set(normalized_terms(candidate.container))
            venue_hits = [term for term in terms.terms if _matched(term, venue_set)]
        venue_applicable = bool(venue_hits)
        venue_value = (
            self._weighted_share(venue_hits, terms) if venue_applicable else 0.0
        )
        if venue_applicable:
            reasons.append(ResearchRelevanceReason.QUERY_TERM_IN_VENUE)

        recency_value, recency_applicable, recency_reason = _recency(
            candidate.published_year,
            terms,
            oldest=oldest,
            newest=newest,
        )
        if recency_reason is not None:
            reasons.append(recency_reason)

        if duplicate:
            reasons.append(ResearchRelevanceReason.SAME_RESOURCE_AS_EARLIER_RESULT)

        components = (
            ResearchRelevanceComponent(
                name=TITLE_COVERAGE,
                value=coverage,
                weight=self._weights.title_coverage,
                applicable=True,
            ),
            ResearchRelevanceComponent(
                name=PHRASE_ADJACENCY,
                value=phrase_value if phrase_applicable else 0.0,
                weight=self._weights.phrase_adjacency,
                applicable=phrase_applicable,
            ),
            ResearchRelevanceComponent(
                name=VENUE_TERMS,
                value=venue_value if venue_applicable else 0.0,
                weight=self._weights.venue_terms,
                applicable=venue_applicable,
            ),
            ResearchRelevanceComponent(
                name=RECENCY,
                value=recency_value,
                weight=self._weights.recency,
                applicable=recency_applicable,
            ),
        )
        return components, tuple(reasons)


def _matched(term: str, tokens: set[str]) -> bool:
    """Say whether a query term appears among a record's tokens.

    Equality, plus the one variation that is safe to allow: a trailing plural on
    a word that is not an identifier. Nothing is stemmed to a root, because a
    root is where `injection` and `injector` become the same word and where
    `next.js` becomes `next`.
    """
    if term in tokens:
        return True
    if any(character.isdigit() for character in term) or not term.isalpha():
        return False
    return any(candidate in tokens for candidate in (term + "s", term + "es")) or any(
        term == token.removesuffix("s") or term == token.removesuffix("es")
        for token in tokens
        if token.isalpha()
    )


def _adjacent(phrase: tuple[str, str], tokens: tuple[str, ...]) -> bool:
    first, second = phrase
    return any(
        _matched(first, {tokens[index]}) and _matched(second, {tokens[index + 1]})
        for index in range(len(tokens) - 1)
    )


def _year_span(
    candidates: Sequence[ResearchSourceCandidate],
) -> tuple[int | None, int | None]:
    years = [
        candidate.published_year
        for candidate in candidates
        if candidate.published_year is not None
    ]
    return (min(years), max(years)) if years else (None, None)


def _recency(
    year: int | None,
    terms: ResearchQueryTerms,
    *,
    oldest: int | None,
    newest: int | None,
) -> tuple[float, bool, ResearchRelevanceReason | None]:
    """Score recency only when it was asked for, and only within this result set.

    Newer is not more relevant. It is more relevant when the question asked for
    what is current, and it is the wrong thing to reward otherwise: the paper
    that first described an attack is usually the oldest result and usually the
    one worth reading. So with no freshness intent this component does not
    apply at all.

    When it does apply, it is measured against the other results rather than
    against today. That keeps the ranker free of a clock — the same inputs give
    the same order next year — and it answers the question a person actually has
    while looking at a list, which is which of these is the recent one.
    """
    if not terms.freshness_intent:
        return 0.0, False, ResearchRelevanceReason.RECENCY_NOT_REQUESTED
    if year is None:
        return 0.0, False, ResearchRelevanceReason.PUBLICATION_YEAR_UNKNOWN
    if oldest is None or newest is None or newest <= oldest:
        return 0.0, False, None
    value = (year - oldest) / (newest - oldest)
    return (
        value,
        True,
        (
            ResearchRelevanceReason.NEWER_THAN_OTHER_RESULTS
            if value > 0.5
            else ResearchRelevanceReason.OLDER_THAN_OTHER_RESULTS
        ),
    )
