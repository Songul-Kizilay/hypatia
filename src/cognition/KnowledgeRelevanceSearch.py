"""Rank knowledge chunks by shared query terms, not a single whole-string match.

`KnowledgeEngine.search()` (`knowledge.Search.find`) requires the *entire*
casefolded query to appear verbatim as one substring of a chunk's content.
That is the right contract for an exact lookup, but it silently makes
`ask_knowledge` unusable for its intended purpose -- answering an ordinary
question from researched material -- because a natural question ("How does
UNION-based SQL injection work?") is almost never a source's own exact
wording, even when that source plainly answers it.

This does not change `Search` or its existing callers at all; it is a
second, additive way to find relevant chunks, used only by `ask_knowledge`.
It reuses the same bounded, identifier-preserving `ResearchQueryTerms`
tokenizer NVD's keyword route and the curated discovery provider already
use, so "UNION-based", "ASP.NET" and similar technical terms survive intact
rather than being split into generic words. A chunk matches when it shares
at least one *significant* query term; chunks sharing more terms rank first.

A term counts as significant only if it is a recognised technical
identifier, or is at least three characters and not one of
`ResearchQueryTerms.STOP_WORDS`. This is a second, stricter filter than
`ResearchQueryTerms.of()` itself applies: that tokenizer deliberately falls
back to a query's raw, unfiltered tokens when every token is a stop word
(a sparse query is still ranked against exactly what was asked, which is
the right default for its own callers). Ranking chunks by *substring
containment* is not that case -- a short stop word like "is" or "it" is a
substring of a huge fraction of ordinary prose, so without this filter a
content-free query such as "What is it?" would spuriously "match" chunks
that share no actual subject with it, and `ask_knowledge` would present an
unrelated chunk as grounded evidence. A query with no significant term
matches nothing -- the same honest "found nothing" `ask_knowledge` already
reports for a query that has no answer, never a guess.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchQueryTerms import STOP_WORDS, ResearchQueryTerms

_MINIMUM_SIGNIFICANT_TERM_LENGTH = 3


def rank_chunks_by_term_relevance(
    chunks: Sequence[Chunk],
    query: str,
) -> list[Chunk]:
    """Return chunks sharing at least one significant term, most shared first.

    A stable sort keyed only on the match count, so chunks that tie keep
    their original relative order -- the result is deterministic for an
    unchanged index and an unchanged query, never dependent on dict/set
    iteration order.
    """
    try:
        parsed = ResearchQueryTerms.of(query)
    except ResearchError:
        return []
    significant_terms = _significant_terms(parsed)
    if not significant_terms:
        return []
    scored = [(_shared_term_count(chunk, significant_terms), chunk) for chunk in chunks]
    relevant = [(score, chunk) for score, chunk in scored if score > 0]
    relevant.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _score, chunk in relevant]


def _significant_terms(parsed: ResearchQueryTerms) -> tuple[str, ...]:
    technical = parsed.technical_terms
    return tuple(
        dict.fromkeys(
            term
            for term in parsed.terms
            if term not in STOP_WORDS
            and (term in technical or len(term) >= _MINIMUM_SIGNIFICANT_TERM_LENGTH)
        )
    )


def _shared_term_count(chunk: Chunk, significant_terms: tuple[str, ...]) -> int:
    folded_content = chunk.content.casefold()
    return sum(1 for term in significant_terms if term in folded_content)
