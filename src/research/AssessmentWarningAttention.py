"""How hard a warning is asking to be looked at.

Three levels, and deliberately not a number. A score invites arithmetic — adding
two mediums into a high, averaging four warnings into a claim-level rating — and
none of that arithmetic would mean anything, because these are not measurements.
They are a person's recorded judgements, sorted by how much trouble ignoring one
tends to cause.

`SecurityFindingSeverity` was not reused, though it has a similar shape. It
grades violations of a security property found by auditing persisted state, and
borrowing it here would quietly assert that a source somebody found unhelpful is
a security finding. Different question, different vocabulary.

Nothing acts on these. The highest level still only means a person should look.
"""

from __future__ import annotations

from enum import StrEnum


class AssessmentWarningAttention(StrEnum):
    """Say how much a recorded judgement is asking a person to look again."""

    INFO = "info"
    REVIEW = "review"
    HIGH_ATTENTION = "high_attention"

    @property
    def rank(self) -> int:
        """Return the ordering weight, higher meaning more pressing."""
        return _RANK[self]


_RANK = {
    AssessmentWarningAttention.INFO: 0,
    AssessmentWarningAttention.REVIEW: 1,
    AssessmentWarningAttention.HIGH_ATTENTION: 2,
}
