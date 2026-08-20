"""Read-only cognition coverage for accepted-content restoration status."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class ContentStoreMustNotRun:
    def load(self) -> list[ResearchSourceContentRecord]:
        raise AssertionError("Restoration status must not read persistence.")

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        raise AssertionError("Restoration status must not write persistence.")


class ResearchSourceContentRestorationStatusCognitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.session_manager = SessionManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.rename_service = SessionRenameTransactionService(
            session_manager=self.session_manager,
            memory_manager=self.memory_manager,
            event_bus=self.event_bus,
        )

    def _engine(
        self,
        status: ResearchSourceContentRestorationStatus | None,
    ) -> CognitiveEngine:
        return CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            self.rename_service,
            research_source_content_store=ContentStoreMustNotRun(),
            research_source_content_restoration_status=status,
        )

    def test_structured_status_returns_captured_aggregate_without_side_effects(
        self,
    ) -> None:
        status = ResearchSourceContentRestorationStatus(True, 2, 7)
        memory_count = self.memory_manager.count()
        documents_before = self.knowledge_engine.documents()

        response = self._engine(status).process(
            BrainRequest(
                message="Show accepted research content health",
                request_id="restoration-status-1",
                metadata={"intent": "research_source_content_restoration_status"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(
            response.intent,
            "research_source_content_restoration_status",
        )
        self.assertEqual(response.request_id, "restoration-status-1")
        self.assertEqual(response.memory_count, 0)
        self.assertIs(response.research_source_content_restoration_status, status)
        self.assertEqual(
            response.message,
            "Research content restoration status:\n"
            "Runtime: ready\n"
            "Restored documents: 2\n"
            "Restored paragraphs: 7\n"
            "Network access: not used\n"
            "Persistent writes: not used",
        )
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(self.knowledge_engine.documents(), documents_before)

    def test_plain_status_command_reports_safe_unavailable_state(self) -> None:
        response = self._engine(None).process(
            BrainRequest(
                message="  ReSeArCh CoNtEnT StAtUs  ",
                request_id="restoration-status-2",
            )
        )

        status = response.research_source_content_restoration_status
        self.assertIsNotNone(status)
        assert status is not None
        self.assertFalse(status.available)
        self.assertEqual(
            response.message,
            "Research content restoration status:\n"
            "Runtime: unavailable\n"
            "Restored documents: unavailable\n"
            "Restored paragraphs: unavailable\n"
            "Network access: not used\n"
            "Persistent writes: not used",
        )


if __name__ == "__main__":
    unittest.main()
