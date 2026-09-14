"""One claim, one source, and the recorded judgement that makes the pair worth checking.

Derived and never stored. Everything a warning says can be recomputed from the
claims, the evidence, the sources, and the current assessments, so persisting it
would create a second copy of the truth that could drift from the first and then
be believed. It also means revising an assessment simply changes the warnings:
mark a source retracted and the warning appears, supersede that with `normal`
and it is gone, with no stale record anywhere claiming otherwise.

Identity is derived for the same reason. A warning is the claim, the source, and
the kind — three things that already exist — so two runs of the calculation over
unchanged state produce warnings that compare equal instead of two rows that
merely look alike.

The grouping is per source rather than per evidence record. A claim resting on
four excerpts from one retracted paper has one problem, not four, and four
identical warnings would bury the claim resting on four different retracted
papers, which is a much worse situation.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.AssessmentWarningAttention import AssessmentWarningAttention
from research.AssessmentWarningKind import AssessmentWarningKind

MAX_WARNING_EVIDENCE_IDS = 100


@dataclass(frozen=True, slots=True)
class ResearchAssessmentWarning:
    """Report that one claim rests on a source somebody judged concerning."""

    claim_id: str
    kind: AssessmentWarningKind
    attention: AssessmentWarningAttention
    source_document_id: str = ""
    assessment_id: str = ""
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.claim_id, str) or not self.claim_id.strip():
            raise ResearchError("An assessment warning requires a claim ID.")
        if not isinstance(self.kind, AssessmentWarningKind):
            raise ResearchError("An assessment warning kind must be a known code.")
        if not isinstance(self.attention, AssessmentWarningAttention):
            raise ResearchError("An assessment warning attention level is invalid.")
        for value, label in (
            (self.source_document_id, "source document ID"),
            (self.assessment_id, "assessment ID"),
        ):
            if not isinstance(value, str):
                raise ResearchError(f"An assessment warning {label} must be text.")
        if not isinstance(self.evidence_ids, tuple):
            raise ResearchError("Assessment warning evidence IDs must be a tuple.")
        if len(self.evidence_ids) > MAX_WARNING_EVIDENCE_IDS:
            raise ResearchError("An assessment warning names too much evidence.")
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ResearchError("An assessment warning evidence ID is invalid.")
        # A warning about one source has to name it. The claim-level warning
        # about corroboration deliberately names none, because it is about the
        # shape of the whole set rather than about any single member.
        names_a_source = self.kind is not (
            AssessmentWarningKind.CORROBORATION_MAY_NOT_BE_INDEPENDENT
        )
        if names_a_source and not self.source_document_id.strip():
            raise ResearchError("This assessment warning must name its source.")
        object.__setattr__(self, "claim_id", self.claim_id.strip())
        object.__setattr__(self, "source_document_id", self.source_document_id.strip())
        object.__setattr__(self, "assessment_id", self.assessment_id.strip())

    @property
    def identity(self) -> tuple[str, str, str]:
        """Return the derived identity: this claim, this source, this concern."""
        return (self.claim_id, self.source_document_id, self.kind.value)

    def summary(self) -> str:
        """Render the warning in one bounded line that changes nothing."""
        subject = (
            f"source {self.source_document_id}"
            if self.source_document_id
            else "the sources behind this claim"
        )
        return (
            f"[{self.attention.value}] {self.kind.value}: claim {self.claim_id} "
            f"rests on {subject} ({len(self.evidence_ids)} evidence record(s))"
        )
