"""Turn explicit hypothesis outcomes into bounded, checkable lessons.

This module reads one already-derived appraisal. It does not watch events,
persist status, mutate a hypothesis, or decide whether the hypothesis is true.
Only an explicit Failure Memory command asks the application layer to call it.

WEAKENED and CONTRADICTED deliberately use different existing lesson kinds.
If an operator remembers a weakened hypothesis and later remembers it again
after it becomes contradicted, both observations keep stable, distinct lesson
identities. That is a bounded record of two explicit observations, not hidden
transition tracking.
"""

from __future__ import annotations

from datetime import datetime

from core.Exceptions import ResearchError
from research.FailureLessonKind import FailureLessonKind
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisStatus import HypothesisStatus
from research.ResearchFailureLesson import (
    MAX_LESSON_CONTEXT_LENGTH,
    MAX_LESSON_PROVENANCE,
    MAX_LESSON_STATEMENT_LENGTH,
    ResearchFailureLesson,
    lesson_identity,
)
from research.ResearchRun import ResearchRun

MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN = 40

_LESSON_KINDS = {
    HypothesisStatus.WEAKENED: FailureLessonKind.DISPROVING_EVIDENCE,
    HypothesisStatus.CONTRADICTED: FailureLessonKind.FAILED_HYPOTHESIS,
}


class HypothesisFailureLessonDeriver:
    """Derive at most one advisory lesson from one current appraisal."""

    def derive(
        self,
        appraisal: HypothesisAppraisal,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> tuple[ResearchFailureLesson, ...]:
        """Return a lesson only for a weakened or contradicted hypothesis."""
        if not isinstance(appraisal, HypothesisAppraisal):
            raise ResearchError("Hypothesis lesson derivation requires an appraisal.")
        if not isinstance(run, ResearchRun):
            raise ResearchError("Hypothesis lesson derivation requires a research run.")
        hypothesis = appraisal.hypothesis
        if hypothesis.run_id != run.run_id:
            raise ResearchError("Hypothesis and research run do not match.")
        kind = _LESSON_KINDS.get(appraisal.status)
        if kind is None:
            return ()
        provenance: list[str] = []
        for record_id in (
            hypothesis.hypothesis_id,
            *hypothesis.opposing_evidence_ids,
        ):
            if record_id not in provenance:
                provenance.append(record_id)
        lesson = ResearchFailureLesson(
            lesson_id=lesson_identity(
                hypothesis.run_id,
                kind,
                hypothesis.hypothesis_id,
            ),
            kind=kind,
            run_id=hypothesis.run_id,
            subject_id=hypothesis.hypothesis_id,
            statement=self._statement(appraisal)[:MAX_LESSON_STATEMENT_LENGTH],
            provenance=tuple(provenance[:MAX_LESSON_PROVENANCE]),
            context=run.question[:MAX_LESSON_CONTEXT_LENGTH],
            recorded_at=recorded_at,
        )
        return (lesson,)

    @staticmethod
    def _statement(appraisal: HypothesisAppraisal) -> str:
        if appraisal.status is HypothesisStatus.WEAKENED:
            return (
                "This hypothesis is currently weakened: opposing evidence is "
                "recorded alongside support. No truth or falsity is decided here."
            )
        return (
            "This hypothesis is currently contradicted: opposing evidence is "
            "recorded without supporting source coverage in this run. No truth or "
            "falsity is decided here."
        )
