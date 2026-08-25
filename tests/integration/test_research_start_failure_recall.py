"""A new research question meets what already went wrong on questions like it.

Remembering a failure is only half of learning from one. Until now Hypatia
recalled lessons solely when someone thought to ask for them, which is the
moment they are least likely to think of it. Creating a run now carries the
relevant ones with it.

Advice arrives *with* the run, never instead of it. The run is persisted before
anything here is consulted, so almost every test in this file is one property
seen from a different side: nothing in the advisory path may change the outcome
of creating a run, including by failing. A recall that turned a saved run into
a reported failure would be worse than no recall at all.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.FailureLessonKind import FailureLessonKind
from research.JsonFileFailureLessonStore import JsonFileFailureLessonStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

RECORDED = datetime(2026, 8, 23, tzinfo=UTC)

PRIOR_CONTEXT = "Which observation would change the ring-age hypothesis?"
PRIOR_STATEMENT = (
    'Contradicted hypothesis: "The rings formed recently." - opposing evidence '
    "is recorded without supporting source coverage in this run. No truth or "
    "falsity is decided here."
)

#: Overlaps the remembered lesson on words that identify its subject.
RELATED_QUESTION = "Which observation would settle the ring-age debate?"

#: Overlaps it only on "evidence", which every disproving lesson contains.
UNRELATED_QUESTION = "Does quantum error correction reduce evidence loss?"


class RecordingLLMProvider:
    """Records any model call, so an advisory read can be shown not to make one."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(
        self,
        prompt: str,
        history: tuple[object, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append(prompt)
        return "must not run"


class ResearchStartRecallFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.lesson_path = self.root / "lessons.json"
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.lesson_store = JsonFileFailureLessonStore(self.lesson_path)
        self.llm_provider = RecordingLLMProvider()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.addCleanup(self.temporary_directory.cleanup)

    def remember(self, kind: FailureLessonKind = FailureLessonKind.FAILED_HYPOTHESIS):
        """Put one durable lesson in place before the engine is built."""
        self.lesson_store.save(
            [
                ResearchFailureLesson(
                    lesson_id="lesson:run-old:failed_hypothesis:h1",
                    kind=kind,
                    run_id="run-old",
                    subject_id="h1",
                    statement=PRIOR_STATEMENT,
                    provenance=("h1", "evidence-4"),
                    context=PRIOR_CONTEXT,
                    recorded_at=RECORDED,
                )
            ]
        )

    def engine(self) -> CognitiveEngine:
        memory_manager = MemoryManager(self.event_bus)
        session_manager = SessionManager(self.event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=self.event_bus,
            ),
            llm_provider=self.llm_provider,  # type: ignore[arg-type]
            research_run_manager=self.manager,
            failure_lesson_store=self.lesson_store,
        )

    @staticmethod
    def create(question: str) -> BrainRequest:
        return BrainRequest(
            message="Create internet research run",
            metadata={"intent": "research_run_create", "research_question": question},
        )


class AdviceArrivesWithTheRunTests(ResearchStartRecallFixture):
    def test_a_new_question_meets_what_went_wrong_on_questions_like_it(self) -> None:
        self.remember()

        response = self.engine().process(self.create(RELATED_QUESTION))

        self.assertTrue(response.success)
        self.assertEqual(len(response.failure_lessons), 1)
        self.assertIn("Possibly relevant prior lessons: 1", response.message)
        self.assertIn(PRIOR_STATEMENT, response.message)

    def test_the_run_is_reported_before_the_advice(self) -> None:
        """Advice that reads like a precondition is advice that blocks."""
        self.remember()

        response = self.engine().process(self.create(RELATED_QUESTION))
        lines = response.message.splitlines()

        self.assertLess(
            lines.index(f"ID: {response.research_runs[0].run_id}"),
            lines.index("Possibly relevant prior lessons: 1"),
        )
        self.assertIn("This run was created either way", response.message)

    def test_an_unrelated_question_creates_the_run_and_says_nothing(self) -> None:
        self.remember()

        response = self.engine().process(self.create(UNRELATED_QUESTION))

        self.assertTrue(response.success)
        self.assertEqual(response.failure_lessons, ())
        self.assertNotIn("prior lessons", response.message)
        self.assertEqual(len(self.manager.list()), 1)

    def test_nothing_remembered_leaves_the_report_unchanged(self) -> None:
        response = self.engine().process(self.create(RELATED_QUESTION))

        self.assertTrue(response.success)
        self.assertEqual(response.failure_lessons, ())
        self.assertTrue(response.message.endswith(response.research_runs[0].run_id))


class AdviceCannotHarmTheRunTests(ResearchStartRecallFixture):
    def test_advice_that_raises_still_creates_the_run(self) -> None:
        """The run is already saved. A failure here would be a lie about it."""
        self.remember()
        engine = self.engine()
        service = engine._failure_memory_service
        assert service is not None

        def explode(question: str) -> tuple[ResearchFailureLesson, ...]:
            raise RuntimeError("advice is broken")

        service.advice = explode  # type: ignore[method-assign]
        response = engine.process(self.create(RELATED_QUESTION))

        self.assertTrue(response.success)
        self.assertEqual(response.failure_lessons, ())
        self.assertEqual(len(self.manager.list()), 1)
        self.assertEqual(self.manager.list()[0].question, RELATED_QUESTION)

    def test_a_run_is_created_when_failure_memory_is_absent(self) -> None:
        engine = self.engine()
        engine._failure_memory_service = None

        response = engine.process(self.create(RELATED_QUESTION))

        self.assertTrue(response.success)
        self.assertEqual(response.failure_lessons, ())

    def test_creating_a_run_remembers_nothing_new(self) -> None:
        """Consulting failure memory is a read. It may not derive or store."""
        self.remember()
        before = self.lesson_path.read_bytes()
        engine = self.engine()

        engine.process(self.create(RELATED_QUESTION))

        self.assertEqual(self.lesson_path.read_bytes(), before)
        service = engine._failure_memory_service
        assert service is not None
        self.assertEqual(len(service.lessons()), 1)

    def test_creating_a_run_consults_no_model(self) -> None:
        """Lessons are shown to a person. They never become prompt text."""
        self.remember()

        response = self.engine().process(self.create(RELATED_QUESTION))

        self.assertTrue(response.failure_lessons)
        self.assertEqual(self.llm_provider.calls, [])

    def test_the_only_event_is_the_advisory_read(self) -> None:
        self.remember()

        self.engine().process(self.create(RELATED_QUESTION))

        self.assertEqual(
            [event.name for event in self.events if event.name.startswith("failure")],
            ["failure_memory.lessons_recalled"],
        )


if __name__ == "__main__":
    unittest.main()
