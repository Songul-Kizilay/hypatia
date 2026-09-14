"""Exact transient quotations proposed by a bounded local keyword matcher."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.ResearchSourcePreview import ResearchSourcePreview

MAX_PASSAGE_CHARACTERS = 800
MAX_PASSAGE_PROPOSALS = 20
_WORDS = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ResearchPassageProposal:
    """Offsets are Python character indices in the exact extracted source text.

    These are not original HTML/PDF byte offsets. Quotation identity is tied to
    the preview's extracted-text digest, not merely to the source URL.
    """

    preview: ResearchSourcePreview = field(repr=False)
    start: int
    end: int
    matched_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.preview, ResearchSourcePreview)
            or type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end <= len(self.preview.source.content)
            or self.end - self.start > MAX_PASSAGE_CHARACTERS
        ):
            raise ResearchError("Passage source range is invalid.")
        terms = set(_WORDS.findall(self.quote.casefold()))
        if (
            not isinstance(self.matched_terms, tuple)
            or not self.matched_terms
            or any(
                not isinstance(term, str) or term not in terms
                for term in self.matched_terms
            )
            or tuple(sorted(set(self.matched_terms))) != self.matched_terms
        ):
            raise ResearchError("Passage matched terms are invalid.")

    @property
    def quote(self) -> str:
        return self.preview.source.content[self.start : self.end]


def propose_passages(
    question: str, previews: tuple[ResearchSourcePreview, ...], *, limit: int = 10
) -> tuple[ResearchPassageProposal, ...]:
    """Rank exact line/window spans by distinct keyword overlap, not confidence.

    No stemming, semantic inference, instruction execution, storage or model call.
    Return no proposals when there is no match. Long lines are split into bounded
    windows; adjacent words can be split, a disclosed lexical matching limitation.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ResearchError("Enter a question or keywords of at most 2,000 characters.")
    if type(limit) is not int or not 1 <= limit <= MAX_PASSAGE_PROPOSALS:
        raise ResearchError("Passage proposal limit must be between 1 and 20.")
    if (
        not isinstance(previews, tuple)
        or len(previews) > 10
        or any(not isinstance(p, ResearchSourcePreview) for p in previews)
        or len({(p.execution_id, p.run_id) for p in previews}) > 1
        or len({p.step_id for p in previews}) != len(previews)
    ):
        raise ResearchError("Passage proposals require one bounded acquisition batch.")
    query_terms = {
        term for term in _WORDS.findall(question.casefold()) if len(term) >= 3
    }
    if not query_terms:
        return ()
    ranked: list[tuple[int, int, int, ResearchPassageProposal]] = []
    for source_index, preview in enumerate(previews):
        text = preview.source.content
        for line in re.finditer(r"[^\r\n]+", text):
            for start in range(line.start(), line.end(), MAX_PASSAGE_CHARACTERS):
                end = min(start + MAX_PASSAGE_CHARACTERS, line.end())
                terms = tuple(
                    sorted(
                        query_terms & set(_WORDS.findall(text[start:end].casefold()))
                    )
                )
                if not terms:
                    continue
                proposal = ResearchPassageProposal(preview, start, end, terms)
                ranked.append((-len(terms), source_index, start, proposal))
                # Retain only bounded top results even for many short lines.
                ranked.sort(key=lambda entry: entry[:3])
                del ranked[limit:]
    return tuple(entry[3] for entry in ranked)
