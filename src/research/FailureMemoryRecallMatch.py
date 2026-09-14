"""Explain why one remembered failure was recalled for a question.

The match is a read-only lexical trace, not evidence that the old lesson
applies to the new work.  It carries the lesson already selected by the
existing advisor together with the exact normalized terms shared with the
question; it grants no authority and changes no ranking or research state.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.ResearchFailureLesson import ResearchFailureLesson


@dataclass(frozen=True, slots=True)
class FailureMemoryRecallMatch:
    """One selected lesson and the lexical overlap that selected it."""

    lesson: ResearchFailureLesson
    shared_terms: tuple[str, ...]
