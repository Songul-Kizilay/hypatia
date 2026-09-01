"""Derive a reflection report from what a research run actually recorded.

Generation is pure reading and deterministic templates, for the same reason
curiosity is: a model asked to reflect will produce a confident narrative about
work it cannot inspect. Everything here points at a persisted record — a
failure, a contradiction, a superseded claim, an uncited source — and describes
it in process terms only.

Where reflection and curiosity ask the same question, reflection reuses
curiosity rather than re-deriving it. The thin-record observations come from the
gap detector, and the "what next" section is the curiosity generator's output,
reported but never stored: turning a question into work stays curiosity's
decision to offer and a human's decision to take.

There is no recursive reflection. This generator accepts a research run and
nothing else, and a reflection report is not a research run, so reflecting on a
reflection is not an operation that exists.
"""

from __future__ import annotations

from datetime import datetime

from core.Exceptions import ResearchError
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.ReflectionFindingKind import ReflectionFindingKind
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchReflectionFinding import (
    MAX_FINDING_DETAIL_LENGTH,
    ResearchReflectionFinding,
)
from research.ResearchReflectionReport import (
    MAX_REFLECTION_FINDINGS,
    ResearchReflectionReport,
    reflection_identity,
)
from research.ResearchRun import ResearchRun

RUN_SUBJECT = "run"

_GAP_FINDINGS: dict[ResearchKnowledgeGapKind, ReflectionFindingKind] = {
    ResearchKnowledgeGapKind.CONTRADICTED_CLAIM: ReflectionFindingKind.CONTRADICTION,
    ResearchKnowledgeGapKind.UNRESOLVED_CLAIM: ReflectionFindingKind.UNCERTAIN,
    ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM: ReflectionFindingKind.WEAK_EVIDENCE,
    ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_CLAIM: (
        ReflectionFindingKind.WEAK_EVIDENCE
    ),
    ResearchKnowledgeGapKind.LOW_TRUST_SOURCE: ReflectionFindingKind.WEAK_EVIDENCE,
    ResearchKnowledgeGapKind.UNASSESSED_SOURCE: ReflectionFindingKind.WEAK_EVIDENCE,
    ResearchKnowledgeGapKind.UNUSED_SOURCE: ReflectionFindingKind.UNUSED_EFFORT,
    ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION: ReflectionFindingKind.UNUSED_EFFORT,
}


class ResearchReflectionGenerator:
    """Read one research run and report how the research itself went."""

    def __init__(
        self,
        *,
        detector: ResearchKnowledgeGapDetector | None = None,
        question_generator: ResearchCuriosityQuestionGenerator | None = None,
        max_findings: int = MAX_REFLECTION_FINDINGS,
    ) -> None:
        if isinstance(max_findings, bool) or not isinstance(max_findings, int):
            raise ValueError("Reflection finding limit must be a whole number.")
        if max_findings < 1 or max_findings > MAX_REFLECTION_FINDINGS:
            raise ValueError("Reflection finding limit is out of range.")
        self._detector = detector or ResearchKnowledgeGapDetector()
        self._question_generator = (
            question_generator or ResearchCuriosityQuestionGenerator(max_questions=3)
        )
        self._max_findings = max_findings

    def reflect(
        self,
        run: ResearchRun,
        reflected_at: datetime,
    ) -> ResearchReflectionReport:
        """Return one bounded report, performing no research of any kind."""
        if not isinstance(run, ResearchRun):
            raise ResearchError("Reflection requires a research run.")
        findings = [
            *self._failures(run),
            *self._revisions(run),
            *self._from_gaps(run, reflected_at),
            *self._unused_discoveries(run),
            *self._worked(run),
            *self._next_questions(run, reflected_at),
        ]
        findings.sort(key=lambda finding: (finding.order, finding.subject_id))
        return ResearchReflectionReport(
            report_id=reflection_identity(run.run_id, reflected_at),
            run_id=run.run_id,
            question=run.question,
            findings=tuple(findings[: self._max_findings]),
            summary=CanonicalResearchSummary.from_runs((run,)),
            reflected_at=reflected_at,
        )

    def _failures(self, run: ResearchRun) -> list[ResearchReflectionFinding]:
        """Report what the run recorded as having gone wrong."""
        return [
            self._finding(
                ReflectionFindingKind.FAILED,
                record.stage,
                f"The {record.stage} stage failed: {record.reason}",
            )
            for record in run.failures
        ]

    def _revisions(self, run: ResearchRun) -> list[ResearchReflectionFinding]:
        """Report where a later record replaced an earlier one."""
        findings = [
            self._finding(
                ReflectionFindingKind.REVISED_BELIEF,
                claim.claim_id,
                "A later claim replaced an earlier one, so what was believed "
                "here changed during the run.",
            )
            for claim in run.claims
            if claim.supersedes_claim_id
        ]
        findings.extend(
            self._finding(
                ReflectionFindingKind.REVISED_BELIEF,
                assessment.assessment_id,
                "A later assessment replaced an earlier one, so how far this "
                "source was trusted changed during the run.",
            )
            for assessment in run.assessments
            if assessment.supersedes_assessment_id
        )
        return findings

    def _from_gaps(
        self,
        run: ResearchRun,
        reflected_at: datetime,
    ) -> list[ResearchReflectionFinding]:
        """Reuse gap detection rather than re-deriving a thin record."""
        return [
            self._finding(
                _GAP_FINDINGS[gap.kind],
                gap.subject_id or RUN_SUBJECT,
                gap.summary,
            )
            for gap in self._detector.detect(run, reflected_at)
            if gap.kind in _GAP_FINDINGS
        ]

    def _unused_discoveries(self, run: ResearchRun) -> list[ResearchReflectionFinding]:
        """Report discovery work that never became an accepted source."""
        accepted = {source.url for source in run.sources}
        findings: list[ResearchReflectionFinding] = []
        for record in run.discoveries:
            unused = sum(
                1 for candidate in record.candidates if candidate.url not in accepted
            )
            if not unused:
                continue
            findings.append(
                self._finding(
                    ReflectionFindingKind.UNUSED_EFFORT,
                    record.discovery_id,
                    f"{unused} of {len(record.candidates)} candidates from "
                    f"{record.provider} were never accepted. A candidate is not "
                    "a source, so this is normal, not waste.",
                )
            )
        return findings

    def _worked(self, run: ResearchRun) -> list[ResearchReflectionFinding]:
        """Report only what actually landed, with each stage kept separate."""
        stages = (
            (len(run.sources), "source", "accepted"),
            (len(run.evidence), "evidence record", "recorded"),
            (len(run.assessments), "source assessment", "written"),
            (len(run.claims), "claim", "authored"),
        )
        return [
            self._finding(
                ReflectionFindingKind.WORKED,
                f"{label}s",
                f"{count} {label}{'' if count == 1 else 's'} {verb}.",
            )
            for count, label, verb in stages
            if count
        ]

    def _next_questions(
        self,
        run: ResearchRun,
        reflected_at: datetime,
    ) -> list[ResearchReflectionFinding]:
        """Report curiosity's proposals without storing or acting on any."""
        gaps = self._detector.detect(run, reflected_at)
        return [
            self._finding(
                ReflectionFindingKind.NEXT_QUESTION,
                question.question_id,
                question.text,
            )
            for question in self._question_generator.generate(run, gaps)
        ]

    @staticmethod
    def _finding(
        kind: ReflectionFindingKind,
        subject_id: str,
        detail: str,
    ) -> ResearchReflectionFinding:
        return ResearchReflectionFinding(
            kind=kind,
            subject_id=subject_id,
            detail=detail[:MAX_FINDING_DETAIL_LENGTH],
        )
