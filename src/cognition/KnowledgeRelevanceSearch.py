"""Rank knowledge chunks by shared query terms, not a single whole-string match.

`KnowledgeEngine.search()` (`knowledge.Search.find`) requires the *entire*
casefolded query to appear verbatim as one substring of a chunk's content.
That is the right contract for an exact lookup, but it silently makes
`ask_knowledge` unusable for its intended purpose -- answering an ordinary
question from researched material -- because a natural question ("How does
UNION-based SQL injection work?") is almost never a source's own exact
wording, even when that source plainly answers it.

This does not change `Search` or its existing callers at all; it is a
second, additive way to find relevant chunks, used by `ask_knowledge`.
Ordinary chat uses the separate, stricter `rank_chunks_for_conversation` below.
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

import re
from collections.abc import Sequence

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from knowledge.KnowledgeContextPrompt import MAX_CHARS_PER_KNOWLEDGE_CONTEXT_RESULT
from research.ResearchQueryTerms import STOP_WORDS, ResearchQueryTerms

_MINIMUM_SIGNIFICANT_TERM_LENGTH = 3

# Only automatic conversation grounding uses this stricter policy. Keep the
# explicit ask_knowledge/research query contracts unchanged.
_CONVERSATION_FILLER = frozenset(
    "you your yours yourself we our ours they their them me my mine myself "
    "he she his her its this that these those there here please help find "
    "tell explain describe show give want need know learn understand "
    "could would should will have has had am been being did doing "
    "some any something anything everything nothing thanks thank hello hi "
    "good morning evening doing let's lets about more much many "
    "used use work works difference between compare versus vs simply "
    "bana benim sen senin siz sizin biz bizim bir bu şu o ve ile için "
    "nedir nasıl anlat açıkla lütfen yardım eder misin hakkında".split()
)


def rank_chunks_for_conversation(
    chunks: Sequence[Chunk], query: str, *, max_results: int
) -> list[Chunk]:
    """Conservatively ground chat only when all residual terms are covered.

    Whole-term matches avoid `union` matching `reunion`. Coverage is checked
    across the bounded selected excerpts, allowing SQL injection/XSS comparisons
    while refusing a casual request whose subject (e.g. lost keys) is absent.
    This is lexical evidence selection, not semantic understanding: paraphrases
    can fall back to ordinary chat. No model or external lookup decides relevance.
    Each selected excerpt must add coverage; a complete SQLi result must not
    also cite XSS merely because both mention user data or query output.
    """
    if max_results <= 0:
        return []
    try:
        # A sentence-final period is punctuation, not part of an identifier.
        parsed = ResearchQueryTerms.of(query.rstrip().rstrip(".!?"))
    except ResearchError:
        return []
    terms = tuple(
        term for term in _significant_terms(parsed) if term not in _CONVERSATION_FILLER
    )
    if not terms:
        return []
    patterns = [re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)") for term in terms]
    scored = [
        (
            frozenset(
                i
                for i, pattern in enumerate(patterns)
                if pattern.search(
                    chunk.content[:MAX_CHARS_PER_KNOWLEDGE_CONTEXT_RESULT].casefold()
                )
            ),
            chunk,
        )
        for chunk in chunks
    ]
    relevant = [(matched, chunk) for matched, chunk in scored if matched]
    relevant.sort(key=lambda pair: len(pair[0]), reverse=True)
    selected: list[Chunk] = []
    covered: frozenset[int] = frozenset()
    for matched, chunk in relevant:
        if not matched - covered:
            continue
        selected.append(chunk)
        covered = covered | matched
        if len(covered) == len(terms) or len(selected) == max_results:
            break
    if len(covered) != len(terms):
        return []
    return selected


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
