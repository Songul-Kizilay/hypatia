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
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAssessmentAuthorization import ResearchAssessmentAuthorization
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.SourceAssessmentStepOperation import SourceAssessmentStepOperation

TEXT = "The source states the ring system directly."


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
    authorization: ResearchAssessmentAuthorization | None,
) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Record the authored assessment",
        capability=ResearchPlanStepCapability.SOURCE_ASSESSMENT,
        assessment_authorization=authorization,
    )


class SourceAssessmentStepOperationTests(unittest.TestCase):
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
        self.operation = SourceAssessmentStepOperation(self.manager)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _accepted(self, run_id: str, url: str = "https://example.test/a") -> str:
        result = self.acceptance.accept(source(url), run_id)
        assert result.document_id is not None
        return result.document_id

    def _with_evidence(self, run_id: str) -> tuple[str, str]:
        document_id = self._accepted(run_id)
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return document_id, updated.evidence[-1].evidence_id

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "source_assessment")

    def test_records_an_authored_assessment_for_an_accepted_source(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                    information_trust=ResearchInformationTrust.HIGH,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        run = self.manager.get(run_id)
        self.assertEqual(len(run.assessments), 1)
        recorded = run.assessments[0]
        self.assertEqual(recorded.source_document_id, document_id)
        self.assertEqual(recorded.text, TEXT)
        self.assertIs(recorded.information_trust, ResearchInformationTrust.HIGH)
        self.assertIn("authored trust 'high'", result.detail)
        self.assertIn("not claim verification", result.detail)

    def test_repeating_the_exact_first_assessment_records_nothing_new(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)
        context = ResearchPlanExecutionContext(research_run_id=run_id)
        authorization = ResearchAssessmentAuthorization(
            document_id=document_id,
            evidence_ids=(evidence_id,),
            text=TEXT,
            information_trust=ResearchInformationTrust.MEDIUM,
        )
        self.operation.run(step(authorization), context)
        first = self.manager.get(run_id)

        with self.assertRaisesRegex(
            ResearchError, f"already recorded as {first.assessments[0].assessment_id}"
        ):
            self.operation.run(step(authorization), context)

        self.assertEqual(self.manager.get(run_id), first)

    def test_distinct_assessments_of_the_same_source_are_still_recorded(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)
        context = ResearchPlanExecutionContext(research_run_id=run_id)
        base = ResearchAssessmentAuthorization(
            document_id=document_id, evidence_ids=(evidence_id,), text=TEXT
        )
        self.operation.run(step(base), context)
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Manual judgement.",
            independence="independent",
        )

        for different in (
            ResearchAssessmentAuthorization(
                document_id=document_id,
                evidence_ids=(evidence_id,),
                text="A different reading.",
            ),
            ResearchAssessmentAuthorization(
                document_id=document_id,
                evidence_ids=(evidence_id,),
                text=TEXT,
                information_trust=ResearchInformationTrust.LOW,
            ),
            ResearchAssessmentAuthorization(
                document_id=document_id,
                evidence_ids=(evidence_id,),
                text="Manual judgement.",
            ),
        ):
            with self.subTest(text=different.text):
                self.operation.run(step(different), context)

        self.assertEqual(len(self.manager.get(run_id).assessments), 5)

    def test_replayed_superseding_assessment_is_still_refused_by_the_manager(
        self,
    ) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)
        context = ResearchPlanExecutionContext(research_run_id=run_id)
        self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id, evidence_ids=(evidence_id,), text=TEXT
                )
            ),
            context,
        )
        original = self.manager.get(run_id).assessments[0].assessment_id
        correction = step(
            ResearchAssessmentAuthorization(
                document_id=document_id,
                evidence_ids=(evidence_id,),
                text="Corrected.",
                supersedes_assessment_id=original,
            )
        )
        self.operation.run(correction, context)
        recorded = self.manager.get(run_id)

        with self.assertRaisesRegex(ResearchError, "already been superseded"):
            self.operation.run(correction, context)

        self.assertEqual(self.manager.get(run_id), recorded)

    def test_assessment_creates_no_evidence_or_claim(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)
        before = len(self.manager.get(run_id).evidence)

        self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        run = self.manager.get(run_id)
        self.assertEqual(len(run.evidence), before)
        self.assertEqual(run.claims, ())
        self.assertEqual(run.claim_contradictions, ())

    def test_trust_defaults_to_unassessed_and_is_never_derived(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        recorded = self.manager.get(run_id).assessments[0]
        self.assertIs(
            recorded.information_trust,
            ResearchInformationTrust.UNASSESSED,
        )
        self.assertIn("authored trust 'unassessed'", result.detail)

    def test_supersession_history_is_preserved(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)
        first = self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text="First authored assessment.",
                    information_trust=ResearchInformationTrust.LOW,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )
        first_id = self.manager.get(run_id).assessments[0].assessment_id

        second = self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text="Revised authored assessment.",
                    information_trust=ResearchInformationTrust.HIGH,
                    supersedes_assessment_id=first_id,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(first.succeeded)
        self.assertTrue(second.succeeded)
        assessments = self.manager.get(run_id).assessments
        self.assertEqual(len(assessments), 2)
        self.assertIsNone(assessments[0].supersedes_assessment_id)
        self.assertEqual(assessments[1].supersedes_assessment_id, first_id)
        self.assertIn(f"superseding {first_id}", second.detail)

    def test_unaccepted_source_cannot_be_assessed(self) -> None:
        accepting = self._run_id()
        other = self._run_id()
        document_id, evidence_id = self._with_evidence(accepting)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(
                    ResearchAssessmentAuthorization(
                        document_id=document_id,
                        evidence_ids=(evidence_id,),
                        text=TEXT,
                    )
                ),
                ResearchPlanExecutionContext(research_run_id=other),
            )

        self.assertEqual(self.manager.get(other).assessments, ())

    def test_foreign_evidence_reference_is_rejected(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(
                    ResearchAssessmentAuthorization(
                        document_id=document_id,
                        evidence_ids=("missing-evidence",),
                        text=TEXT,
                    )
                ),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).assessments, ())

    def test_missing_authorization_records_nothing(self) -> None:
        run_id = self._run_id()
        self._accepted(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(None),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).assessments, ())

    def test_cancellation_prevents_the_assessment_write(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(
                    ResearchAssessmentAuthorization(
                        document_id=document_id,
                        evidence_ids=(evidence_id,),
                        text=TEXT,
                    )
                ),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(self.manager.get(run_id).assessments, ())

    def test_closed_and_unknown_runs_record_nothing(self) -> None:
        closed = self._run_id()
        document_id, evidence_id = self._with_evidence(closed)
        self.manager.transition_status(closed, ResearchRunStatus.CANCELLED)
        authorization = ResearchAssessmentAuthorization(
            document_id=document_id,
            evidence_ids=(evidence_id,),
            text=TEXT,
        )

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(authorization),
                ResearchPlanExecutionContext(research_run_id=closed),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                step(authorization),
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(step(authorization), ResearchPlanExecutionContext())

        self.assertEqual(self.manager.get(closed).assessments, ())

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()
        document_id, evidence_id = self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchAssessmentAuthorization(
                    document_id=document_id,
                    evidence_ids=(evidence_id,),
                    text="t" * 2_000,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)


class ResearchAssessmentAuthorizationTests(unittest.TestCase):
    def test_normalizes_values(self) -> None:
        authorization = ResearchAssessmentAuthorization(
            document_id="  doc-1  ",
            evidence_ids=("  e-1  ",),
            text="  Authored  ",
            information_trust="high",  # type: ignore[arg-type]
            supersedes_assessment_id="  a-1  ",
        )

        self.assertEqual(authorization.document_id, "doc-1")
        self.assertEqual(authorization.evidence_ids, ("e-1",))
        self.assertEqual(authorization.text, "Authored")
        self.assertIs(
            authorization.information_trust,
            ResearchInformationTrust.HIGH,
        )
        self.assertEqual(authorization.supersedes_assessment_id, "a-1")

    def test_rejects_invalid_values(self) -> None:
        valid = {"document_id": "d", "evidence_ids": ("e",), "text": "t"}
        for override in (
            {"document_id": "  "},
            {"text": "  "},
            {"text": "t" * 2_001},
            {"evidence_ids": ()},
            {"evidence_ids": ["e"]},
            {"evidence_ids": ("  ",)},
            {"evidence_ids": tuple(f"e{index}" for index in range(21))},
            {"information_trust": "excellent"},
            {"supersedes_assessment_id": "  "},
            {"document_id": "d" * 201},
        ):
            with self.subTest(override=override):
                with self.assertRaises(ResearchError):
                    ResearchAssessmentAuthorization(**{**valid, **override})  # type: ignore[arg-type]

    def test_requires_evidence_grounding(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssessmentAuthorization(
                document_id="d",
                evidence_ids=(),
                text="An assessment with no evidence.",
            )


if __name__ == "__main__":
    unittest.main()
