"""Tests for fail-closed accepted research content startup restoration."""

from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import KnowledgeError, ResearchError
from knowledge.Document import Document
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceContentRestorer import ResearchSourceContentRestorer


class RecordingContentStore:
    def __init__(self, records: list[ResearchSourceContentRecord]) -> None:
        self.records = list(records)
        self.load_calls = 0
        self.save_calls = 0

    def load(self) -> list[ResearchSourceContentRecord]:
        self.load_calls += 1
        return list(self.records)

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        self.save_calls += 1
        raise AssertionError("Startup restoration must not write content storage.")


class FailingSecondKnowledgeEngine(KnowledgeEngine):
    def __init__(self) -> None:
        super().__init__()
        self.add_calls = 0
        self.clear_calls = 0

    def add_document(self, document: Document) -> Document:
        self.add_calls += 1
        if self.add_calls == 2:
            raise KnowledgeError("Injected second-document failure.")
        return super().add_document(document)

    def clear(self) -> None:
        self.clear_calls += 1
        super().clear()


class ResearchSourceContentRestorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fetched_at = datetime(2026, 8, 20, 12, 30, tzinfo=UTC)

    def _source(
        self,
        suffix: str = "one",
        *,
        title: str | None = None,
        content: str | None = None,
    ) -> ResearchSource:
        return ResearchSource(
            url=f"https://example.com/{suffix}",
            title=title or f"Source {suffix}",
            content=content or f"Accepted finding {suffix}.",
            content_type="text/plain",
            fetched_at=self.fetched_at,
        )

    def _run(
        self,
        source: ResearchSource,
        *,
        run_id: str = "run-1",
        document_id: str | None = None,
    ) -> ResearchRun:
        manager = ResearchRunManager(id_factory=lambda: run_id)
        run = manager.create(f"Question for {run_id}")
        return manager.add_source(
            run.run_id,
            source,
            document_id or source.to_document().document_id,
        )

    def _record(
        self,
        source: ResearchSource,
        document_id: str | None = None,
    ) -> ResearchSourceContentRecord:
        return ResearchSourceContentRecord.from_source(
            source,
            document_id or source.to_document().document_id,
            self.fetched_at + timedelta(minutes=1),
        )

    def test_matching_content_is_restored_without_persistent_writes(self) -> None:
        source = self._source()
        record = self._record(source)
        store = RecordingContentStore([record])
        knowledge_engine = KnowledgeEngine()
        restorer = ResearchSourceContentRestorer(store, knowledge_engine)

        restored = restorer.restore([self._run(source)])

        self.assertTrue(restored.available)
        self.assertEqual(restored.restored_document_count, 1)
        self.assertEqual(restored.restored_paragraph_count, 1)
        self.assertEqual(store.load_calls, 1)
        self.assertEqual(store.save_calls, 0)
        self.assertEqual(len(knowledge_engine.documents()), 1)
        self.assertEqual(
            knowledge_engine.documents()[0].document_id, record.document_id
        )
        self.assertEqual(
            knowledge_engine.search("accepted")[0].document_id,
            record.document_id,
        )

    def test_missing_content_snapshot_is_a_no_op(self) -> None:
        store = RecordingContentStore([])
        knowledge_engine = KnowledgeEngine()

        restored = ResearchSourceContentRestorer(store, knowledge_engine).restore([])

        self.assertTrue(restored.available)
        self.assertEqual(restored.restored_document_count, 0)
        self.assertEqual(restored.restored_paragraph_count, 0)
        self.assertEqual(knowledge_engine.documents(), [])
        self.assertEqual(store.save_calls, 0)

    def test_orphan_or_mismatched_content_is_rejected_before_indexing(self) -> None:
        source = self._source()
        cases: tuple[tuple[list[ResearchRun], str], ...] = (
            ([], "no accepted provenance"),
            ([self._run(self._source(title="Changed title"))], "does not match"),
        )
        for runs, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                knowledge_engine = KnowledgeEngine()
                restorer = ResearchSourceContentRestorer(
                    RecordingContentStore([self._record(source)]),
                    knowledge_engine,
                )

                with self.assertRaisesRegex(ResearchError, expected_message):
                    restorer.restore(runs)

                self.assertEqual(knowledge_engine.documents(), [])

    def test_conflicting_run_provenance_is_rejected_before_indexing(self) -> None:
        source = self._source()
        conflicting = self._source(title="Conflicting title")
        document_id = source.to_document().document_id
        restorer = ResearchSourceContentRestorer(
            RecordingContentStore([self._record(source)]),
            KnowledgeEngine(),
        )

        with self.assertRaisesRegex(ResearchError, "conflicting source provenance"):
            restorer.restore(
                [
                    self._run(source, run_id="run-1", document_id=document_id),
                    self._run(
                        conflicting,
                        run_id="run-2",
                        document_id=document_id,
                    ),
                ]
            )

    def test_invalid_stable_document_id_and_noncanonical_content_are_rejected(
        self,
    ) -> None:
        source = self._source()
        invalid_id = "wrong-document-id"
        padded_content = f" {source.content} "
        encoded = padded_content.encode("utf-8")
        padded_record = ResearchSourceContentRecord(
            document_id=source.to_document().document_id,
            url=source.url,
            title=source.title,
            content=padded_content,
            content_type=source.content_type,
            fetched_at=source.fetched_at,
            stored_at=source.fetched_at + timedelta(minutes=1),
            content_byte_count=len(encoded),
            content_sha256=hashlib.sha256(encoded).hexdigest(),
        )
        cases = (
            (
                self._record(source, invalid_id),
                [self._run(source, document_id=invalid_id)],
                "invalid document ID",
            ),
            (padded_record, [self._run(source)], "not canonical"),
        )
        for record, runs, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                knowledge_engine = KnowledgeEngine()

                with self.assertRaisesRegex(ResearchError, expected_message):
                    ResearchSourceContentRestorer(
                        RecordingContentStore([record]),
                        knowledge_engine,
                    ).restore(runs)

                self.assertEqual(knowledge_engine.documents(), [])

    def test_nonempty_index_is_preserved_and_rejected(self) -> None:
        source = self._source()
        knowledge_engine = KnowledgeEngine()
        existing = knowledge_engine.add_document(self._source("existing").to_document())

        with self.assertRaisesRegex(ResearchError, "empty knowledge index"):
            ResearchSourceContentRestorer(
                RecordingContentStore([self._record(source)]),
                knowledge_engine,
            ).restore([self._run(source)])

        self.assertEqual(
            [document.document_id for document in knowledge_engine.documents()],
            [existing.document_id],
        )

    def test_oversized_restored_paragraph_set_is_rejected_before_indexing(
        self,
    ) -> None:
        source = self._source()
        knowledge_engine = KnowledgeEngine()
        restorer = ResearchSourceContentRestorer(
            RecordingContentStore([self._record(source)]),
            knowledge_engine,
        )

        with (
            patch.object(restorer, "_MAXIMUM_RESTORED_PARAGRAPHS", 0),
            self.assertRaisesRegex(ResearchError, "too many paragraphs"),
        ):
            restorer.restore([self._run(source)])

        self.assertEqual(knowledge_engine.documents(), [])

    def test_indexing_failure_clears_every_partially_restored_document(self) -> None:
        first = self._source("one")
        second = self._source("two")
        knowledge_engine = FailingSecondKnowledgeEngine()
        restorer = ResearchSourceContentRestorer(
            RecordingContentStore([self._record(first), self._record(second)]),
            knowledge_engine,
        )

        with self.assertRaisesRegex(ResearchError, "Unable to restore"):
            restorer.restore(
                [
                    self._run(first, run_id="run-1"),
                    self._run(second, run_id="run-2"),
                ]
            )

        self.assertEqual(knowledge_engine.add_calls, 2)
        self.assertEqual(knowledge_engine.clear_calls, 1)
        self.assertEqual(knowledge_engine.documents(), [])
        self.assertEqual(knowledge_engine.search("accepted"), [])


if __name__ == "__main__":
    unittest.main()
