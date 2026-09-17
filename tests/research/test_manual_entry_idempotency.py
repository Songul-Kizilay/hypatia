"""Re-confirming an identical manual entry never records it twice.

The run manager is the one write path for manual entry and plan steps, so the
refusal lives there: previews say the write is not allowed and name the
existing record, and recording refuses the exact repeat.  Corrections that
supersede a record, and any genuinely different entry, are still accepted.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource


def source(url: str) -> ResearchSource:
    return ResearchSource(
        url=url,
        title="A source",
        content="Saturn has a prominent ring system.",
        content_type="text/plain",
        fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


class ManualEntryIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.knowledge = KnowledgeEngine()
        self.runs = ResearchRunManager(
            JsonFileResearchRunStore(Path(directory.name) / "runs.json")
        )
        acceptance = ResearchSourceAcceptanceService(self.knowledge, self.runs)
        self.run_id = self.runs.create("What evidence supports the claim?").run_id
        self.documents = []
        self.evidence_ids = []
        for url in ("https://example.test/a", "https://example.test/b"):
            document_id = acceptance.accept(source(url), self.run_id).document_id
            chunk = next(
                c for c in self.knowledge.chunks() if c.document_id == document_id
            )
            run = self.runs.add_evidence(self.run_id, chunk, "Directly relevant.")
            self.documents.append(document_id)
            self.evidence_ids.append(run.evidence[-1].evidence_id)

    def test_repeated_manual_evidence_is_refused_naming_the_existing_record(self):
        chunk = next(
            c for c in self.knowledge.chunks() if c.document_id == self.documents[0]
        )
        before = self.runs.get(self.run_id)

        with self.assertRaisesRegex(
            ResearchError, f"already recorded as {self.evidence_ids[0]}"
        ):
            self.runs.add_evidence(self.run_id, chunk, " Directly relevant. ")

        self.assertEqual(self.runs.get(self.run_id), before)
        self.runs.add_evidence(self.run_id, chunk, "A different reading.")
        self.assertEqual(len(self.runs.get(self.run_id).evidence), 3)

    def test_repeated_assessment_preview_and_record_are_refused(self):
        values = (self.run_id, self.documents[0], [self.evidence_ids[0]], "Direct.")
        first = self.runs.record_source_assessment(*values, information_trust="high")
        existing = first.assessments[-1].assessment_id

        preview = self.runs.preview_source_assessment_write(
            *values, information_trust="high"
        )

        self.assertFalse(preview.allowed)
        self.assertIn(f"already recorded as {existing}", preview.reason)
        with self.assertRaisesRegex(ResearchError, existing):
            self.runs.record_source_assessment(*values, information_trust="high")
        # A different judgement and an explicit correction are still recorded.
        self.runs.record_source_assessment(*values, information_trust="low")
        correction = self.runs.preview_source_assessment_write(
            *values, supersedes_assessment_id=existing, information_trust="high"
        )
        self.assertTrue(correction.allowed)
        self.assertEqual(len(self.runs.get(self.run_id).assessments), 2)

    def test_repeated_claim_preview_and_record_are_refused(self):
        values = (self.run_id, [self.evidence_ids[0]], "Saturn has rings.", "likely")
        existing = self.runs.record_claim(*values).claims[-1].claim_id

        preview = self.runs.preview_claim_write(*values)

        self.assertFalse(preview.allowed)
        self.assertIn(f"already recorded as {existing}", preview.reason)
        with self.assertRaisesRegex(ResearchError, existing):
            self.runs.record_claim(*values)
        self.assertTrue(
            self.runs.preview_claim_write(*values, supersedes_claim_id=existing).allowed
        )
        self.runs.record_claim(
            self.run_id, [self.evidence_ids[0]], "Saturn has rings.", "hypothesis"
        )
        self.assertEqual(len(self.runs.get(self.run_id).claims), 2)

    def test_repeated_comparison_note_preview_and_record_are_refused(self):
        assessments = [
            self.runs.record_source_assessment(
                self.run_id, document, [evidence], "Grounded."
            )
            .assessments[-1]
            .assessment_id
            for document, evidence in zip(
                self.documents, self.evidence_ids, strict=True
            )
        ]
        values = (
            self.run_id,
            self.documents,
            self.evidence_ids,
            assessments,
            "Both describe rings.",
        )
        existing = self.runs.record_source_comparison_note(*values)
        note_id = existing.comparison_notes[-1].note_id

        preview = self.runs.preview_source_comparison_note_write(*values)

        self.assertFalse(preview.allowed)
        self.assertIn(f"already recorded as {note_id}", preview.reason)
        with self.assertRaisesRegex(ResearchError, note_id):
            self.runs.record_source_comparison_note(*values)
        self.assertEqual(len(self.runs.get(self.run_id).comparison_notes), 1)


if __name__ == "__main__":
    unittest.main()
