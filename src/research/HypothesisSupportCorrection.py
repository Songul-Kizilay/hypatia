"""Project source-assessment corrections that timed support lived through.

This is provenance work, not hypothesis judgement. It compares two records an
operator explicitly linked through ``supersedes_assessment_id`` and reports the
link only when the current supporting relation was already standing. It does
not decide whether the hypothesis is true, whether the source is trustworthy,
or whether one independence label is better than another.

Legacy supporting relations have no recorded authoring time. Their sequence
cannot be reconstructed honestly, so they produce no projected correction.
Parallel assessments are disagreements, not corrections, and are excluded too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchRun import ResearchRun
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceIndependence import ResearchSourceIndependence


@dataclass(frozen=True, slots=True)
class HypothesisSupportCorrection:
    """One explicit source correction with checkable hypothesis provenance."""

    evidence_id: str
    source_document_id: str
    earlier_assessment_id: str
    later_assessment_id: str
    earlier_independence: ResearchSourceIndependence
    later_independence: ResearchSourceIndependence

    def __post_init__(self) -> None:
        for label, value in (
            ("Evidence ID", self.evidence_id),
            ("Source document ID", self.source_document_id),
            ("Earlier assessment ID", self.earlier_assessment_id),
            ("Later assessment ID", self.later_assessment_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{label} cannot be empty.")
            object.__setattr__(self, label.lower().replace(" ", "_"), value.strip())
        if not isinstance(self.earlier_independence, ResearchSourceIndependence):
            raise ResearchError("Earlier source independence is invalid.")
        if not isinstance(self.later_independence, ResearchSourceIndependence):
            raise ResearchError("Later source independence is invalid.")
        if self.earlier_independence is self.later_independence:
            raise ResearchError("A source correction must change independence.")


class HypothesisSupportCorrectionFinder:
    """Find only explicit, time-provable corrections to standing support."""

    def find(
        self,
        hypothesis: ResearchHypothesis,
        run: ResearchRun,
    ) -> tuple[HypothesisSupportCorrection, ...]:
        if not isinstance(hypothesis, ResearchHypothesis):
            raise ResearchError("Support correction projection needs a hypothesis.")
        if not isinstance(run, ResearchRun):
            raise ResearchError("Support correction projection needs a research run.")
        if hypothesis.run_id != run.run_id:
            raise ResearchError("Hypothesis and research run do not match.")
        if hypothesis.withdrawn:
            return ()

        support_by_document = self._timed_support_by_document(hypothesis, run)
        assessments_by_id = {
            assessment.assessment_id: assessment for assessment in run.assessments
        }
        corrections: list[HypothesisSupportCorrection] = []
        for later in sorted(
            run.assessments,
            key=lambda assessment: (
                assessment.recorded_at,
                assessment.assessment_id,
            ),
        ):
            earlier = assessments_by_id.get(later.supersedes_assessment_id or "")
            if earlier is None or not self._changed_independence(earlier, later):
                continue
            support = support_by_document.get(later.source_document_id)
            if support is None or support[0] > later.recorded_at:
                continue
            corrections.append(
                HypothesisSupportCorrection(
                    evidence_id=support[1],
                    source_document_id=later.source_document_id,
                    earlier_assessment_id=earlier.assessment_id,
                    later_assessment_id=later.assessment_id,
                    earlier_independence=earlier.independence,
                    later_independence=later.independence,
                )
            )
        return tuple(corrections)

    @staticmethod
    def _timed_support_by_document(
        hypothesis: ResearchHypothesis,
        run: ResearchRun,
    ) -> dict[str, tuple[datetime, str]]:
        evidence_by_id = {record.evidence_id: record for record in run.evidence}
        support_by_document: dict[str, tuple[datetime, str]] = {}
        for evidence_id in hypothesis.supporting_evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            authored_at = hypothesis.authored_at(
                evidence_id,
                HypothesisEvidenceRelation.SUPPORTS,
            )
            if evidence is None or authored_at is None:
                continue
            candidate = (authored_at, evidence_id)
            current = support_by_document.get(evidence.source_document_id)
            if current is None or candidate < current:
                support_by_document[evidence.source_document_id] = candidate
        return support_by_document

    @staticmethod
    def _changed_independence(
        earlier: ResearchSourceAssessmentRecord,
        later: ResearchSourceAssessmentRecord,
    ) -> bool:
        return (
            earlier.source_document_id == later.source_document_id
            and earlier.independence is not later.independence
        )
