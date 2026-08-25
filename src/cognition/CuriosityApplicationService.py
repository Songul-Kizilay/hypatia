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
from research.CuriosityQuestionStore import CuriosityQuestionStore
from research.JsonFileCuriosityQuestionStore import MAX_CURIOSITY_STORE_QUESTIONS
from research.ResearchCuriosityPreview import ResearchCuriosityPreview
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

CURIOSITY_GAP_DETECT_INTENT = "curiosity_gap_detect"
CURIOSITY_QUESTION_PREVIEW_INTENT = "curiosity_question_preview"
CURIOSITY_QUESTION_STORE_INTENT = "curiosity_question_store"
CURIOSITY_QUESTION_LIST_INTENT = "curiosity_question_list"
CURIOSITY_QUESTION_ACCEPT_INTENT = "curiosity_question_accept"
CURIOSITY_QUESTION_DISMISS_INTENT = "curiosity_question_dismiss"


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
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._detector = detector or ResearchKnowledgeGapDetector()
        self._generator = generator or ResearchCuriosityQuestionGenerator()
        self._question_store = question_store
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
        gaps = self._detector.detect(run, self._clock())
        questions = self._generator.generate(run, gaps) if generate else ()
        return ResearchCuriosityPreview(
            run_id=run.run_id,
            gaps=gaps,
            questions=questions,
        )

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
