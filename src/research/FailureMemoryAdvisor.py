"""Surface prior lessons that might bear on a new question. Advisory only.

Recall is the point of remembering failures, and it is also where a failure
memory turns dangerous. A system that blocks work because something similar went
wrong once has stopped researching and started superstition, so nothing here
blocks anything. It returns lessons for a person to read, ranked and bounded,
and the caller is free to ignore every one.

Matching is deliberately dumb: shared words between the new question and the
lesson's own wording, weighted by how much the lesson kind is worth
remembering. Recency breaks only an otherwise exact tie. A smarter matcher
would be a model deciding which past failures apply to present work, which is
exactly the kind of confident, unauditable judgement this project keeps out of
the loop.

Dumb is not the same as indiscriminate. Every lesson carries some shared
vocabulary simply by being a lesson, so a single overlapping word says almost
nothing: an unrelated question about error-correction thresholds matched a
hypothesis about planetary rings on the word "evidence" alone. Two words is
still a crude test, but it is a test. Advice nobody trusts is worse than no
advice, because it teaches people to skip the part that was worth reading.
"""

from __future__ import annotations

from collections.abc import Iterable

from research.FailureMemoryRecallMatch import FailureMemoryRecallMatch
from research.FailureMemoryTokens import failure_memory_tokens
from research.ResearchFailureLesson import ResearchFailureLesson

DEFAULT_RECALL_LIMIT = 5
MAX_RECALL_LIMIT = 20
MIN_SHARED_TOKENS = 2


class FailureMemoryAdvisor:
    """Rank remembered lessons against a new question, deciding nothing."""

    def __init__(self, limit: int = DEFAULT_RECALL_LIMIT) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("Failure recall limit must be a whole number.")
        if limit < 1 or limit > MAX_RECALL_LIMIT:
            raise ValueError("Failure recall limit is out of range.")
        self._limit = limit

    def relevant(
        self,
        question: str,
        lessons: Iterable[ResearchFailureLesson],
    ) -> tuple[ResearchFailureLesson, ...]:
        """Return lessons sharing wording with the question, heaviest first."""
        return tuple(match.lesson for match in self.matches(question, lessons))

    def matches(
        self,
        question: str,
        lessons: Iterable[ResearchFailureLesson],
    ) -> tuple[FailureMemoryRecallMatch, ...]:
        """Return selected lessons with their exact normalized shared terms."""
        wanted = failure_memory_tokens(question)
        if not wanted:
            return ()
        scored: list[tuple[int, int, ResearchFailureLesson, tuple[str, ...]]] = []
        for lesson in lessons:
            shared_terms = tuple(sorted(wanted & lesson.tokens()))
            if len(shared_terms) < MIN_SHARED_TOKENS:
                continue
            scored.append((len(shared_terms), lesson.weight, lesson, shared_terms))
        # Stable passes keep the final lesson-ID tie-break deterministic while
        # making overlap, kind weight, and then recency descend in that order.
        scored.sort(key=lambda entry: entry[2].lesson_id)
        scored.sort(key=lambda entry: entry[2].recorded_at, reverse=True)
        scored.sort(key=lambda entry: entry[1], reverse=True)
        scored.sort(key=lambda entry: entry[0], reverse=True)
        return tuple(
            FailureMemoryRecallMatch(
                lesson=entry[2],
                shared_terms=entry[3],
            )
            for entry in scored[: self._limit]
        )
