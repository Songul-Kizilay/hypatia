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

There is no recursive reflection. This generator accepts a research run and an
optional sequence of that run's authored hypotheses; a reflection report is
neither, so reflecting on a reflection is not an operation that exists.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from core.Exceptions import ResearchError
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.ReflectionFindingKind import ReflectionFindingKind
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchHypothesis import ResearchHypothesis
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
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.SourceIdentity import identity_of

RUN_SUBJECT = "run"

_GAP_FINDINGS: dict[ResearchKnowledgeGapKind, ReflectionFindingKind] = {
    ResearchKnowledgeGapKind.CONTRADICTED_CLAIM: ReflectionFindingKind.CONTRADICTION,
    ResearchKnowledgeGapKind.UNRESOLVED_CLAIM: ReflectionFindingKind.UNCERTAIN,
    ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM: ReflectionFindingKind.WEAK_EVIDENCE,
    ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_CLAIM: (
        ReflectionFindingKind.WEAK_EVIDENCE
    ),
    ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_HYPOTHESIS: (
        ReflectionFindingKind.WEAK_EVIDENCE
    ),
    ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP: (
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
        hypotheses: Sequence[ResearchHypothesis] = (),
    ) -> ResearchReflectionReport:
        """Return one bounded report, performing no research of any kind."""
        if not isinstance(run, ResearchRun):
            raise ResearchError("Reflection requires a research run.")
        findings = [
            *self._failures(run),
            *self._revisions(run),
            *self._from_gaps(run, reflected_at, hypotheses),
            *self._unused_discoveries(run),
            *self._worked(run),
            *self._next_questions(run, reflected_at, hypotheses),
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
        findings: list[ResearchReflectionFinding] = []
        claims_by_id = {claim.claim_id: claim for claim in run.claims}
        for claim in run.claims:
            earlier_claim = claims_by_id.get(claim.supersedes_claim_id or "")
            if earlier_claim is None:
                continue
            findings.append(
                self._finding(
                    ReflectionFindingKind.REVISED_BELIEF,
                    claim.claim_id,
                    self._claim_revision_detail(earlier_claim, claim),
                )
            )
        assessments_by_id = {
            assessment.assessment_id: assessment for assessment in run.assessments
        }
        for assessment in run.assessments:
            earlier = assessments_by_id.get(assessment.supersedes_assessment_id or "")
            if earlier is None:
                continue
            findings.append(
                self._finding(
                    ReflectionFindingKind.REVISED_BELIEF,
                    assessment.assessment_id,
                    self._assessment_revision_detail(earlier, assessment),
                )
            )
        return findings

    @classmethod
    def _claim_revision_detail(
        cls,
        earlier: ResearchClaimRecord,
        later: ResearchClaimRecord,
    ) -> str:
        """Name only the authored claim dimensions the records changed."""
        structured_changes: list[str] = []
        if earlier.epistemic_state is not later.epistemic_state:
            structured_changes.append(
                "epistemic state from "
                f"{earlier.epistemic_state.value} to {later.epistemic_state.value}"
            )
        if earlier.confidence is not later.confidence:
            structured_changes.append(
                "authored confidence from "
                f"{earlier.confidence.value} to {later.confidence.value}"
            )
        if earlier.source_document_ids != later.source_document_ids:
            structured_changes.append("linked sources")
        if earlier.evidence_ids != later.evidence_ids:
            structured_changes.append("linked evidence")
        wording_changed = earlier.text != later.text
        if structured_changes:
            changes = [*structured_changes]
            if wording_changed:
                changes.append("authored wording")
            return (
                "A later claim changed this claim's "
                f"{cls._joined(changes)} during the run."
            )
        if wording_changed:
            return (
                "A later claim replaced this claim's authored wording; no "
                "structured claim judgement or provenance changed."
            )
        return (
            "A later claim replaced this claim record; no authored wording, "
            "structured claim judgement, or provenance changed."
        )

    @classmethod
    def _assessment_revision_detail(
        cls,
        earlier: ResearchSourceAssessmentRecord,
        later: ResearchSourceAssessmentRecord,
    ) -> str:
        """Name only the source-assessment dimensions the records changed."""
        changes: list[str] = []
        for label, before, after in (
            (
                "information trust",
                earlier.information_trust.value,
                later.information_trust.value,
            ),
            ("usefulness", earlier.usefulness.value, later.usefulness.value),
            (
                "applicability",
                earlier.applicability.value,
                later.applicability.value,
            ),
            (
                "independence",
                earlier.independence.value,
                later.independence.value,
            ),
            (
                "publication status",
                earlier.publication_status.value,
                later.publication_status.value,
            ),
        ):
            if before != after:
                changes.append(f"{label} from {before} to {after}")
        if earlier.evidence_ids != later.evidence_ids:
            changes.append("linked evidence")
        if changes:
            return (
                "A later assessment changed this source's "
                f"{cls._joined(changes)} during the run."
            )
        return (
            "A later assessment replaced this source assessment's authored "
            "wording; no structured source judgement changed."
        )

    @staticmethod
    def _joined(values: list[str]) -> str:
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]} and {values[1]}"
        return f"{', '.join(values[:-1])}, and {values[-1]}"

    def _from_gaps(
        self,
        run: ResearchRun,
        reflected_at: datetime,
        hypotheses: Sequence[ResearchHypothesis],
    ) -> list[ResearchReflectionFinding]:
        """Reuse gap detection rather than re-deriving a thin record."""
        return [
            self._finding(
                _GAP_FINDINGS[gap.kind],
                gap.subject_id or RUN_SUBJECT,
                gap.summary,
            )
            for gap in self._detector.detect(run, reflected_at, hypotheses)
            if gap.kind in _GAP_FINDINGS
        ]

    def _unused_discoveries(self, run: ResearchRun) -> list[ResearchReflectionFinding]:
        """Report discovery work that never became an accepted source."""
        accepted = {identity_of(source.url) for source in run.sources}
        findings: list[ResearchReflectionFinding] = []
        for record in run.discoveries:
            unused = sum(
                1
                for candidate in record.candidates
                if identity_of(candidate.url) not in accepted
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
        hypotheses: Sequence[ResearchHypothesis],
    ) -> list[ResearchReflectionFinding]:
        """Report curiosity's proposals without storing or acting on any."""
        gaps = self._detector.detect(run, reflected_at, hypotheses)
        return [
            self._finding(
                ReflectionFindingKind.NEXT_QUESTION,
                question.question_id,
                question.text,
            )
            for question in self._question_generator.generate(run, gaps, hypotheses)
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
