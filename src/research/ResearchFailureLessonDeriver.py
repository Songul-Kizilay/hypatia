"""Derive checkable lessons from what a research run actually recorded.

Derivation is pure reading and fixed templates. Every lesson it produces names
the persisted records it came from, so a lesson can always be traced back and,
if the records say otherwise, discarded.

The templates are careful about what they assert. A superseded claim records
revision, not falsity. A discovery whose
candidates were never accepted produced "this did not pay off here", not "this
provider is useless". The difference matters most later, when the lesson is
recalled by someone who no longer remembers the run.
"""

from __future__ import annotations

from datetime import datetime

from core.Exceptions import ResearchError
from research.FailureLessonKind import FailureLessonKind
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchFailureLesson import (
    MAX_LESSON_CONTEXT_LENGTH,
    MAX_LESSON_PROVENANCE,
    MAX_LESSON_STATEMENT_LENGTH,
    ResearchFailureLesson,
    lesson_identity,
)
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord

MAX_LESSONS_PER_RUN = 40


class ResearchFailureLessonDeriver:
    """Read one run and report the lessons its own records support."""

    def __init__(self, max_lessons: int = MAX_LESSONS_PER_RUN) -> None:
        if isinstance(max_lessons, bool) or not isinstance(max_lessons, int):
            raise ValueError("Failure lesson limit must be a whole number.")
        if max_lessons < 1 or max_lessons > MAX_LESSONS_PER_RUN:
            raise ValueError("Failure lesson limit is out of range.")
        self._max_lessons = max_lessons

    def derive(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> tuple[ResearchFailureLesson, ...]:
        """Return the lessons this run supports, heaviest first and bounded."""
        if not isinstance(run, ResearchRun):
            raise ResearchError("Failure lesson derivation requires a research run.")
        lessons = [
            *self._contradicted_claims(run, recorded_at),
            *self._superseded_claims(run, recorded_at),
            *self._superseded_assessments(run, recorded_at),
            *self._low_trust_sources(run, recorded_at),
            *self._unused_discoveries(run, recorded_at),
            *self._operation_failures(run, recorded_at),
        ]
        lessons.sort(key=lambda lesson: (-lesson.weight, lesson.lesson_id))
        return tuple(lessons[: self._max_lessons])

    def _contradicted_claims(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> list[ResearchFailureLesson]:
        """A claim named in a contradiction is one we can no longer simply hold."""
        latest_by_claim: dict[str, ResearchClaimContradictionRecord] = {}
        for record in run.claim_contradictions:
            for claim_id in record.claim_ids:
                current = latest_by_claim.get(claim_id)
                if current is None or (record.recorded_at, record.contradiction_id) > (
                    current.recorded_at,
                    current.contradiction_id,
                ):
                    latest_by_claim[claim_id] = record
        return [
            self._lesson(
                run,
                FailureLessonKind.DISPROVING_EVIDENCE,
                claim_id,
                "This claim was recorded as contradicting another, so it "
                "cannot simply be held. Which one survives is not settled "
                "here.",
                (claim_id, record.contradiction_id, *record.evidence_ids),
                recorded_at,
            )
            for claim_id, record in latest_by_claim.items()
        ]

    def _superseded_claims(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> list[ResearchFailureLesson]:
        """Classify a replaced claim from its actual authored epistemic state."""
        by_id = {claim.claim_id: claim for claim in run.claims}
        lessons: list[ResearchFailureLesson] = []
        for claim in run.claims:
            earlier = by_id.get(claim.supersedes_claim_id or "")
            if earlier is None:
                continue
            kind = (
                FailureLessonKind.FAILED_HYPOTHESIS
                if earlier.epistemic_state is ResearchEpistemicState.HYPOTHESIS
                else FailureLessonKind.REVISED_CLAIM
            )
            lessons.append(
                self._lesson(
                    run,
                    kind,
                    earlier.claim_id,
                    self._revision_statement(earlier, claim),
                    (earlier.claim_id, claim.claim_id),
                    recorded_at,
                )
            )
            if claim.confidence is not earlier.confidence:
                lessons.append(
                    self._confidence_lesson(run, earlier, claim, recorded_at)
                )
        return lessons

    @staticmethod
    def _revision_statement(
        earlier: ResearchClaimRecord,
        later: ResearchClaimRecord,
    ) -> str:
        if earlier.epistemic_state is ResearchEpistemicState.HYPOTHESIS:
            return (
                "We stopped holding this hypothesis claim and replaced it with a "
                f"{later.epistemic_state.value} one. It was abandoned, not disproved."
            )
        return (
            f"We revised this {earlier.epistemic_state.value} claim and replaced it "
            f"with a {later.epistemic_state.value} one. The earlier claim was "
            "superseded, not disproved by that replacement."
        )

    def _confidence_lesson(
        self,
        run: ResearchRun,
        earlier: ResearchClaimRecord,
        later: ResearchClaimRecord,
        recorded_at: datetime,
    ) -> ResearchFailureLesson:
        return self._lesson(
            run,
            FailureLessonKind.CONFIDENCE_CHANGE,
            earlier.claim_id,
            f"Confidence here moved from {earlier.confidence.value} to "
            f"{later.confidence.value}. Whatever supported the first reading was "
            "not as strong as it looked.",
            (earlier.claim_id, later.claim_id),
            recorded_at,
        )

    def _superseded_assessments(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> list[ResearchFailureLesson]:
        """A revised assessment means we misjudged a source the first time."""
        by_id = {record.assessment_id: record for record in run.assessments}
        lessons: list[ResearchFailureLesson] = []
        for assessment in run.assessments:
            earlier = by_id.get(assessment.supersedes_assessment_id or "")
            if earlier is None or earlier.information_trust is (
                assessment.information_trust
            ):
                continue
            lessons.append(
                self._lesson(
                    run,
                    FailureLessonKind.INVALID_ASSUMPTION,
                    earlier.assessment_id,
                    f"This source was first assessed {earlier.information_trust.value} "
                    f"and later {assessment.information_trust.value}. The first "
                    "judgement did not hold.",
                    (earlier.assessment_id, assessment.assessment_id),
                    recorded_at,
                )
            )
        return lessons

    def _low_trust_sources(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> list[ResearchFailureLesson]:
        """Accepting a source we then judged weak is worth remembering."""
        superseded = {
            record.supersedes_assessment_id
            for record in run.assessments
            if record.supersedes_assessment_id
        }
        active_low = [
            record
            for record in run.assessments
            if record.assessment_id not in superseded
            and record.information_trust is ResearchInformationTrust.LOW
        ]
        # Parallel assessments are legitimate, but a lesson is identified by
        # source. Keep one lesson per source and let the newest active record
        # provide its exact provenance instead of manufacturing duplicate IDs.
        latest_by_source: dict[str, ResearchSourceAssessmentRecord] = {}
        for record in active_low:
            current = latest_by_source.get(record.source_document_id)
            if current is None or (record.recorded_at, record.assessment_id) > (
                current.recorded_at,
                current.assessment_id,
            ):
                latest_by_source[record.source_document_id] = record
        return [
            self._lesson(
                run,
                FailureLessonKind.FALSE_POSITIVE,
                record.source_document_id,
                "This source was accepted and then assessed as low trust. "
                "Acceptance is not a judgement of quality, and here the two "
                "diverged.",
                (record.source_document_id, record.assessment_id),
                recorded_at,
            )
            for record in latest_by_source.values()
        ]

    def _unused_discoveries(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> list[ResearchFailureLesson]:
        """A discovery that yielded no accepted source did not pay off here."""
        accepted = {source.url for source in run.sources}
        return [
            self._lesson(
                run,
                FailureLessonKind.INEFFECTIVE_STRATEGY,
                record.discovery_id,
                f"Searching {record.provider} for this returned "
                f"{len(record.candidates)} candidate(s) and none was accepted. "
                "That is a result about this query, not about the provider.",
                (record.discovery_id,),
                recorded_at,
            )
            for record in run.discoveries
            if record.candidates
            and not any(candidate.url in accepted for candidate in record.candidates)
        ]

    def _operation_failures(
        self,
        run: ResearchRun,
        recorded_at: datetime,
    ) -> list[ResearchFailureLesson]:
        """Each recorded failure is a lesson about how the work goes wrong."""
        lessons: list[ResearchFailureLesson] = []
        base_identities = [self._failure_identity(record) for record in run.failures]
        reserved = set(base_identities)
        used: set[str] = set()
        occurrences: dict[str, int] = {}
        for record, base_identity in zip(run.failures, base_identities, strict=True):
            provider = f" for {record.provider}" if record.provider else ""
            occurrence = occurrences.get(base_identity, 0) + 1
            occurrences[base_identity] = occurrence
            identity = base_identity
            if identity in used:
                while True:
                    candidate = f"{base_identity}:occurrence-{occurrence}"
                    occurrence += 1
                    if candidate not in reserved and candidate not in used:
                        identity = candidate
                        break
            used.add(identity)
            lessons.append(
                self._lesson(
                    run,
                    FailureLessonKind.OPERATION_FAILURE,
                    identity,
                    f"The {record.stage} stage{provider} failed here: {record.reason}",
                    (f"failure:{identity}",),
                    recorded_at,
                )
            )
        return lessons

    @staticmethod
    def _failure_identity(record: ResearchFailureRecord) -> str:
        identity = f"{record.stage}:{record.occurred_at.isoformat()}"
        return f"{identity}:{record.provider}" if record.provider else identity

    @staticmethod
    def _lesson(
        run: ResearchRun,
        kind: FailureLessonKind,
        subject_id: str,
        statement: str,
        provenance: tuple[str, ...],
        recorded_at: datetime,
    ) -> ResearchFailureLesson:
        unique: list[str] = []
        for value in provenance:
            if value and value not in unique:
                unique.append(value)
        return ResearchFailureLesson(
            lesson_id=lesson_identity(run.run_id, kind, subject_id),
            kind=kind,
            run_id=run.run_id,
            subject_id=subject_id,
            statement=statement[:MAX_LESSON_STATEMENT_LENGTH],
            provenance=tuple(unique[:MAX_LESSON_PROVENANCE]),
            context=run.question[:MAX_LESSON_CONTEXT_LENGTH],
            recorded_at=recorded_at,
        )
