"""Read-only cognition coverage for research evidence integrity status."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
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
from research.ResearchEvidenceIntegrityAuditor import (
    ResearchEvidenceIntegrityAuditor,
)
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class RunStoreMustNotRunDuringAudit:
    def __init__(self) -> None:
        self.save_calls = 0
        self.audit_started = False

    def load(self) -> list[ResearchRun]:
        raise AssertionError("Evidence integrity must not read run persistence.")

    def save(self, runs: list[ResearchRun]) -> None:
        if self.audit_started:
            raise AssertionError("Evidence integrity must not write run persistence.")
        self.save_calls += 1


class ContentStoreMustNotRun:
    def load(self) -> list[ResearchSourceContentRecord]:
        raise AssertionError("Evidence integrity must not read content persistence.")

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        raise AssertionError("Evidence integrity must not write content persistence.")


class SourceFetcherMustNotRun:
    def fetch(self, url: str) -> ResearchSource:
        raise AssertionError("Evidence integrity must not access the network.")


class ResearchEvidenceIntegrityStatusCognitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.session_manager = SessionManager(self.event_bus)
        self.knowledge_engine = KnowledgeEngine()
        self.rename_service = SessionRenameTransactionService(
            session_manager=self.session_manager,
            memory_manager=self.memory_manager,
            event_bus=self.event_bus,
        )
        self.run_store = RunStoreMustNotRunDuringAudit()
        self.run_manager = ResearchRunManager(
            self.run_store,
            clock=lambda: self.now,
            id_factory=lambda: "run-1",
            evidence_id_factory=lambda: "evidence-1",
        )

    def _engine(self, *, available: bool) -> CognitiveEngine:
        return CognitiveEngine(
            self.knowledge_engine,
            self.memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            self.session_manager,
            self.rename_service,
            research_source_fetcher=SourceFetcherMustNotRun(),
            research_run_manager=self.run_manager if available else None,
            research_source_content_store=ContentStoreMustNotRun(),
            research_evidence_integrity_auditor=(
                ResearchEvidenceIntegrityAuditor(self.knowledge_engine)
                if available
                else None
            ),
        )

    def test_structured_status_audits_in_memory_without_side_effects(self) -> None:
        source = ResearchSource(
            url="https://example.com/evidence",
            title="Evidence source",
            content="Accepted paragraph.",
            content_type="text/plain",
            fetched_at=self.now,
        )
        document = self.knowledge_engine.add_document(
            source.to_document(),
            stable_chunk_ids=True,
        )
        run = self.run_manager.create("Which evidence remains connected?")
        self.run_manager.add_source(run.run_id, source, document.document_id)
        chunk = self.knowledge_engine.chunks()[0]
        self.run_manager.add_evidence(run.run_id, chunk, "User-selected note.")
        save_calls = self.run_store.save_calls
        memory_count = self.memory_manager.count()
        chunks_before = self.knowledge_engine.chunks()
        self.run_store.audit_started = True

        response = self._engine(available=True).process(
            BrainRequest(
                message="Audit research evidence integrity",
                request_id="evidence-integrity-1",
                metadata={"intent": "research_evidence_integrity_status"},
            )
        )

        status = response.research_evidence_integrity_status
        self.assertIsNotNone(status)
        assert status is not None
        self.assertTrue(status.available)
        self.assertEqual(status.recorded_evidence_count, 1)
        self.assertEqual(status.matched_evidence_count, 1)
        self.assertEqual(status.missing_evidence_count, 0)
        self.assertEqual(status.changed_evidence_count, 0)
        self.assertEqual(response.request_id, "evidence-integrity-1")
        self.assertEqual(response.intent, "research_evidence_integrity_status")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Research evidence integrity status:\n"
            "Runtime: ready\n"
            "Recorded evidence: 1\n"
            "Matched restored paragraphs: 1\n"
            "Missing restored paragraphs: 0\n"
            "Changed restored paragraphs: 0\n"
            "Network access: not used\n"
            "Persistent writes: not used",
        )
        self.assertEqual(self.run_store.save_calls, save_calls)
        self.assertEqual(self.memory_manager.count(), memory_count)
        self.assertEqual(self.knowledge_engine.chunks(), chunks_before)

    def test_plain_status_command_reports_safe_unavailable_state(self) -> None:
        response = self._engine(available=False).process(
            BrainRequest(
                message="  ReSeArCh EvIdEnCe StAtUs  ",
                request_id="evidence-integrity-2",
            )
        )

        status = response.research_evidence_integrity_status
        self.assertIsNotNone(status)
        assert status is not None
        self.assertFalse(status.available)
        self.assertEqual(
            response.message,
            "Research evidence integrity status:\n"
            "Runtime: unavailable\n"
            "Recorded evidence: unavailable\n"
            "Matched restored paragraphs: unavailable\n"
            "Missing restored paragraphs: unavailable\n"
            "Changed restored paragraphs: unavailable\n"
            "Network access: not used\n"
            "Persistent writes: not used",
        )


if __name__ == "__main__":
    unittest.main()
