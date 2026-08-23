"""Turn detected gaps into ranked questions the system proposes to itself.

Generation is deterministic and template-driven on purpose. A model asked to
invent follow-up questions can quietly smuggle in assertions; a template can
only ask about a claim, source, or question the system already recorded. Every
produced string is interrogative, so nothing here can be mistaken for a finding.

Ranking is a stated formula, not a learned score: gap severity dominates, and
recorded uncertainty breaks ties. Identical inputs always produce identical
ordering.
"""

from __future__ import annotations

from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchCuriosityQuestion import (
    MAX_QUESTION_TEXT_LENGTH,
    ResearchCuriosityQuestion,
)
from research.ResearchKnowledgeGap import ResearchKnowledgeGap
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRun import ResearchRun

DEFAULT_MAX_QUESTIONS = 10
MAX_QUESTIONS_CEILING = 20
MAX_SUBJECT_LENGTH = 120
SEVERITY_WEIGHT = 10

_TEMPLATES: dict[ResearchKnowledgeGapKind, str] = {
    ResearchKnowledgeGapKind.CONTRADICTED_CLAIM: (
        "What evidence would resolve the contradiction around this claim: {subject}?"
    ),
    ResearchKnowledgeGapKind.UNRESOLVED_CLAIM: (
        "What evidence would settle this still-open claim: {subject}?"
    ),
    ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM: (
        "Which independent source would corroborate this claim: {subject}?"
    ),
    ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION: (
        "Which sources could begin to answer this unsupported question: {subject}?"
    ),
    ResearchKnowledgeGapKind.LOW_TRUST_SOURCE: (
        "Which higher-trust source covers the same ground as this one: {subject}?"
    ),
    ResearchKnowledgeGapKind.UNASSESSED_SOURCE: (
        "How trustworthy is this accepted but unassessed source: {subject}?"
    ),
    ResearchKnowledgeGapKind.UNUSED_SOURCE: (
        "What evidence, if any, does this so-far unused source support: {subject}?"
    ),
}

_UNCERTAINTY_BONUS: dict[ResearchClaimConfidence, int] = {
    ResearchClaimConfidence.UNASSESSED: 3,
    ResearchClaimConfidence.LOW: 2,
    ResearchClaimConfidence.MEDIUM: 1,
    ResearchClaimConfidence.HIGH: 0,
}


class ResearchCuriosityQuestionGenerator:
    """Produce bounded, ranked candidate questions from detected gaps."""

    def __init__(self, max_questions: int = DEFAULT_MAX_QUESTIONS) -> None:
        if isinstance(max_questions, bool) or not isinstance(max_questions, int):
            raise ValueError("Curiosity question limit must be a whole number.")
        if max_questions < 1 or max_questions > MAX_QUESTIONS_CEILING:
            raise ValueError("Curiosity question limit is out of range.")
        self._max_questions = max_questions

    def generate(
        self,
        run: ResearchRun,
        gaps: tuple[ResearchKnowledgeGap, ...],
    ) -> tuple[ResearchCuriosityQuestion, ...]:
        """Return ranked candidate questions, highest rank first."""
        subjects = self._subjects(run)
        questions = [
            self._question(run, gap, subjects.get(gap.subject_id, run.question))
            for gap in gaps
            if gap.kind in _TEMPLATES
        ]
        questions.sort(
            key=lambda question: (-question.rank_score, question.question_id)
        )
        return tuple(questions[: self._max_questions])

    def _question(
        self,
        run: ResearchRun,
        gap: ResearchKnowledgeGap,
        subject: str,
    ) -> ResearchCuriosityQuestion:
        template = _TEMPLATES[gap.kind]
        text = template.format(subject=self._trim(subject))
        return ResearchCuriosityQuestion(
            question_id=question_identity(gap.gap_id),
            gap_id=gap.gap_id,
            run_id=gap.run_id,
            kind=gap.kind,
            subject_id=gap.subject_id,
            text=text[:MAX_QUESTION_TEXT_LENGTH],
            rank_score=self._rank(run, gap),
            generated_at=gap.detected_at,
        )

    @staticmethod
    def _rank(run: ResearchRun, gap: ResearchKnowledgeGap) -> int:
        """Rank by declared severity, breaking ties with recorded uncertainty."""
        bonus = 0
        for claim in run.claims:
            if claim.claim_id == gap.subject_id:
                bonus = _UNCERTAINTY_BONUS.get(claim.confidence, 0)
                break
        return gap.severity * SEVERITY_WEIGHT + bonus

    @staticmethod
    def _subjects(run: ResearchRun) -> dict[str, str]:
        """Map claim and source identifiers to their own recorded wording."""
        subjects = {claim.claim_id: claim.text for claim in run.claims}
        for source in run.sources:
            subjects[source.document_id] = source.title or source.url
        return subjects

    @staticmethod
    def _trim(subject: str) -> str:
        collapsed = " ".join(subject.split())
        if len(collapsed) <= MAX_SUBJECT_LENGTH:
            return collapsed
        return collapsed[: MAX_SUBJECT_LENGTH - 1].rstrip() + "…"


def question_identity(gap_id: str) -> str:
    """Return a stable identity so re-generating a question yields the same ID."""
    return f"question:{gap_id}"
