"""How far a source actually bears on the question this run is asking.

This is the human counterpart to lexical relevance, and it is kept in a separate
vocabulary precisely so it can disagree with one. The ranker says the question's
words appear in the title. This says whether a person who read the thing thinks
it answers the question. Those disagree often, and the disagreement is the
useful part: a title that matches every word while being about something else is
the failure mode the ranking cannot see, and a person can.

Nothing here reorders anything. Recording `unrelated` about a source the ranker
put first leaves it first, and the two answers are displayed side by side rather
than reconciled, because reconciling them would throw away whichever one was
inconvenient.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSourceApplicability(StrEnum):
    """Say how directly a source bears on this run's question."""

    UNKNOWN = "unknown"
    DIRECT = "direct"
    PARTIAL = "partial"
    BACKGROUND_ONLY = "background_only"
    UNRELATED = "unrelated"
