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
from research.ClaimCreationStepOperation import ClaimCreationStepOperation
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchClaimAuthorization import ResearchClaimAuthorization
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource

TEXT = "Saturn has a prominent ring system."


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


def step(authorization: ResearchClaimAuthorization | None) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Record the authored claim",
        capability=ResearchPlanStepCapability.CLAIM_CREATION,
        claim_authorization=authorization,
    )


class ClaimCreationStepOperationTests(unittest.TestCase):
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
        self.operation = ClaimCreationStepOperation(self.manager)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _with_evidence(self, run_id: str, url: str = "https://example.test/a") -> str:
        result = self.acceptance.accept(source(url), run_id)
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return updated.evidence[-1].evidence_id

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "claim_creation")

    def test_repeating_the_exact_first_claim_records_nothing_new(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)
        context = ResearchPlanExecutionContext(research_run_id=run_id)
        authorization = ResearchClaimAuthorization(
            evidence_ids=(evidence_id,),
            text=TEXT,
            epistemic_state=ResearchEpistemicState.HYPOTHESIS,
        )
        self.operation.run(step(authorization), context)
        first = self.manager.get(run_id)

        with self.assertRaisesRegex(
            ResearchError, f"already recorded as {first.claims[0].claim_id}"
        ):
            self.operation.run(step(authorization), context)
        self.assertEqual(self.manager.get(run_id), first)

        for different in (
            ResearchClaimAuthorization(
                evidence_ids=(evidence_id,),
                text=TEXT,
                epistemic_state=ResearchEpistemicState.LIKELY,
            ),
            ResearchClaimAuthorization(
                evidence_ids=(evidence_id,),
                text="A different claim.",
                epistemic_state=ResearchEpistemicState.HYPOTHESIS,
            ),
        ):
            with self.subTest(different=different):
                self.operation.run(step(different), context)
        self.assertEqual(len(self.manager.get(run_id).claims), 3)

    def test_replayed_superseding_claim_is_still_refused_by_the_manager(
        self,
    ) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)
        context = ResearchPlanExecutionContext(research_run_id=run_id)
        self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                    epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                )
            ),
            context,
        )
        correction = step(
            ResearchClaimAuthorization(
                evidence_ids=(evidence_id,),
                text="Corrected claim.",
                epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                supersedes_claim_id=self.manager.get(run_id).claims[0].claim_id,
            )
        )
        self.operation.run(correction, context)
        recorded = self.manager.get(run_id)

        with self.assertRaisesRegex(ResearchError, "already been superseded"):
            self.operation.run(correction, context)
        self.assertEqual(self.manager.get(run_id), recorded)

    def test_records_an_authored_claim_in_its_declared_state(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                    epistemic_state=ResearchEpistemicState.STRONG_EVIDENCE,
                    confidence=ResearchClaimConfidence.MEDIUM,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        claims = self.manager.get(run_id).claims
        self.assertEqual(len(claims), 1)
        self.assertIs(
            claims[0].epistemic_state,
            ResearchEpistemicState.STRONG_EVIDENCE,
        )
        self.assertIs(claims[0].confidence, ResearchClaimConfidence.MEDIUM)
        self.assertEqual(claims[0].evidence_ids, (evidence_id,))
        self.assertIn("authored state 'strong_evidence'", result.detail)
        self.assertIn("promotes nothing", result.detail)

    def test_completion_never_promotes_a_hypothesis(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                    epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        recorded = self.manager.get(run_id).claims[0]
        self.assertTrue(result.succeeded)
        self.assertIs(recorded.epistemic_state, ResearchEpistemicState.HYPOTHESIS)
        self.assertIs(recorded.confidence, ResearchClaimConfidence.UNASSESSED)
        self.assertNotIn("fact", result.detail)

    def test_every_declared_state_is_recorded_verbatim(self) -> None:
        for state in ResearchEpistemicState:
            with self.subTest(state=state):
                run_id = self._run_id()
                evidence_id = self._with_evidence(
                    run_id,
                    url=f"https://example.test/{state.value}",
                )

                self.operation.run(
                    step(
                        ResearchClaimAuthorization(
                            evidence_ids=(evidence_id,),
                            text=TEXT,
                            epistemic_state=state,
                        )
                    ),
                    ResearchPlanExecutionContext(research_run_id=run_id),
                )

                self.assertIs(
                    self.manager.get(run_id).claims[0].epistemic_state,
                    state,
                )

    def test_claim_requires_evidence_even_for_speculation(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchClaimAuthorization(
                evidence_ids=(),
                text=TEXT,
                epistemic_state=ResearchEpistemicState.SPECULATION,
            )

    def test_foreign_evidence_reference_is_rejected_without_mutation(self) -> None:
        run_id = self._run_id()
        other_run = self._run_id()
        foreign_evidence = self._with_evidence(other_run)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(
                    ResearchClaimAuthorization(
                        evidence_ids=(foreign_evidence,),
                        text=TEXT,
                        epistemic_state=ResearchEpistemicState.LIKELY,
                    )
                ),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).claims, ())

    def test_stale_evidence_reference_is_rejected(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(
                    ResearchClaimAuthorization(
                        evidence_ids=("evidence-that-never-existed",),
                        text=TEXT,
                        epistemic_state=ResearchEpistemicState.LIKELY,
                    )
                ),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).claims, ())

    def test_supersession_history_is_preserved(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)
        self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text="Initial authored claim.",
                    epistemic_state=ResearchEpistemicState.HYPOTHESIS,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )
        first_id = self.manager.get(run_id).claims[0].claim_id

        second = self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text="Revised authored claim.",
                    epistemic_state=ResearchEpistemicState.LIKELY,
                    supersedes_claim_id=first_id,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        claims = self.manager.get(run_id).claims
        self.assertEqual(len(claims), 2)
        self.assertIsNone(claims[0].supersedes_claim_id)
        self.assertEqual(claims[1].supersedes_claim_id, first_id)
        self.assertIs(claims[0].epistemic_state, ResearchEpistemicState.HYPOTHESIS)
        self.assertIn(f"superseding {first_id}", second.detail)

    def test_contradiction_state_is_untouched(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)

        self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text=TEXT,
                    epistemic_state=ResearchEpistemicState.LIKELY,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertEqual(self.manager.get(run_id).claim_contradictions, ())

    def test_missing_authorization_records_nothing(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(None),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).claims, ())

    def test_cancellation_prevents_the_claim_write(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(
                    ResearchClaimAuthorization(
                        evidence_ids=(evidence_id,),
                        text=TEXT,
                        epistemic_state=ResearchEpistemicState.LIKELY,
                    )
                ),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(self.manager.get(run_id).claims, ())

    def test_closed_and_unknown_runs_record_nothing(self) -> None:
        closed = self._run_id()
        evidence_id = self._with_evidence(closed)
        authorization = ResearchClaimAuthorization(
            evidence_ids=(evidence_id,),
            text=TEXT,
            epistemic_state=ResearchEpistemicState.LIKELY,
        )
        self.manager.transition_status(closed, ResearchRunStatus.CANCELLED)

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

        self.assertEqual(self.manager.get(closed).claims, ())

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchClaimAuthorization(
                    evidence_ids=(evidence_id,),
                    text="c" * 2_000,
                    epistemic_state=ResearchEpistemicState.LIKELY,
                )
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)


class ResearchClaimAuthorizationTests(unittest.TestCase):
    def test_accepts_exact_enum_values_as_text(self) -> None:
        authorization = ResearchClaimAuthorization(
            evidence_ids=("  e-1  ",),
            text="  Authored  ",
            epistemic_state="likely",  # type: ignore[arg-type]
            confidence="high",  # type: ignore[arg-type]
            supersedes_claim_id="  c-1  ",
        )

        self.assertEqual(authorization.evidence_ids, ("e-1",))
        self.assertEqual(authorization.text, "Authored")
        self.assertIs(authorization.epistemic_state, ResearchEpistemicState.LIKELY)
        self.assertIs(authorization.confidence, ResearchClaimConfidence.HIGH)
        self.assertEqual(authorization.supersedes_claim_id, "c-1")

    def test_rejects_invalid_values(self) -> None:
        valid = {
            "evidence_ids": ("e",),
            "text": "t",
            "epistemic_state": ResearchEpistemicState.LIKELY,
        }
        for override in (
            {"evidence_ids": ()},
            {"evidence_ids": ["e"]},
            {"evidence_ids": ("  ",)},
            {"evidence_ids": tuple(f"e{index}" for index in range(51))},
            {"text": "  "},
            {"text": "t" * 2_001},
            {"epistemic_state": "extremely_true"},
            {"epistemic_state": 5},
            {"confidence": "absolute"},
            {"supersedes_claim_id": "  "},
        ):
            with self.subTest(override=override):
                with self.assertRaises(ResearchError):
                    ResearchClaimAuthorization(**{**valid, **override})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
