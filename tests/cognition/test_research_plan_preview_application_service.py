"""Application and routing contracts for no-write Research plan previews."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchPlanPreviewApplicationService import (
    ResearchPlanPreviewApplicationService,
)
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.FailureLessonKind import FailureLessonKind
from research.JsonFileFailureLessonStore import JsonFileFailureLessonStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class ResearchPlanPreviewApplicationServiceTests(unittest.TestCase):
    def test_recognizer_accepts_only_the_exact_structured_intent(self) -> None:
        service = ResearchPlanPreviewApplicationService(ResponseComposer())

        self.assertTrue(
            service.is_draft_preview_request(
                BrainRequest(
                    "ignored",
                    metadata={"intent": "research_plan_draft_preview"},
                )
            )
        )
        self.assertFalse(
            service.is_draft_preview_request(
                BrainRequest("research plan draft preview")
            )
        )

    def test_process_delegates_exact_metadata_and_composes_exact_preview(self) -> None:
        composer = Mock(spec=ResponseComposer)
        draft_service = Mock(spec=ResearchPlanDraftService)
        service = ResearchPlanPreviewApplicationService(composer, draft_service)
        question = "Compare findings."
        steps = (("Review.", ("document-1",)),)
        request = BrainRequest(
            "ignored",
            metadata={
                "research_plan_question": question,
                "research_plan_steps": steps,
            },
        )
        preview = ResearchPlanDraftPreview.rejected("bounded")
        response = BrainResponse("ok", request.request_id, "test", 0)
        draft_service.preview.return_value = preview
        composer.research_plan_draft_preview.return_value = response

        result = service.process_draft_preview(request)

        self.assertIs(result, response)
        draft_service.preview.assert_called_once_with(question, steps)
        composer.research_plan_draft_preview.assert_called_once_with(
            request,
            preview,
            (),
        )

    def test_valid_preview_receives_advice_for_its_canonical_question(self) -> None:
        composer = Mock(spec=ResponseComposer)
        lesson_advisor = Mock(return_value=())
        service = ResearchPlanPreviewApplicationService(
            composer,
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
                id_factory=lambda: "plan-1",
            ),
            lesson_advisor,
        )
        request = BrainRequest(
            "ignored",
            metadata={
                "research_plan_question": "  Compare findings.  ",
                "research_plan_steps": (("Review.", ()),),
            },
        )

        service.process_draft_preview(request)

        lesson_advisor.assert_called_once_with("Compare findings.")

    def test_rejected_preview_does_not_consult_failure_memory(self) -> None:
        lesson_advisor = Mock(return_value=())
        service = ResearchPlanPreviewApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(),
            lesson_advisor,
        )

        response = service.process_draft_preview(BrainRequest("ignored"))

        self.assertFalse(response.success)
        lesson_advisor.assert_not_called()

    def test_broken_advice_cannot_turn_a_valid_preview_into_failure(self) -> None:
        def explode(question: str) -> tuple[ResearchFailureLesson, ...]:
            raise RuntimeError(question)

        service = ResearchPlanPreviewApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
                id_factory=lambda: "plan-1",
            ),
            explode,
        )
        request = BrainRequest(
            "ignored",
            metadata={
                "research_plan_question": "Compare findings.",
                "research_plan_steps": (("Review.", ()),),
            },
        )

        response = service.process_draft_preview(request)

        self.assertTrue(response.success)
        self.assertEqual(response.failure_lessons, ())

    def test_missing_metadata_is_delegated_to_bounded_validation(self) -> None:
        service = ResearchPlanPreviewApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
                id_factory=lambda: "plan-1",
            ),
        )

        response = service.process_draft_preview(BrainRequest("ignored"))

        self.assertFalse(response.success)
        preview = response.research_plan_draft_preview
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertFalse(preview.allowed)
        self.assertIsNone(preview.plan)


class ResearchPlanPreviewCognitiveRoutingTests(unittest.TestCase):
    def test_structured_preview_routes_without_memory_knowledge_or_events(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        knowledge_engine = KnowledgeEngine()
        rename_service = SessionRenameTransactionService(
            session_manager=session_manager,
            memory_manager=memory_manager,
            event_bus=event_bus,
        )
        draft_service = ResearchPlanDraftService(
            clock=lambda: datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
            id_factory=lambda: "plan-1",
        )
        engine = CognitiveEngine(
            knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            rename_service,
            research_plan_draft_service=draft_service,
        )
        memory_count = memory_manager.count()
        documents_before = knowledge_engine.documents()
        events: list[str] = []
        event_bus.subscribe("*", lambda event: events.append(event.name))

        response = engine.process(
            BrainRequest(
                "Preview explicit authored research plan",
                request_id="plan-preview-1",
                metadata={
                    "intent": "research_plan_draft_preview",
                    "research_plan_question": "Compare findings.",
                    "research_plan_steps": (
                        ("Review sources.", ("document-1",)),
                        ("Record gaps.", ()),
                    ),
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "research_plan_draft_preview")
        self.assertEqual(response.request_id, "plan-preview-1")
        preview = response.research_plan_draft_preview
        self.assertIsNotNone(preview)
        assert preview is not None and preview.plan is not None
        self.assertEqual(preview.plan.plan_id, "plan-1")
        self.assertEqual(
            tuple(step.instruction for step in preview.plan.steps),
            ("Review sources.", "Record gaps."),
        )
        self.assertEqual(memory_manager.count(), memory_count)
        self.assertEqual(knowledge_engine.documents(), documents_before)
        self.assertEqual(events, [])

    def test_preview_surfaces_durable_related_lessons_without_starting_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lesson_store = JsonFileFailureLessonStore(root / "lessons.json")
            lesson_store.save(
                [
                    ResearchFailureLesson(
                        lesson_id="lesson:run-old:failed_hypothesis:h1",
                        kind=FailureLessonKind.FAILED_HYPOTHESIS,
                        run_id="run-old",
                        subject_id="h1",
                        statement=(
                            "The earlier ring-age hypothesis lacked opposing "
                            "evidence."
                        ),
                        provenance=("h1", "evidence-4"),
                        context=(
                            "Which observation would change the ring-age " "hypothesis?"
                        ),
                        recorded_at=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
                    )
                ]
            )
            lessons_before = (root / "lessons.json").read_bytes()
            run_manager = ResearchRunManager(
                JsonFileResearchRunStore(root / "runs.json")
            )
            run_manager.load()
            event_bus = EventBus()
            memory_manager = MemoryManager(event_bus)
            session_manager = SessionManager(event_bus)
            knowledge_engine = KnowledgeEngine()
            events: list[str] = []
            event_bus.subscribe("*", lambda event: events.append(event.name))
            engine = CognitiveEngine(
                knowledge_engine,
                memory_manager,
                Planner(),
                event_bus,
                ResponseComposer(),
                session_manager,
                SessionRenameTransactionService(
                    session_manager=session_manager,
                    memory_manager=memory_manager,
                    event_bus=event_bus,
                ),
                research_run_manager=run_manager,
                failure_lesson_store=lesson_store,
                research_plan_draft_service=ResearchPlanDraftService(
                    clock=lambda: datetime(2026, 8, 22, 18, 0, tzinfo=UTC),
                    id_factory=lambda: "plan-1",
                ),
            )

            response = engine.process(
                BrainRequest(
                    "Preview explicit authored research plan",
                    metadata={
                        "intent": "research_plan_draft_preview",
                        "research_plan_question": (
                            "Which observation would settle the ring-age debate?"
                        ),
                        "research_plan_steps": (("Review observations.", ()),),
                    },
                )
            )

            self.assertTrue(response.success)
            self.assertEqual(len(response.failure_lessons), 1)
            self.assertIn("Possibly relevant prior lessons: 1", response.message)
            self.assertEqual(run_manager.list(), [])
            self.assertEqual((root / "lessons.json").read_bytes(), lessons_before)
            self.assertEqual(events, ["failure_memory.lessons_recalled"])


if __name__ == "__main__":
    unittest.main()
