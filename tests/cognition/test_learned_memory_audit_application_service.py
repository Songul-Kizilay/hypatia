from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.LearnedMemoryAuditApplicationService import (
    LEARNED_MEMORY_AUDIT_INTENT,
    LearnedMemoryAuditApplicationService,
)
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMConversationMessage import LLMConversationMessage
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCorrection import correct_learned_memory_value
from memory.LearnedMemoryStore import append_learned_memory
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class CountingLLMProvider:
    """Record every language-model call reaching the engine."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        del history, system_instruction
        self.calls.append(prompt)
        return "Understood."


class CountingSemanticRuntime:
    """Record every semantic query reaching the runtime."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def attach(self, event_bus: object) -> None:
        return None

    def start_refresh(self, *args: object, **kwargs: object) -> str:
        return "started"

    def search(
        self,
        source_text: str,
        *,
        limit: int | None = None,
    ) -> tuple[()]:
        del limit
        self.queries.append(source_text)
        return ()


class LearnedMemoryAuditApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.response_composer = ResponseComposer()
        self.service = LearnedMemoryAuditApplicationService(
            self.memory_manager,
            self.response_composer,
        )

    def _remember(self, kind: str, key: str, value: str) -> None:
        append_learned_memory(
            self.memory_manager,
            LearnedMemory(kind=kind, key=key, value=value),  # type: ignore[arg-type]
        )

    def test_recognizes_only_the_explicit_structured_intent(self) -> None:
        self.assertTrue(
            self.service.is_audit_request(
                BrainRequest(
                    message="",
                    metadata={"intent": LEARNED_MEMORY_AUDIT_INTENT},
                )
            )
        )
        self.assertFalse(
            self.service.is_audit_request(BrainRequest(message="audit memory"))
        )
        self.assertFalse(
            self.service.is_audit_request(
                BrainRequest(message="", metadata={"intent": "recall"})
            )
        )

    def test_empty_store_renders_bounded_report(self) -> None:
        response = self.service.process_audit(
            BrainRequest(message="", metadata={"intent": LEARNED_MEMORY_AUDIT_INTENT})
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "learned_memory_audit")
        self.assertIsNotNone(response.learned_memory_audit)
        assert response.learned_memory_audit is not None
        self.assertEqual(response.learned_memory_audit.total_learned_records, 0)
        self.assertIn("Total learned records: 0", response.message)
        self.assertIn("Persistent writes: not used", response.message)
        self.assertIn(
            "Merges, deletions, and rewrites: not performed",
            response.message,
        )

    def test_report_message_omits_stored_values(self) -> None:
        self._remember("preference", "favorite_planet", "Jupiter")
        correct_learned_memory_value(
            self.memory_manager,
            kind="preference",
            key="favorite_planet",
            value="Saturn",
        )
        self._remember("preference", "preferred_planet", "Saturn")

        response = self.service.process_audit(
            BrainRequest(message="", metadata={"intent": LEARNED_MEMORY_AUDIT_INTENT})
        )

        self.assertNotIn("Jupiter", response.message)
        self.assertNotIn("Saturn", response.message)
        self.assertIn("favorite_planet", response.message)
        self.assertIn("Conflicting-history identities: 1", response.message)

    def test_audit_is_deterministic_and_writes_nothing(self) -> None:
        self._remember("preference", "favorite_planet", "Jupiter")
        correct_learned_memory_value(
            self.memory_manager,
            kind="preference",
            key="favorite_planet",
            value="Saturn",
        )
        request = BrainRequest(
            message="",
            metadata={"intent": LEARNED_MEMORY_AUDIT_INTENT},
        )
        before = [record.memory_id for record in self.memory_manager.all()]
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        first = self.service.process_audit(request)
        second = self.service.process_audit(request)

        self.assertEqual(first.learned_memory_audit, second.learned_memory_audit)
        self.assertEqual(first.message, second.message)
        self.assertEqual(
            [record.memory_id for record in self.memory_manager.all()],
            before,
        )
        self.assertEqual(events, [])


class LearnedMemoryAuditRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        path = Path(self.temporary_directory.name) / "knowledge.md"
        path.write_text("Hypatia\n\nKnowledge", encoding="utf-8")
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(path)
        self.session_manager = SessionManager(self.event_bus)
        self.llm_provider = CountingLLMProvider()
        self.semantic_runtime = CountingSemanticRuntime()
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            llm_provider=self.llm_provider,
            semantic_memory_index_runtime=self.semantic_runtime,  # type: ignore[arg-type]
            chat_semantic_memory_enabled=True,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_structured_request_reaches_the_audit_without_provider_calls(self) -> None:
        append_learned_memory(
            self.memory_manager,
            LearnedMemory(
                kind="preference",
                key="favorite_planet",
                value="Saturn",
            ),
        )

        response = self.engine.process(
            BrainRequest(
                message="",
                metadata={"intent": LEARNED_MEMORY_AUDIT_INTENT},
                request_id="request-audit",
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "learned_memory_audit")
        self.assertEqual(response.request_id, "request-audit")
        assert response.learned_memory_audit is not None
        self.assertEqual(response.learned_memory_audit.active_memories, 1)
        self.assertEqual(self.llm_provider.calls, [])
        self.assertEqual(self.semantic_runtime.queries, [])

    def test_plain_conversation_never_triggers_the_audit(self) -> None:
        response = self.engine.process(BrainRequest(message="audit my memory please"))

        self.assertNotEqual(response.intent, "learned_memory_audit")
        self.assertIsNone(response.learned_memory_audit)


class ResearchPlanExecutionRouteTests(unittest.TestCase):
    """The engine must only route; execution state lives in the service."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        path = Path(self.temporary_directory.name) / "knowledge.md"
        path.write_text("Hypatia\n\nKnowledge", encoding="utf-8")
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(path)
        self.session_manager = SessionManager(self.event_bus)
        self.llm_provider = CountingLLMProvider()
        self.engine = CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            SessionRenameTransactionService(
                session_manager=self.session_manager,
                memory_manager=self.memory_manager,
                event_bus=self.event_bus,
            ),
            llm_provider=self.llm_provider,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_engine_routes_start_status_and_cancel_without_owning_state(self) -> None:
        started = self.engine.process(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": "research_plan_execution_start",
                    "research_plan_question": "What evidence supports the claim?",
                    "research_plan_steps": (("Collect sources", ()),),
                },
            )
        )

        self.assertTrue(started.success)
        self.assertEqual(started.intent, "research_plan_execution")
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        self.assertFalse(started.research_plan_execution.performed_research_work)
        self.assertFalse(hasattr(self.engine, "_executions"))

        status = self.engine.process(
            BrainRequest(
                message="Research plan execution",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": plan_id,
                },
            )
        )
        self.assertTrue(status.success)

        cancelled = self.engine.process(
            BrainRequest(
                message="Research plan execution",
                metadata={
                    "intent": "research_plan_execution_cancel",
                    "research_plan_id": plan_id,
                },
            )
        )
        self.assertTrue(cancelled.success)
        assert cancelled.research_plan_execution is not None
        self.assertEqual(
            cancelled.research_plan_execution.status.value,
            "cancelled",
        )
        self.assertEqual(self.llm_provider.calls, [])

    def test_execution_routes_never_write_memory(self) -> None:
        before = len(self.memory_manager.all())

        self.engine.process(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": "research_plan_execution_start",
                    "research_plan_question": "What evidence supports the claim?",
                    "research_plan_steps": (("Collect sources", ()),),
                },
            )
        )

        self.assertEqual(len(self.memory_manager.all()), before)


if __name__ == "__main__":
    unittest.main()
