"""Turn a research question into comparable terms without destroying identifiers.

Ordinary text search normalises aggressively: lowercase, strip punctuation, stem
to a root, drop short words. Every one of those steps is wrong here. `CVE-2026-12345`
becomes `cve` and three numbers, `Next.js` becomes two words, `ASP.NET` becomes
`asp` and `net`, `C++` becomes `c`, and `HTTP/2` becomes `http` and `2`. The most
specific thing a security question can contain is exactly the thing that is
destroyed first, and what survives is the generic half.

So normalisation here is deliberately shallow. Case is folded, because case is
never the difference between two identifiers. Surrounding punctuation is stripped,
because a comma after a word is not part of the word. Nothing else happens: no
stemming, no splitting on interior dots or slashes or hyphens, no dropping of
short tokens. A handful of function words are removed, from a closed list that is
checked against the token as a whole, so a listed word can never remove part of an
identifier.

Terms are also classified. A token that carries digits with letters, or an
interior dot or slash, or is written in capitals, is treated as a technical
identifier: it is far more specific than a common word, and matching it means
considerably more than matching `attack` or `analysis`.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_QUERY_TERMS = 32
MAX_TERM_LENGTH = 80

#: Words removed from a query before matching. The list is short and closed on
#: purpose: every entry is a word that carries no subject matter on its own, and
#: a longer list would eventually remove something that does.
STOP_WORDS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "what",
        "when",
        "which",
        "why",
        "with",
    }
)

#: Words that state an interest in how recent something is. Deliberately narrow.
#: `new` and `modern` are absent because `new york` and `modern cryptography` are
#: subjects, not requests for the newest result.
FRESHNESS_WORDS = frozenset(
    {
        "current",
        "currently",
        "emerging",
        "latest",
        "newest",
        "recent",
        "recently",
        "today",
        "up-to-date",
    }
)

#: Acronyms that are the vocabulary of the whole field rather than a name for
#: anything in it. `HTTP` in a web-security question is as unspecific as `web`,
#: and treating it as an identifier makes a paper that merely says `HTTP`
#: outrank one that says `request smuggling`. Closed and short, like the stop
#: words: every entry is an acronym that names a medium, not a subject.
COMMON_ACRONYMS = frozenset(
    {
        "api",
        "cpu",
        "css",
        "dns",
        "gpu",
        "html",
        "http",
        "https",
        "ip",
        "json",
        "pdf",
        "tcp",
        "udp",
        "url",
        "web",
        "xml",
    }
)

_TRIM = "\"'`,;:!?()[]{}<>«»“”‘’"
_MIN_YEAR = 1900
_MAX_YEAR = 2099


@dataclass(frozen=True, slots=True)
class ResearchQueryTerms:
    """Hold the comparable terms of one query and what they ask for."""

    terms: tuple[str, ...]
    technical_terms: frozenset[str]
    phrases: tuple[tuple[str, str], ...]
    freshness_intent: bool
    freshness_year: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.terms, tuple) or not self.terms:
            raise ResearchError("Research query terms must be a non-empty tuple.")
        if len(self.terms) > MAX_QUERY_TERMS:
            raise ResearchError("Research query terms are too many.")
        for term in self.terms:
            if not isinstance(term, str) or not term:
                raise ResearchError("Research query terms must be non-empty text.")
            if len(term) > MAX_TERM_LENGTH:
                raise ResearchError("A research query term is too long.")
        if not isinstance(self.technical_terms, frozenset):
            raise ResearchError("Research technical terms must be a frozen set.")
        if not self.technical_terms <= set(self.terms):
            raise ResearchError("A research technical term is not a query term.")
        if not isinstance(self.phrases, tuple):
            raise ResearchError("Research query phrases must be a tuple.")
        if not isinstance(self.freshness_intent, bool):
            raise ResearchError("Research freshness intent must be a boolean.")
        if self.freshness_year is not None and (
            isinstance(self.freshness_year, bool)
            or not isinstance(self.freshness_year, int)
            or not _MIN_YEAR <= self.freshness_year <= _MAX_YEAR
        ):
            raise ResearchError("A research freshness year must be a plausible year.")

    @classmethod
    def of(cls, query: str) -> ResearchQueryTerms:
        """Return the comparable terms of a query, keeping identifiers intact."""
        if not isinstance(query, str) or not query.strip():
            raise ResearchError("A research query must be text.")
        # Classification reads the written token and matching reads the folded
        # one. `JWT` and `jwt` must match each other, but only the first is
        # written as an acronym, and folding before classifying would throw that
        # away for every acronym in every query.
        written = [
            trimmed
            for token in query.split()
            if (trimmed := token.strip(_TRIM)) and len(trimmed) <= MAX_TERM_LENGTH
        ]
        if not written:
            raise ResearchError("A research query must contain a usable term.")
        technical_written = {
            token.casefold() for token in written if is_technical_term(token)
        }
        tokens = [token.casefold() for token in written]
        year = _freshness_year(tokens)
        # Freshness words and a bare year state how the results should be chosen,
        # not what they should be about. Leaving them among the subject terms
        # would penalise every title for not containing the word `latest`.
        kept = [
            token
            for token in tokens
            if token not in STOP_WORDS
            and token not in FRESHNESS_WORDS
            and not (year is not None and token == str(year))
        ]
        # Falling back to the raw tokens matters: a query made entirely of listed
        # words is a poor query, but silently ranking against nothing would be
        # worse than ranking against exactly what was asked.
        ordered = _unique(kept or tokens)[:MAX_QUERY_TERMS]
        phrases = tuple(
            (kept[index], kept[index + 1]) for index in range(len(kept) - 1)
        )[:MAX_QUERY_TERMS]
        return cls(
            terms=tuple(ordered),
            technical_terms=frozenset(technical_written & set(ordered)),
            phrases=phrases,
            freshness_intent=year is not None
            or any(token in FRESHNESS_WORDS for token in tokens),
            freshness_year=year,
        )


def is_technical_term(term: str) -> bool:
    """Say whether a term looks like an identifier rather than a common word."""
    if not isinstance(term, str) or len(term) < 2:
        return False
    if term.casefold() in COMMON_ACRONYMS:
        return False
    has_digit = any(character.isdigit() for character in term)
    has_alpha = any(character.isalpha() for character in term)
    if has_digit and has_alpha:
        return True
    interior = term[1:-1]
    if any(character in interior for character in "./#"):
        return True
    if term.endswith("++") or term.endswith("#"):
        return True
    return has_alpha and term.isupper()


def normalized_terms(value: str) -> tuple[str, ...]:
    """Return the comparable tokens of arbitrary text, folded the same way."""
    if not isinstance(value, str):
        return ()
    return tuple(
        folded for token in value.split() if (folded := token.strip(_TRIM).casefold())
    )


def _unique(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def _freshness_year(tokens: list[str]) -> int | None:
    for token in tokens:
        if len(token) == 4 and token.isdigit() and _MIN_YEAR <= int(token) <= _MAX_YEAR:
            return int(token)
    return None
