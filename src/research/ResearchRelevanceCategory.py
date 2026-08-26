"""How closely a discovered candidate matches the question that found it.

Four bands rather than a bare number, because a number invites arithmetic that
the number cannot support. A score of 62 is not twice as relevant as 31, and
nothing downstream should be able to multiply, average, or threshold these
values into a judgement about whether the source is *true*.

Relevance is the only thing this vocabulary describes: whether the words of the
question appear in the record of the source. It says nothing about whether the
publication is reputable, whether its claims hold, whether anything corroborates
it, or how much confidence any conclusion drawn from it deserves. Those are
separate questions with separate answers elsewhere, and collapsing them into one
number is how a well-matched title starts to read as a well-established fact.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchRelevanceCategory(StrEnum):
    """Say how well a candidate matched the query, and nothing more."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    UNRELATED = "unrelated"
    #: Nothing was compared. A query that could not be reduced to terms leaves
    #: the results in the order the provider chose, and saying `unrelated`
    #: about them would be a judgement that was never actually made.
    UNMEASURED = "unmeasured"
