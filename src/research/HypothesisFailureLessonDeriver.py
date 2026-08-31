"""Turn explicit hypothesis outcomes into bounded, checkable lessons.

This module reads one already-derived appraisal. It does not watch events,
persist status, mutate a hypothesis, or decide whether the hypothesis is true.
Only an explicit Failure Memory command asks the application layer to call it.

WEAKENED and CONTRADICTED deliberately use different existing lesson kinds.
If an operator remembers a weakened hypothesis and later remembers it again
after it becomes contradicted, both observations keep stable, distinct lesson
identities. That is a bounded record of two explicit observations, not hidden
transition tracking.

A lesson names the hypothesis in the wording it was written in. An outcome
recorded only as an identifier is unreadable by the time anyone needs it, and
recall matches on shared words, so a lesson made entirely of fixed phrasing
would match every later question containing a word like "evidence".
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

#: Retention order for a run that produces more outcomes than the cap keeps.
#: Deliberately not the recall weight. Recall ranks what is most worth reading
#: next; retention decides what is kept at all. A weakened hypothesis outranks a
#: contradicted one during recall, so reusing that order here would discard the
#: contradictions first — losing exactly the outcome this capability exists for.
_RETENTION_ORDER = {
    FailureLessonKind.FAILED_HYPOTHESIS: 0,
    FailureLessonKind.DISPROVING_EVIDENCE: 1,
}

NO_TRUTH_DECIDED = "No truth or falsity is decided here."


def hypothesis_retention_key(lesson: ResearchFailureLesson) -> tuple[int, str]:
    """Order outcome lessons so a bounded run keeps the strongest signal."""
    return (
        _RETENTION_ORDER.get(lesson.kind, len(_RETENTION_ORDER)),
        lesson.lesson_id,
    )


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
        provenance = self._provenance(appraisal)
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
    def _provenance(appraisal: HypothesisAppraisal) -> list[str]:
        """Name every side that made the remembered outcome possible.

        A weakened status exists only because support and opposition coexist.
        Interleave those records so the bounded provenance keeps both sides even
        when either side alone is longer than the lesson limit. A contradicted
        status has no supporting side and therefore names only its opposition.
        """
        hypothesis = appraisal.hypothesis
        groups = (
            (
                hypothesis.supporting_evidence_ids,
                hypothesis.opposing_evidence_ids,
            )
            if appraisal.status is HypothesisStatus.WEAKENED
            else (hypothesis.opposing_evidence_ids,)
        )
        provenance = [hypothesis.hypothesis_id]
        index = 0
        while len(provenance) < MAX_LESSON_PROVENANCE:
            added = False
            for group in groups:
                if index < len(group):
                    record_id = group[index]
                    if record_id not in provenance:
                        provenance.append(record_id)
                        if len(provenance) == MAX_LESSON_PROVENANCE:
                            break
                    added = True
            if not added:
                break
            index += 1
        return provenance

    @classmethod
    def _statement(cls, appraisal: HypothesisAppraisal) -> str:
        """Describe the outcome in terms of the hypothesis actually written."""
        if appraisal.status is HypothesisStatus.WEAKENED:
            prefix = 'Weakened hypothesis: "'
            suffix = (
                '" - opposing evidence is recorded alongside its support. '
                f"{NO_TRUTH_DECIDED}"
            )
        else:
            prefix = 'Contradicted hypothesis: "'
            suffix = (
                '" - opposing evidence is recorded without supporting source '
                f"coverage in this run. {NO_TRUTH_DECIDED}"
            )
        # Only the quoted wording is shortened. Trimming the whole sentence
        # would eventually cut the disclaimer off the end, leaving a lesson
        # that reads like a verdict.
        budget = MAX_LESSON_STATEMENT_LENGTH - len(prefix) - len(suffix)
        wording = appraisal.hypothesis.one_line_statement(budget)
        return f"{prefix}{wording}{suffix}"
