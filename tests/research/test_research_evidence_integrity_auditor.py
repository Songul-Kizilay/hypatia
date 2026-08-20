"""Read-only evidence-to-restored-paragraph integrity audit tests."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from knowledge.Document import Document
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchEvidenceIntegrityAuditor import (
    ResearchEvidenceIntegrityAuditor,
)
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


class DuplicateLocatorKnowledgeEngine(KnowledgeEngine):
    def chunks(self) -> list[Chunk]:
        return [
            Chunk("document-1", 0, "First", chunk_id="chunk-1"),
            Chunk("document-1", 0, "Second", chunk_id="chunk-2"),
        ]


class OversizedKnowledgeEngine(KnowledgeEngine):
    def chunk_count(self) -> int:
        return 1

    def chunks(self) -> list[Chunk]:
        raise AssertionError("An oversized index must not be copied or scanned.")


class ResearchEvidenceIntegrityAuditorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)

    def test_classifies_matching_missing_and_changed_evidence_without_mutation(
        self,
    ) -> None:
        engine = KnowledgeEngine()
        engine.add_document(
            Document(
                title="Matching",
                content="Matching paragraph.",
                document_id="document-match",
            ),
            stable_chunk_ids=True,
        )
        engine.add_document(
            Document(
                title="Changed",
                content="Current paragraph.",
                document_id="document-change",
            ),
            stable_chunk_ids=True,
        )
        matching_chunk = engine.chunks()[0]
        evidence = (
            self._evidence("evidence-match", matching_chunk),
            self._evidence(
                "evidence-change",
                Chunk(
                    "document-change",
                    0,
                    "Prior paragraph.",
                    chunk_id="prior-chunk",
                ),
            ),
            self._evidence(
                "evidence-missing",
                Chunk(
                    "document-missing",
                    0,
                    "Missing paragraph.",
                    chunk_id="missing-chunk",
                ),
            ),
        )
        run = self._run(evidence)
        chunks_before = engine.chunks()

        status = ResearchEvidenceIntegrityAuditor(engine).audit([run])

        self.assertTrue(status.available)
        self.assertEqual(status.recorded_evidence_count, 3)
        self.assertEqual(status.matched_evidence_count, 1)
        self.assertEqual(status.missing_evidence_count, 1)
        self.assertEqual(status.changed_evidence_count, 1)
        self.assertEqual(engine.chunks(), chunks_before)
        self.assertEqual(run.evidence, evidence)

    def test_empty_snapshot_is_ready_with_zero_counts(self) -> None:
        status = ResearchEvidenceIntegrityAuditor(KnowledgeEngine()).audit([])

        self.assertTrue(status.available)
        self.assertEqual(status.recorded_evidence_count, 0)

    def test_bound_and_ambiguous_locator_return_safe_unavailable_state(self) -> None:
        evidence = self._evidence(
            "evidence-1",
            Chunk("document-1", 0, "Paragraph.", chunk_id="chunk-1"),
        )
        run = self._run((evidence,))

        with patch(
            "research.ResearchEvidenceIntegrityAuditor."
            "MAX_AUDITED_RESEARCH_EVIDENCE",
            0,
        ):
            bounded = ResearchEvidenceIntegrityAuditor(KnowledgeEngine()).audit([run])
        with patch(
            "research.ResearchEvidenceIntegrityAuditor.MAX_AUDITED_RESEARCH_RUNS",
            0,
        ):
            oversized_run_collection = ResearchEvidenceIntegrityAuditor(
                KnowledgeEngine()
            ).audit([run])
        with patch(
            "research.ResearchEvidenceIntegrityAuditor." "MAX_AUDITED_RESEARCH_CHUNKS",
            0,
        ):
            oversized_index = ResearchEvidenceIntegrityAuditor(
                OversizedKnowledgeEngine()
            ).audit([run])
        ambiguous = ResearchEvidenceIntegrityAuditor(
            DuplicateLocatorKnowledgeEngine()
        ).audit([run])

        self.assertFalse(bounded.available)
        self.assertFalse(oversized_run_collection.available)
        self.assertFalse(oversized_index.available)
        self.assertFalse(ambiguous.available)

    def test_invalid_run_collection_is_rejected(self) -> None:
        auditor = ResearchEvidenceIntegrityAuditor(KnowledgeEngine())

        with self.assertRaisesRegex(ResearchError, "requires research runs"):
            auditor.audit(["invalid"])  # type: ignore[list-item]

    def _evidence(self, evidence_id: str, chunk: Chunk) -> ResearchEvidenceRecord:
        return ResearchEvidenceRecord.from_chunk(
            evidence_id,
            chunk,
            "User-selected note.",
            self.now,
        )

    def _run(
        self,
        evidence: tuple[ResearchEvidenceRecord, ...],
    ) -> ResearchRun:
        document_ids = tuple(
            dict.fromkeys(record.source_document_id for record in evidence)
        )
        return ResearchRun(
            run_id="run-1",
            question="Which evidence remains connected?",
            status=ResearchRunStatus.COLLECTING,
            sources=tuple(
                ResearchSourceRecord(
                    document_id=document_id,
                    url=f"https://example.com/{document_id}",
                    title=document_id,
                    content_type="text/plain",
                    fetched_at=self.now,
                    added_at=self.now,
                )
                for document_id in document_ids
            ),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
            evidence=evidence,
        )


if __name__ == "__main__":
    unittest.main()
