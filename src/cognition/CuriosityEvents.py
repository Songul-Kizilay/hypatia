"""Bounded observability for curiosity gap detection and question proposals.

Payloads carry run, gap, and question identifiers, bounded gap-kind categories,
counts, and integer ranks. They never carry a research question, claim text,
proposed question text, URL, source body, evidence text, or an exception
message.
"""

from __future__ import annotations

from collections import Counter

from eventbus.EventBus import EventBus
from research.CuriosityResearchProposal import CuriosityResearchProposal
from research.ResearchCuriosityPreview import ResearchCuriosityPreview
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion

GAPS_DETECTED = "curiosity.gaps_detected"
QUESTIONS_GENERATED = "curiosity.questions_generated"
QUESTIONS_STORED = "curiosity.questions_stored"
QUESTION_ACCEPTED = "curiosity.question_accepted"
QUESTION_DISMISSED = "curiosity.question_dismissed"
PROPOSAL_PREVIEWED = "curiosity.proposal_previewed"

EVENT_SOURCE = "research.curiosity"


class CuriosityEvents:
    """Publish bounded curiosity events, or nothing when no bus is present."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def gaps_detected(self, preview: ResearchCuriosityPreview) -> None:
        kinds = Counter(gap.kind.value for gap in preview.gaps)
        self._emit(
            GAPS_DETECTED,
            {
                "run_id": preview.run_id,
                "gap_count": preview.gap_count,
                "gap_kinds": dict(sorted(kinds.items())),
            },
        )

    def questions_generated(self, preview: ResearchCuriosityPreview) -> None:
        ranks = [question.rank_score for question in preview.questions]
        self._emit(
            QUESTIONS_GENERATED,
            {
                "run_id": preview.run_id,
                "gap_count": preview.gap_count,
                "question_count": preview.question_count,
                "top_rank_score": max(ranks) if ranks else 0,
                "executed": False,
            },
        )

    def questions_stored(
        self,
        preview: ResearchCuriosityPreview,
        stored_count: int,
        total_count: int,
    ) -> None:
        self._emit(
            QUESTIONS_STORED,
            {
                "run_id": preview.run_id,
                "proposed_count": preview.question_count,
                "stored_count": stored_count,
                "total_count": total_count,
                "executed": False,
            },
        )

    def question_accepted(self, question: ResearchCuriosityQuestion) -> None:
        self._emit(QUESTION_ACCEPTED, self._decision_payload(question))

    def proposal_previewed(self, proposal: CuriosityResearchProposal) -> None:
        """Announce that a proposal was drafted, and that nothing ran.

        Counts and identifiers only, as everywhere else. The step count is the
        useful number precisely because it is a count of work described rather
        than work done.
        """
        self._emit(
            PROPOSAL_PREVIEWED,
            {
                "curiosity_question_id": proposal.curiosity_question_id,
                "knowledge_gap_id": proposal.knowledge_gap_id,
                "run_id": proposal.run_id,
                "gap_kind": proposal.gap_kind.value,
                "proposed_step_count": proposal.step_count,
                "authorized": proposal.authorized,
                "started": proposal.started,
            },
        )

    def question_dismissed(self, question: ResearchCuriosityQuestion) -> None:
        self._emit(QUESTION_DISMISSED, self._decision_payload(question))

    @staticmethod
    def _decision_payload(
        question: ResearchCuriosityQuestion,
    ) -> dict[str, object]:
        return {
            "question_id": question.question_id,
            "gap_id": question.gap_id,
            "run_id": question.run_id,
            "kind": question.kind.value,
            "rank_score": question.rank_score,
            "status": question.status.value,
            "executed": False,
        }

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
