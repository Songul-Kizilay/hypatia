from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import KnowledgeError, ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceAcceptanceResult import ResearchSourceAcceptanceResult
from research.ResearchSourceContentRecord import ResearchSourceContentRecord


def source(url: str = "https://example.test/a") -> ResearchSource:
    return ResearchSource(
        url=url,
        title="A source",
        content="Accepted source body text.",
        content_type="text/html",
        fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


class RecordingContentStore:
    """In-memory content store that can fail on demand."""

    def __init__(
        self,
        fail_on_save: bool = False,
        fail_on_rollback: bool = False,
    ) -> None:
        self.records: list[ResearchSourceContentRecord] = []
        self.fail_on_save = fail_on_save
        self.fail_on_rollback = fail_on_rollback
        self.saves = 0

    def load(self) -> list[ResearchSourceContentRecord]:
        return list(self.records)

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        self.saves += 1
        if self.fail_on_save and self.saves == 1:
            raise ResearchError("Content store unavailable.")
        if self.fail_on_rollback and self.saves > 1:
            raise ResearchError("Content rollback unavailable.")
        self.records = list(records)


class FailingRunManager:
    """Run manager whose add_source always rejects."""

    def add_source(
        self,
        run_id: str,
        source_value: object,
        document_id: str,
        requested_url: str | None = None,
        discovery_candidate_id: str | None = None,
    ) -> None:
        raise ResearchError("Research source is already attached to this run.")


class AcceptanceResultTests(unittest.TestCase):
    def test_attempted_and_accepted_are_separate(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceAcceptanceResult(accepted=True, transaction_attempted=False)
        with self.assertRaises(ResearchError):
            ResearchSourceAcceptanceResult(
                accepted=True,
                transaction_attempted=True,
                failure_reason="should not be here",
            )
        with self.assertRaises(ResearchError):
            ResearchSourceAcceptanceResult(accepted=False, transaction_attempted=True)

        attempted = ResearchSourceAcceptanceResult(
            accepted=False,
            transaction_attempted=True,
            failure_reason="did not accept",
        )
        self.assertTrue(attempted.transaction_attempted)
        self.assertFalse(attempted.accepted)


class ResearchSourceAcceptanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.content_store = RecordingContentStore()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _service(self, **overrides: object) -> ResearchSourceAcceptanceService:
        return ResearchSourceAcceptanceService(
            overrides.get("knowledge_engine", self.knowledge_engine),  # type: ignore[arg-type]
            overrides.get("run_manager", self.manager),  # type: ignore[arg-type]
            overrides.get("content_store", self.content_store),  # type: ignore[arg-type]
        )

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def test_successful_acceptance_records_the_source(self) -> None:
        run_id = self._run_id()

        result = self._service().accept(source(), run_id)

        self.assertTrue(result.accepted)
        self.assertTrue(result.transaction_attempted)
        self.assertIsNotNone(result.document_id)
        run = self.manager.get(run_id)
        self.assertEqual(len(run.sources), 1)
        self.assertEqual(len(self.content_store.records), 1)
        self.assertEqual(self.knowledge_engine.document_count(), 1)

    def test_acceptance_creates_no_evidence_or_claims(self) -> None:
        run_id = self._run_id()

        self._service().accept(source(), run_id)

        run = self.manager.get(run_id)
        self.assertEqual(run.evidence, ())
        self.assertEqual(run.assessments, ())
        self.assertEqual(run.claims, ())

    def test_content_failure_rolls_back_knowledge(self) -> None:
        run_id = self._run_id()
        service = self._service(content_store=RecordingContentStore(fail_on_save=True))

        result = service.accept(source(), run_id)

        self.assertFalse(result.accepted)
        self.assertTrue(result.transaction_attempted)
        self.assertIn("knowledge was rolled back", result.failure_reason)
        self.assertEqual(self.knowledge_engine.document_count(), 0)
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_add_source_failure_rolls_back_content_and_knowledge(self) -> None:
        service = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            FailingRunManager(),  # type: ignore[arg-type]
            self.content_store,
        )

        result = service.accept(source(), "run-1")

        self.assertFalse(result.accepted)
        self.assertTrue(result.transaction_attempted)
        self.assertIn("content and knowledge were rolled back", result.failure_reason)
        self.assertEqual(self.knowledge_engine.document_count(), 0)
        self.assertEqual(self.content_store.records, [])

    def test_failed_content_rollback_is_reported_precisely(self) -> None:
        store = RecordingContentStore(fail_on_rollback=True)
        service = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            FailingRunManager(),  # type: ignore[arg-type]
            store,
        )

        result = service.accept(source(), "run-1")

        self.assertFalse(result.accepted)
        self.assertIn("content rollback failed", result.failure_reason)
        self.assertEqual(self.knowledge_engine.document_count(), 0)

    def test_duplicate_source_is_rejected_deterministically(self) -> None:
        run_id = self._run_id()
        service = self._service()
        first = service.accept(source(), run_id)

        self.assertTrue(first.accepted)
        with self.assertRaises(KnowledgeError):
            service.accept(source(), run_id)

        self.assertEqual(len(self.manager.get(run_id).sources), 1)
        self.assertEqual(self.knowledge_engine.document_count(), 1)
        self.assertEqual(len(self.content_store.records), 1)

    def test_unknown_run_leaves_no_mutation(self) -> None:
        result = self._service().accept(source(), "missing-run")

        self.assertFalse(result.accepted)
        self.assertEqual(self.knowledge_engine.document_count(), 0)
        self.assertEqual(self.content_store.records, [])

    def test_indexing_failure_raises_for_the_caller(self) -> None:
        class FailingKnowledgeEngine(KnowledgeEngine):
            def add_document(self, document, stable_chunk_ids: bool = False):  # type: ignore[no-untyped-def]
                raise KnowledgeError("Indexing unavailable.")

        service = ResearchSourceAcceptanceService(
            FailingKnowledgeEngine(),
            self.manager,
            self.content_store,
        )

        with self.assertRaises(KnowledgeError):
            service.accept(source(), self._run_id())

    def test_knowledge_only_acceptance_without_a_run(self) -> None:
        result = self._service().accept(source(), "")

        self.assertTrue(result.accepted)
        self.assertIsNone(result.run)
        self.assertEqual(self.knowledge_engine.document_count(), 1)
        self.assertEqual(self.content_store.records, [])


if __name__ == "__main__":
    unittest.main()
