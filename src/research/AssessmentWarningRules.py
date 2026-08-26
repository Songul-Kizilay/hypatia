"""The closed table that turns a recorded judgement into a warning, or into nothing.

Every rule is a lookup. There is no scoring, no threshold, no accumulation, and
nothing a model contributes: a dimension either has a value that concerns us or
it does not, and the same stored state produces the same warnings on any machine
with nothing configured.

The table is mostly empty on purpose. `unknown` never warns, because absence of
a judgement is not a negative judgement — most sources are never appraised, and a
system that treated silence as a complaint would bury the sources somebody
actually looked at and disliked. `useful`, `direct`, `independent` and `normal`
never warn either, for the same reason in reverse: a person saying a source was
fine is not a reason to keep asking about it.

`partially_useful` and `partial` are absent as well. They mean the person got
something out of it, and warning about a source that partly worked would make
the honest middle answer more expensive to record than the flattering one.
"""

from __future__ import annotations

from research.AssessmentWarningAttention import AssessmentWarningAttention
from research.AssessmentWarningKind import AssessmentWarningKind
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness

#: The publication was pulled or amended. Retraction and withdrawal are the two
#: strongest signals anywhere in this file, because they are the only ones where
#: the literature itself, and not only our reader, has changed its mind.
PUBLICATION_RULES = {
    ResearchSourcePublicationStatus.RETRACTED: (
        AssessmentWarningKind.SOURCE_RETRACTED,
        AssessmentWarningAttention.HIGH_ATTENTION,
    ),
    ResearchSourcePublicationStatus.WITHDRAWN: (
        AssessmentWarningKind.SOURCE_WITHDRAWN,
        AssessmentWarningAttention.HIGH_ATTENTION,
    ),
    #: A correction is not a retraction. The paper still stands; some part of it
    #: changed, and whoever leaned on it should check which part.
    ResearchSourcePublicationStatus.CORRECTED: (
        AssessmentWarningKind.SOURCE_CORRECTED,
        AssessmentWarningAttention.INFO,
    ),
}

USEFULNESS_RULES = {
    ResearchSourceUsefulness.NOT_USEFUL: (
        AssessmentWarningKind.SOURCE_NOT_USEFUL,
        AssessmentWarningAttention.REVIEW,
    ),
}

#: `unrelated` is the sharper of the two: somebody read the thing and concluded
#: it is not about this question, while a claim continues to rest on it.
APPLICABILITY_RULES = {
    ResearchSourceApplicability.UNRELATED: (
        AssessmentWarningKind.SOURCE_UNRELATED,
        AssessmentWarningAttention.REVIEW,
    ),
    ResearchSourceApplicability.BACKGROUND_ONLY: (
        AssessmentWarningKind.SOURCE_BACKGROUND_ONLY,
        AssessmentWarningAttention.INFO,
    ),
}

INDEPENDENCE_RULES = {
    ResearchSourceIndependence.DERIVATIVE: (
        AssessmentWarningKind.SOURCE_NOT_INDEPENDENT,
        AssessmentWarningAttention.REVIEW,
    ),
    ResearchSourceIndependence.LIKELY_DUPLICATE: (
        AssessmentWarningKind.SOURCE_NOT_INDEPENDENT,
        AssessmentWarningAttention.REVIEW,
    ),
}

#: Raised once for a claim that several sources appear to corroborate when at
#: least one of them was judged to be repeating another. The count is what makes
#: it worth saying separately: two witnesses and one witness twice look
#: identical from the outside, and only a reader can tell them apart.
CORROBORATION_RULE = (
    AssessmentWarningKind.CORROBORATION_MAY_NOT_BE_INDEPENDENT,
    AssessmentWarningAttention.REVIEW,
)
