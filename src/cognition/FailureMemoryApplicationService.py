"""Remember what did not work, and offer it back without enforcing it.

The pipeline is derive, store, recall. Derivation reads a persisted run and
produces lessons that each name the records they came from. Storing keeps them.
Recall surfaces the ones whose wording overlaps a new question.

Recall is advisory and stays advisory. Nothing here blocks a plan, refuses a
capability, downgrades a claim, or edits a run: a system that stops doing work
because something similar failed once has replaced research with superstition.
The lessons come back as text for a person to weigh, and every one of them can
be ignored.

Nothing in this service performs research either. Deriving, storing, and
recalling all leave every run byte-identical.

Recall is also offered as a plain read, so a caller can put advice in front of
someone at the moment a new question is asked. That path still decides nothing:
it returns lessons to display and cannot fail the work it accompanies.

Hypothesis outcomes enter through a separate explicit command. That command
reads the durable hypothesis store on every request rather than reaching into
the hypothesis service's in-memory state. A lesson therefore never claims that
an outcome survived restart unless the hypothesis itself did.

A durable-write failure leaves the lessons available in this process but
returns an unsuccessful response. Repeating the explicit store request retries
that pending write; no timer, background loop, or unbounded retry is introduced.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.FailureMemoryEvents import FailureMemoryEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.FailureLessonStore import FailureLessonStore
from research.FailureMemoryAdvisor import FailureMemoryAdvisor
from research.HypothesisFailureLessonDeriver import (
    MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN,
    HypothesisFailureLessonDeriver,
    hypothesis_retention_key,
)
from research.HypothesisStore import HypothesisStore
from research.JsonFileFailureLessonStore import MAX_FAILURE_STORE_LESSONS
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchFailureLessonDeriver import ResearchFailureLessonDeriver
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

FAILURE_LESSON_PREVIEW_INTENT = "failure_memory_preview"
FAILURE_LESSON_STORE_INTENT = "failure_memory_store"
FAILURE_LESSON_LIST_INTENT = "failure_memory_list"
FAILURE_LESSON_RECALL_INTENT = "failure_memory_recall"
HYPOTHESIS_FAILURE_LESSON_STORE_INTENT = "failure_memory_hypothesis_store"


class FailureMemoryApplicationService:
    """Derive, keep, and advisorily recall lessons from failed work."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        deriver: ResearchFailureLessonDeriver | None = None,
        hypothesis_deriver: HypothesisFailureLessonDeriver | None = None,
        hypothesis_appraiser: ResearchHypothesisAppraiser | None = None,
        hypothesis_store: HypothesisStore | None = None,
        advisor: FailureMemoryAdvisor | None = None,
        lesson_store: FailureLessonStore | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._deriver = deriver or ResearchFailureLessonDeriver()
        self._hypothesis_deriver = (
            hypothesis_deriver or HypothesisFailureLessonDeriver()
        )
        self._hypothesis_appraiser = (
            hypothesis_appraiser or ResearchHypothesisAppraiser()
        )
        self._hypothesis_store = hypothesis_store
        self._advisor = advisor or FailureMemoryAdvisor()
        self._lesson_store = lesson_store
        self._events = FailureMemoryEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lessons: dict[str, ResearchFailureLesson] = {}
        self._persistence_pending = False
        self._restore()

    @staticmethod
    def is_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == FAILURE_LESSON_PREVIEW_INTENT

    @staticmethod
    def is_store_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == FAILURE_LESSON_STORE_INTENT

    @staticmethod
    def is_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == FAILURE_LESSON_LIST_INTENT

    @staticmethod
    def is_recall_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == FAILURE_LESSON_RECALL_INTENT

    @staticmethod
    def is_hypothesis_store_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == HYPOTHESIS_FAILURE_LESSON_STORE_INTENT

    def lessons(self) -> tuple[ResearchFailureLesson, ...]:
        """Return every remembered lesson, heaviest first."""
        return tuple(
            sorted(
                self._lessons.values(),
                key=lambda lesson: (-lesson.weight, lesson.lesson_id),
            )
        )

    def process_preview(self, request: BrainRequest) -> BrainResponse:
        """Report the lessons a run supports without remembering any."""
        run_id, derived = self._derive(request)
        self._events.derived(run_id, derived)
        return self._response_composer.failure_lessons(request, derived, False)

    def process_store(self, request: BrainRequest) -> BrainResponse:
        """Remember the lessons a run supports, changing nothing about it."""
        run_id, derived = self._derive(request)
        self._events.derived(run_id, derived)
        stored, persisted = self._store(derived)
        if not persisted:
            return self._response_composer.failure_lessons_persistence_failed(
                request,
                derived,
            )
        self._events.stored(run_id, derived, stored, len(self._lessons))
        return self._response_composer.failure_lessons(request, derived, True)

    def process_hypothesis_store(self, request: BrainRequest) -> BrainResponse:
        """Explicitly remember durable weakened and contradicted hypotheses."""
        run_id = self._required_run_id(request)
        run = self._run_manager.get(run_id)
        store = self._hypothesis_store
        if store is None:
            raise ResearchError("Persisted hypotheses are unavailable.")
        recorded_at = self._clock()
        lessons: list[ResearchFailureLesson] = []
        for hypothesis in store.load():
            if hypothesis.run_id != run.run_id:
                continue
            appraisal = self._hypothesis_appraiser.appraise(hypothesis, run)
            lessons.extend(self._hypothesis_deriver.derive(appraisal, run, recorded_at))
        lessons.sort(key=hypothesis_retention_key)
        derived = tuple(lessons[:MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN])
        dropped = len(lessons) - len(derived)
        self._events.derived(run.run_id, derived)
        stored, persisted = self._store(derived)
        if not persisted:
            return self._response_composer.failure_lessons_persistence_failed(
                request,
                derived,
                dropped=dropped,
            )
        self._events.stored(run.run_id, derived, stored, len(self._lessons))
        return self._response_composer.failure_lessons(
            request,
            derived,
            True,
            dropped=dropped,
        )

    def process_list(self, request: BrainRequest) -> BrainResponse:
        """Report everything remembered, deriving nothing new."""
        return self._response_composer.failure_lesson_list(request, self.lessons())

    def process_recall(self, request: BrainRequest) -> BrainResponse:
        """Offer prior lessons that share wording with a new question."""
        question = request.metadata.get("research_question")
        if not isinstance(question, str) or not question.strip():
            raise ResearchError("Failure recall requires a research question.")
        return self._response_composer.failure_lesson_recall(
            request,
            self.advice(question),
        )

    def advice(self, question: str) -> tuple[ResearchFailureLesson, ...]:
        """Return prior lessons overlapping a question, changing nothing.

        This is recall without a command behind it, so that advice can reach a
        person at the moment it is relevant rather than only when they think to
        ask. It derives no lesson, writes nothing, and leaves every run
        byte-identical.

        An unusable question returns nothing instead of raising. A caller using
        this to decorate work that already succeeded must not be handed an
        exception that turns that success into a failure.
        """
        if not isinstance(question, str) or not question.strip():
            return ()
        relevant = self._advisor.relevant(question, self._lessons.values())
        self._events.recalled(relevant, len(self._lessons))
        return relevant

    def _derive(
        self,
        request: BrainRequest,
    ) -> tuple[str, tuple[ResearchFailureLesson, ...]]:
        run = self._run_manager.get(self._required_run_id(request))
        return run.run_id, self._deriver.derive(run, self._clock())

    @staticmethod
    def _required_run_id(request: BrainRequest) -> str:
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("Failure memory requires a research run ID.")
        return run_id.strip()

    def _store(
        self,
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> tuple[int, bool]:
        """Keep lessons that are new, never rewriting one already remembered."""
        stored = 0
        for lesson in lessons:
            if lesson.lesson_id in self._lessons:
                continue
            if len(self._lessons) >= MAX_FAILURE_STORE_LESSONS:
                break
            self._lessons[lesson.lesson_id] = lesson
            stored += 1
        if stored and self._lesson_store is not None:
            self._persistence_pending = True
        persisted = not self._persistence_pending or self._persist()
        if persisted:
            self._persistence_pending = False
        return stored, persisted

    def _restore(self) -> None:
        if self._lesson_store is None:
            return
        for lesson in self._lesson_store.load():
            self._lessons[lesson.lesson_id] = lesson

    def _persist(self) -> bool:
        """Write remembered lessons, never erasing them silently on failure."""
        if self._lesson_store is None:
            return True
        try:
            self._lesson_store.save(list(self._lessons.values()))
        except ResearchError:
            return False
        return True
