"""Bounded reasons a claim's evidence chain deserves a second look.

Every kind here is backed by one structured dimension a person recorded about a
source. None is inferred from prose: a note reading "I think this was retracted"
produces nothing, because the whole value of the structured fields is that they
say what somebody actually decided rather than what they were musing about.

None of these describes the world either. `SOURCE_RETRACTED` says a person
recorded that a publication was withdrawn from the literature. It does not say
the claim resting on it is false — retracted papers have been right and standing
papers have been wrong, and a warning that quietly meant "this is untrue" would
be a research conclusion wearing the clothes of bookkeeping.

Two of them work at different levels and are deliberately not merged.
`SOURCE_NOT_INDEPENDENT` is about one source repeating another.
`CORROBORATION_MAY_NOT_BE_INDEPENDENT` is about a claim that looks corroborated
because several sources stand behind it, when the person who read them said some
of those are the same witness twice.
"""

from __future__ import annotations

from enum import StrEnum


class AssessmentWarningKind(StrEnum):
    """Name one bounded concern raised by a recorded human judgement."""

    SOURCE_RETRACTED = "source_retracted"
    SOURCE_WITHDRAWN = "source_withdrawn"
    SOURCE_CORRECTED = "source_corrected"
    SOURCE_NOT_USEFUL = "source_not_useful"
    SOURCE_UNRELATED = "source_unrelated"
    SOURCE_BACKGROUND_ONLY = "source_background_only"
    SOURCE_NOT_INDEPENDENT = "source_not_independent"
    CORROBORATION_MAY_NOT_BE_INDEPENDENT = "corroboration_may_not_be_independent"

    @property
    def order(self) -> int:
        """Return the report position, lower meaning reported earlier."""
        return _ORDER[self]


#: Report order. Withdrawal of the publication comes first because it is the one
#: a person most needs to see before citing anything; a judgement that a source
#: was merely background comes last because it is the mildest thing on the list.
_ORDER = {
    AssessmentWarningKind.SOURCE_RETRACTED: 0,
    AssessmentWarningKind.SOURCE_WITHDRAWN: 1,
    AssessmentWarningKind.SOURCE_UNRELATED: 2,
    AssessmentWarningKind.SOURCE_NOT_USEFUL: 3,
    AssessmentWarningKind.CORROBORATION_MAY_NOT_BE_INDEPENDENT: 4,
    AssessmentWarningKind.SOURCE_NOT_INDEPENDENT: 5,
    AssessmentWarningKind.SOURCE_CORRECTED: 6,
    AssessmentWarningKind.SOURCE_BACKGROUND_ONLY: 7,
}
