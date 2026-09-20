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
from research.ClaimContradictionStepOperation import ClaimContradictionStepOperation
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchComparisonAuthorization import ResearchComparisonAuthorization
from research.ResearchContradictionAuthorization import (
    ResearchContradictionAuthorization,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.SourceComparisonStepOperation import SourceComparisonStepOperation


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


def source(url: str) -> ResearchSource:
    return ResearchSource(
        url=url,
        title=f"Source {url}",
        content="Saturn has a prominent ring system.",
        content_type="text/html",
        fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


class ResearchFixture(unittest.TestCase):
    """Shared setup building accepted sources, evidence, and claims."""

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

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _accepted_with_evidence(self, run_id: str, slug: str) -> tuple[str, str]:
        result = self.acceptance.accept(
            source(f"https://example.test/{slug}"),
            run_id,
        )
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return result.document_id, updated.evidence[-1].evidence_id

    def _claim(self, run_id: str, evidence_id: str, text: str) -> str:
        updated = self.manager.record_claim(
            run_id,
            [evidence_id],
            text,
            ResearchEpistemicState.LIKELY,
        )
        return updated.claims[-1].claim_id

    def _assessment(self, run_id: str, document_id: str, evidence_id: str) -> str:
        updated = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Authored assessment of the source.",
        )
        return updated.assessments[-1].assessment_id


def contradiction_step(
    authorization: ResearchContradictionAuthorization | None,
) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Record the confirmed contradiction",
        capability=ResearchPlanStepCapability.CLAIM_CONTRADICTION,
        contradiction_authorization=authorization,
    )


def comparison_step(
    authorization: ResearchComparisonAuthorization | None,
) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Record the authored comparison",
        capability=ResearchPlanStepCapability.SOURCE_COMPARISON,
        comparison_authorization=authorization,
    )


class ClaimContradictionStepOperationTests(ResearchFixture):
    def setUp(self) -> None:
        super().setUp()
        self.operation = ClaimContradictionStepOperation(self.manager)

    def _two_claims(self, run_id: str) -> tuple[str, str]:
        _, first_evidence = self._accepted_with_evidence(run_id, f"{run_id}-a")
        _, second_evidence = self._accepted_with_evidence(run_id, f"{run_id}-b")
        return (
            self._claim(run_id, first_evidence, "Saturn has rings."),
            self._claim(run_id, second_evidence, "Saturn has no rings."),
        )

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "claim_contradiction")

    def test_records_a_confirmed_contradiction(self) -> None:
        run_id = self._run_id()
        first, second = self._two_claims(run_id)

        result = self.operation.run(
            contradiction_step(
                ResearchContradictionAuthorization(
                    claim_ids=(first, second),
                    note="These claims cannot both hold.",
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        run = self.manager.get(run_id)
        self.assertEqual(len(run.claim_contradictions), 1)
        self.assertEqual(run.claim_contradictions[0].claim_ids, (first, second))
        self.assertIn("Recorded contradiction", result.detail)
        self.assertIn("neither was decided true", result.detail)

    def test_recording_never_rewrites_either_claim(self) -> None:
        run_id = self._run_id()
        first, second = self._two_claims(run_id)
        before = self.manager.get(run_id).claims

        self.operation.run(
            contradiction_step(
                ResearchContradictionAuthorization(
                    claim_ids=(first, second),
                    note="These claims cannot both hold.",
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        after = self.manager.get(run_id).claims
        self.assertEqual(before, after)
        for claim in after:
            self.assertIs(claim.epistemic_state, ResearchEpistemicState.LIKELY)

    def test_a_proposal_alone_persists_nothing(self) -> None:
        run_id = self._run_id()
        first, second = self._two_claims(run_id)

        preview = self.manager.preview_claim_contradiction_write(
            run_id,
            [first, second],
            "A proposed contradiction awaiting review.",
        )

        self.assertIsNotNone(preview)
        self.assertEqual(self.manager.get(run_id).claim_contradictions, ())

    def test_duplicate_relationship_is_rejected(self) -> None:
        run_id = self._run_id()
        first, second = self._two_claims(run_id)
        authorization = ResearchContradictionAuthorization(
            claim_ids=(first, second),
            note="These claims cannot both hold.",
        )
        self.operation.run(
            contradiction_step(authorization),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        with self.assertRaises(ResearchError):
            self.operation.run(
                contradiction_step(authorization),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(len(self.manager.get(run_id).claim_contradictions), 1)

    def test_foreign_and_stale_claims_are_rejected_without_mutation(self) -> None:
        run_id = self._run_id()
        other_run = self._run_id()
        first, _ = self._two_claims(run_id)
        foreign_first, _ = self._two_claims(other_run)

        for claim_ids in (
            (first, foreign_first),
            (first, "claim-that-never-existed"),
        ):
            with self.subTest(claim_ids=claim_ids):
                with self.assertRaises(ResearchError):
                    self.operation.run(
                        contradiction_step(
                            ResearchContradictionAuthorization(
                                claim_ids=claim_ids,
                                note="Invalid reference.",
                            )
                        ),
                        ResearchPlanExecutionContext(research_run_id=run_id),
                    )

        self.assertEqual(self.manager.get(run_id).claim_contradictions, ())

    def test_missing_authorization_and_cancellation_record_nothing(self) -> None:
        run_id = self._run_id()
        first, second = self._two_claims(run_id)
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self.operation.run(
                contradiction_step(None),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                contradiction_step(
                    ResearchContradictionAuthorization(
                        claim_ids=(first, second),
                        note="Cancelled.",
                    )
                ),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(self.manager.get(run_id).claim_contradictions, ())

    def test_closed_and_unknown_runs_record_nothing(self) -> None:
        closed = self._run_id()
        first, second = self._two_claims(closed)
        authorization = ResearchContradictionAuthorization(
            claim_ids=(first, second),
            note="Closed run.",
        )
        self.manager.transition_status(closed, ResearchRunStatus.CANCELLED)

        for context in (
            ResearchPlanExecutionContext(research_run_id=closed),
            ResearchPlanExecutionContext(research_run_id="missing-run"),
            ResearchPlanExecutionContext(),
        ):
            with self.subTest(context=context):
                with self.assertRaises(ResearchError):
                    self.operation.run(contradiction_step(authorization), context)

        self.assertEqual(self.manager.get(closed).claim_contradictions, ())

    def test_authorization_validation(self) -> None:
        for kwargs in (
            {"claim_ids": ("a",), "note": "n"},
            {"claim_ids": ("a", "b", "c"), "note": "n"},
            {"claim_ids": ("a", "a"), "note": "n"},
            {"claim_ids": ("a", "  "), "note": "n"},
            {"claim_ids": ["a", "b"], "note": "n"},
            {"claim_ids": ("a", "b"), "note": "  "},
            {"claim_ids": ("a", "b"), "note": "n" * 1_001},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResearchError):
                    ResearchContradictionAuthorization(**kwargs)  # type: ignore[arg-type]


class SourceComparisonStepOperationTests(ResearchFixture):
    def setUp(self) -> None:
        super().setUp()
        self.operation = SourceComparisonStepOperation(self.manager)

    def _two_assessed_sources(
        self,
        run_id: str,
    ) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str]]:
        first_document, first_evidence = self._accepted_with_evidence(
            run_id, f"{run_id}-a"
        )
        second_document, second_evidence = self._accepted_with_evidence(
            run_id, f"{run_id}-b"
        )
        first_assessment = self._assessment(run_id, first_document, first_evidence)
        second_assessment = self._assessment(run_id, second_document, second_evidence)
        return (
            (first_document, second_document),
            (first_evidence, second_evidence),
            (first_assessment, second_assessment),
        )

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "source_comparison")

    def test_records_an_authored_comparison(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)

        result = self.operation.run(
            comparison_step(
                ResearchComparisonAuthorization(
                    document_ids=documents,
                    evidence_ids=evidence,
                    assessment_ids=assessments,
                    text="Both sources describe the ring system similarly.",
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        notes = self.manager.get(run_id).comparison_notes
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].source_document_ids, documents)
        self.assertIn("no winner selected", result.detail)
        self.assertIn("no trust promoted", result.detail)

    def test_repeating_the_exact_comparison_note_records_nothing_new(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)
        context = ResearchPlanExecutionContext(research_run_id=run_id)
        authorization = ResearchComparisonAuthorization(
            document_ids=documents,
            evidence_ids=evidence,
            assessment_ids=assessments,
            text="Both sources describe the ring system similarly.",
        )
        self.operation.run(comparison_step(authorization), context)
        first = self.manager.get(run_id)

        with self.assertRaisesRegex(
            ResearchError, f"already recorded as {first.comparison_notes[0].note_id}"
        ):
            self.operation.run(comparison_step(authorization), context)
        self.assertEqual(self.manager.get(run_id), first)

        self.operation.run(
            comparison_step(
                ResearchComparisonAuthorization(
                    document_ids=documents,
                    evidence_ids=evidence,
                    assessment_ids=assessments,
                    text="A different comparison of the same sources.",
                )
            ),
            context,
        )
        self.assertEqual(len(self.manager.get(run_id).comparison_notes), 2)

    def test_comparison_promotes_no_trust_and_verifies_no_claim(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)
        before = self.manager.get(run_id)

        self.operation.run(
            comparison_step(
                ResearchComparisonAuthorization(
                    document_ids=documents,
                    evidence_ids=evidence,
                    assessment_ids=assessments,
                    text="Both sources agree.",
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        after = self.manager.get(run_id)
        self.assertEqual(before.assessments, after.assessments)
        self.assertEqual(before.claims, after.claims)
        self.assertEqual(after.claim_contradictions, ())

    def test_source_count_bounds_are_preserved(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                comparison_step(
                    ResearchComparisonAuthorization(
                        document_ids=(documents[0],),
                        evidence_ids=evidence,
                        assessment_ids=assessments,
                        text="Only one source.",
                    )
                ),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).comparison_notes, ())

    def test_foreign_references_are_rejected_without_mutation(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                comparison_step(
                    ResearchComparisonAuthorization(
                        document_ids=(documents[0], "document-that-never-existed"),
                        evidence_ids=evidence,
                        assessment_ids=assessments,
                        text="Invalid source reference.",
                    )
                ),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).comparison_notes, ())

    def test_missing_authorization_and_cancellation_record_nothing(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self.operation.run(
                comparison_step(None),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                comparison_step(
                    ResearchComparisonAuthorization(
                        document_ids=documents,
                        evidence_ids=evidence,
                        assessment_ids=assessments,
                        text="Cancelled.",
                    )
                ),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(self.manager.get(run_id).comparison_notes, ())

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()
        documents, evidence, assessments = self._two_assessed_sources(run_id)

        result = self.operation.run(
            comparison_step(
                ResearchComparisonAuthorization(
                    document_ids=documents,
                    evidence_ids=evidence,
                    assessment_ids=assessments,
                    text="c" * 2_000,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)

    def test_authorization_validation(self) -> None:
        valid = {
            "document_ids": ("d1", "d2"),
            "evidence_ids": ("e1",),
            "assessment_ids": ("a1",),
            "text": "t",
        }
        for override in (
            {"document_ids": ()},
            {"evidence_ids": ()},
            {"assessment_ids": ()},
            {"document_ids": ["d1", "d2"]},
            {"document_ids": ("d1", "  ")},
            {"text": "  "},
            {"text": "t" * 2_001},
            {"evidence_ids": tuple(f"e{index}" for index in range(51))},
        ):
            with self.subTest(override=override):
                with self.assertRaises(ResearchError):
                    ResearchComparisonAuthorization(**{**valid, **override})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
