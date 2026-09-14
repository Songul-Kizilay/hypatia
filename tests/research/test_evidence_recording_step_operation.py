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
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.EvidenceRecordingStepOperation import EvidenceRecordingStepOperation
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource

NOTE = "Supports the ring claim."


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


def source(url: str = "https://example.test/a") -> ResearchSource:
    return ResearchSource(
        url=url,
        title="A source",
        content="Saturn has a prominent ring system.",
        content_type="text/html",
        fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def step(
    document_id: str,
    chunk_index: int = 0,
    note: str = NOTE,
) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Record the authorized evidence",
        capability=ResearchPlanStepCapability.EVIDENCE_RECORDING,
        evidence_authorization=ResearchEvidenceAuthorization(
            document_id=document_id,
            chunk_index=chunk_index,
            note=note,
        ),
    )


class EvidenceRecordingStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            InMemoryContentStore(),  # type: ignore[arg-type]
        )
        self.operation = EvidenceRecordingStepOperation(
            self.knowledge_engine,
            self.manager,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _accepted(self, run_id: str, url: str = "https://example.test/a") -> str:
        result = self.acceptance.accept(source(url), run_id)
        assert result.document_id is not None
        return result.document_id

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "evidence_recording")

    def test_records_evidence_from_an_accepted_source_chunk(self) -> None:
        run_id = self._run_id()
        document_id = self._accepted(run_id)

        result = self.operation.run(
            step(document_id),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        run = self.manager.get(run_id)
        self.assertEqual(len(run.evidence), 1)
        recorded = run.evidence[0]
        self.assertEqual(recorded.source_document_id, document_id)
        self.assertEqual(recorded.chunk_index, 0)
        self.assertEqual(recorded.note, NOTE)
        self.assertIn("Recorded evidence", result.detail)
        self.assertIn("not a claim", result.detail)

    def test_provenance_is_computed_from_the_real_chunk(self) -> None:
        run_id = self._run_id()
        document_id = self._accepted(run_id)
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == document_id and candidate.index == 0
        )

        self.operation.run(
            step(document_id),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        recorded = self.manager.get(run_id).evidence[0]
        self.assertEqual(recorded.chunk_id, chunk.chunk_id)
        self.assertIn(recorded.excerpt, chunk.content)
        self.assertFalse(recorded.excerpt_truncated)

    def test_recording_creates_no_assessment_or_claim(self) -> None:
        run_id = self._run_id()
        document_id = self._accepted(run_id)

        self.operation.run(
            step(document_id),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        run = self.manager.get(run_id)
        self.assertEqual(run.assessments, ())
        self.assertEqual(run.claims, ())
        self.assertEqual(run.claim_contradictions, ())

    def test_unaccepted_source_cannot_produce_evidence(self) -> None:
        accepting_run = self._run_id()
        other_run = self._run_id()
        document_id = self._accepted(accepting_run)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(document_id),
                ResearchPlanExecutionContext(research_run_id=other_run),
            )

        self.assertEqual(self.manager.get(other_run).evidence, ())

    def test_unknown_chunk_is_refused_rather_than_guessed(self) -> None:
        run_id = self._run_id()
        document_id = self._accepted(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(document_id, chunk_index=99),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                step("missing-document"),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).evidence, ())

    def test_missing_authorization_records_nothing(self) -> None:
        run_id = self._run_id()
        self._accepted(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                ResearchPlanStep(
                    step_id="step-1",
                    instruction="Record evidence",
                    capability=ResearchPlanStepCapability.EVIDENCE_RECORDING,
                ),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).evidence, ())

    def test_cancellation_prevents_the_evidence_write(self) -> None:
        run_id = self._run_id()
        document_id = self._accepted(run_id)
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(document_id),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(self.manager.get(run_id).evidence, ())

    def test_closed_and_unknown_runs_record_nothing(self) -> None:
        closed = self._run_id()
        document_id = self._accepted(closed)
        self.manager.transition_status(closed, ResearchRunStatus.CANCELLED)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(document_id),
                ResearchPlanExecutionContext(research_run_id=closed),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                step(document_id),
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                step(document_id),
                ResearchPlanExecutionContext(),
            )

        self.assertEqual(self.manager.get(closed).evidence, ())

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()
        document_id = self._accepted(run_id)

        result = self.operation.run(
            step(document_id, note="n" * 1_000),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)


class ResearchEvidenceAuthorizationTests(unittest.TestCase):
    def test_normalizes_and_validates(self) -> None:
        authorization = ResearchEvidenceAuthorization(
            document_id="  doc-1  ",
            chunk_index=0,
            note="  A note  ",
        )

        self.assertEqual(authorization.document_id, "doc-1")
        self.assertEqual(authorization.note, "A note")

    def test_rejects_invalid_values(self) -> None:
        for kwargs in (
            {"document_id": "  ", "chunk_index": 0, "note": "n"},
            {"document_id": "d", "chunk_index": -1, "note": "n"},
            {"document_id": "d", "chunk_index": True, "note": "n"},
            {"document_id": "d", "chunk_index": "0", "note": "n"},
            {"document_id": "d", "chunk_index": 0, "note": "  "},
            {"document_id": "d", "chunk_index": 0, "note": "n" * 1_001},
            {"document_id": "d" * 201, "chunk_index": 0, "note": "n"},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResearchError):
                    ResearchEvidenceAuthorization(**kwargs)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
