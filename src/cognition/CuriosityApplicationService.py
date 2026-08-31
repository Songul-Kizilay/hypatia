"""Bounded curiosity: detect gaps, propose questions, and stop there.

The pipeline is deliberately short of acting. Detection reads a run, generation
drafts questions from templates, ranking orders them, and preview reports them.
Storing a question records a proposal; accepting one records that a human thinks
it is worth pursuing. None of those steps starts research, drafts a plan, queues
a background task, or spends a network or model operation.

That separation is the point. A system that automatically chased everything it
noticed would convert idle curiosity into unbounded work, and would quietly
decide for itself what deserves investigation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CuriosityEvents import CuriosityEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.CuriosityProposalBuilder import CuriosityProposalBuilder
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.CuriosityQuestionStore import CuriosityQuestionStore
from research.HypothesisStore import HypothesisStore
from research.JsonFileCuriosityQuestionStore import MAX_CURIOSITY_STORE_QUESTIONS
from research.ResearchCuriosityPreview import ResearchCuriosityPreview
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

CURIOSITY_GAP_DETECT_INTENT = "curiosity_gap_detect"
CURIOSITY_QUESTION_PREVIEW_INTENT = "curiosity_question_preview"
CURIOSITY_QUESTION_STORE_INTENT = "curiosity_question_store"
CURIOSITY_QUESTION_LIST_INTENT = "curiosity_question_list"
CURIOSITY_QUESTION_ACCEPT_INTENT = "curiosity_question_accept"
CURIOSITY_QUESTION_DISMISS_INTENT = "curiosity_question_dismiss"
CURIOSITY_PREPARE_PROPOSAL_INTENT = "curiosity_prepare_proposal"


class CuriosityApplicationService:
    """Detect knowledge gaps and propose ranked questions, without acting."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        detector: ResearchKnowledgeGapDetector | None = None,
        generator: ResearchCuriosityQuestionGenerator | None = None,
        question_store: CuriosityQuestionStore | None = None,
        hypothesis_store: HypothesisStore | None = None,
        draft_service: ResearchPlanDraftService | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._detector = detector or ResearchKnowledgeGapDetector()
        self._generator = generator or ResearchCuriosityQuestionGenerator()
        self._question_store = question_store
        self._hypothesis_store = hypothesis_store
        # Injected so a preview's plan identity and time are deterministic in
        # tests. The digest ignores both, so a default service still previews
        # the same plan content twice.
        self._draft_service = draft_service or ResearchPlanDraftService()
        self._events = CuriosityEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._questions: dict[str, ResearchCuriosityQuestion] = {}
        self._restore()

    @staticmethod
    def is_gap_detect_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_GAP_DETECT_INTENT

    @staticmethod
    def is_question_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_PREVIEW_INTENT

    @staticmethod
    def is_question_store_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_STORE_INTENT

    @staticmethod
    def is_question_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_LIST_INTENT

    @staticmethod
    def is_question_accept_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_ACCEPT_INTENT

    @staticmethod
    def is_prepare_proposal_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_PREPARE_PROPOSAL_INTENT

    @staticmethod
    def is_question_dismiss_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_DISMISS_INTENT

    def questions(self) -> tuple[ResearchCuriosityQuestion, ...]:
        """Return every known proposal, highest rank first."""
        return tuple(
            sorted(
                self._questions.values(),
                key=lambda question: (-question.rank_score, question.question_id),
            )
        )

    def process_gap_detect(self, request: BrainRequest) -> BrainResponse:
        """Report where one run's own record is thin, proposing nothing."""
        preview = self._detect(request, generate=False)
        self._events.gaps_detected(preview)
        return self._response_composer.curiosity_gaps(request, preview)

    def process_question_preview(self, request: BrainRequest) -> BrainResponse:
        """Draft and rank questions for one run without storing any of them."""
        preview = self._detect(request, generate=True)
        self._events.gaps_detected(preview)
        self._events.questions_generated(preview)
        return self._response_composer.curiosity_preview(request, preview)

    def process_question_store(self, request: BrainRequest) -> BrainResponse:
        """Persist the ranked proposals for one run, deciding nothing."""
        preview = self._detect(request, generate=True)
        self._events.gaps_detected(preview)
        self._events.questions_generated(preview)
        stored, durable = self._store(preview.questions)
        if not durable:
            return self._response_composer.curiosity_persistence_failed(
                request,
                f"{stored} proposal(s)",
            )
        persisted = ResearchCuriosityPreview(
            run_id=preview.run_id,
            gaps=preview.gaps,
            questions=preview.questions,
            stored=True,
        )
        self._events.questions_stored(persisted, stored, len(self._questions))
        return self._response_composer.curiosity_preview(request, persisted)

    def process_question_list(self, request: BrainRequest) -> BrainResponse:
        """Report every stored proposal without running anything."""
        return self._response_composer.curiosity_question_list(
            request,
            self.questions(),
        )

    def process_prepare_proposal(self, request: BrainRequest) -> BrainResponse:
        """Draft an inert plan for one accepted question, starting nothing.

        A second, separate operator decision. Accepting a question says it is
        worth keeping; this says a proposal for it is worth reading, and neither
        says anything may run. Nothing here reaches a provider, a source, a tool
        or a model — the plan describes future discovery and performs none of it.

        The gap is re-derived from current state rather than trusted from the
        stored question, because an accepted question outlives the situation
        that produced it. Somebody may have recorded the very evidence the gap
        was about between accepting and asking, and drafting research for a gap
        that has since closed would propose work nobody needs.
        """
        question_id = self._required_text(request, "curiosity_question_id", "question")
        question = self._questions.get(question_id)
        if question is None:
            return self._response_composer.curiosity_question_missing(
                request,
                question_id,
            )
        if question.status is not CuriosityQuestionStatus.ACCEPTED:
            return self._response_composer.curiosity_rejected(
                request,
                "A research proposal needs an accepted curiosity question; this "
                f"one is {question.status.value}.",
            )
        try:
            run = self._run_manager.get(question.run_id)
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        hypotheses = self._hypotheses_for(run.run_id)
        current = {
            gap.gap_id for gap in self._detector.detect(run, self._clock(), hypotheses)
        }
        if question.gap_id not in current:
            return self._response_composer.curiosity_rejected(
                request,
                "Research proposal not prepared: the originating knowledge gap "
                "is no longer current for this run.",
            )
        try:
            proposal = CuriosityProposalBuilder().build(
                question,
                run,
                self._draft_service,
                hypotheses,
            )
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        self._events.proposal_previewed(proposal)
        return self._response_composer.curiosity_proposal(request, proposal)

    def process_question_accept(self, request: BrainRequest) -> BrainResponse:
        return self._decide(request, accept=True)

    def process_question_dismiss(self, request: BrainRequest) -> BrainResponse:
        return self._decide(request, accept=False)

    def _decide(self, request: BrainRequest, accept: bool) -> BrainResponse:
        """Record a human ruling on one proposal, starting no research."""
        question_id = self._required_text(request, "curiosity_question_id", "question")
        question = self._questions.get(question_id)
        if question is None:
            return self._response_composer.curiosity_question_missing(
                request,
                question_id,
            )
        now = self._clock()
        try:
            updated = question.accepted(now) if accept else question.dismissed(now)
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        self._questions[question_id] = updated
        if accept:
            self._events.question_accepted(updated)
        else:
            self._events.question_dismissed(updated)
        if not self._persist():
            return self._response_composer.curiosity_persistence_failed(
                request,
                f"the ruling on {question_id}",
            )
        return self._response_composer.curiosity_question_decided(request, updated)

    def _detect(
        self,
        request: BrainRequest,
        generate: bool,
    ) -> ResearchCuriosityPreview:
        run_id = self._required_text(request, "research_run_id", "run")
        run = self._run_manager.get(run_id)
        hypotheses = self._hypotheses_for(run.run_id)
        gaps = self._detector.detect(run, self._clock(), hypotheses)
        questions = self._generator.generate(run, gaps, hypotheses) if generate else ()
        return ResearchCuriosityPreview(
            run_id=run.run_id,
            gaps=gaps,
            questions=questions,
        )

    def _hypotheses_for(self, run_id: str) -> tuple[ResearchHypothesis, ...]:
        """Return this run's own hypotheses, or none when there is no store.

        Composing the two aggregates is this layer's job precisely because it
        is the only one that knows a store exists. The detector stays a pure
        reading of what it is handed, and curiosity keeps working unchanged
        wherever no hypothesis store is configured.

        A store that cannot be read is not a reason to fail a read-only report
        about a run. The gaps the run itself exposes are still true, so they
        are still reported, and the hypothesis half is simply absent.
        """
        if self._hypothesis_store is None:
            return ()
        try:
            stored = self._hypothesis_store.load()
        except ResearchError:
            return ()
        return tuple(hypothesis for hypothesis in stored if hypothesis.run_id == run_id)

    def _store(
        self,
        questions: tuple[ResearchCuriosityQuestion, ...],
    ) -> tuple[int, bool]:
        """Add proposals that are new, never overwriting a decided one."""
        stored = 0
        for question in questions:
            existing = self._questions.get(question.question_id)
            if existing is not None:
                continue
            if len(self._questions) >= MAX_CURIOSITY_STORE_QUESTIONS:
                break
            self._questions[question.question_id] = question
            stored += 1
        return stored, self._persist() if stored else True

    def _restore(self) -> None:
        if self._question_store is None:
            return
        for question in self._question_store.load():
            self._questions[question.question_id] = question

    def _persist(self) -> bool:
        """Write durable proposals, reporting rather than swallowing a failure.

        True with no store configured is not a false claim: this runtime keeps
        no proposals, and the desktop offers the surface only where it does.
        """
        if self._question_store is None:
            return True
        try:
            self._question_store.save(list(self._questions.values()))
        except ResearchError:
            return False
        return True

    @staticmethod
    def _required_text(request: BrainRequest, key: str, label: str) -> str:
        value = request.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Curiosity {label} ID cannot be empty.")
        return value.strip()
