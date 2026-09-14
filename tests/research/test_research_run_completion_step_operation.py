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
from research.ResearchCompletionAuthorization import ResearchCompletionAuthorization
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunCompletionStepOperation import (
    ResearchRunCompletionStepOperation,
)
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


def step(
    authorization: ResearchCompletionAuthorization | None,
) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Close the research run",
        capability=ResearchPlanStepCapability.RESEARCH_RUN_COMPLETION,
        completion_authorization=authorization,
    )


COMPLETE = ResearchCompletionAuthorization(target_status=ResearchRunStatus.COMPLETED)


class ResearchRunCompletionStepOperationTests(unittest.TestCase):
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
        self.operation = ResearchRunCompletionStepOperation(self.manager)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _with_evidence(self, run_id: str, slug: str = "a") -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=f"https://example.test/{slug}",
                title="A source",
                content="Saturn has a prominent ring system.",
                content_type="text/html",
                fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
            run_id,
        )
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return updated.evidence[-1].evidence_id

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "research_run_completion")

    def test_completion_requires_the_existing_domain_conditions(self) -> None:
        empty_run = self._run_id()

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=empty_run),
        )

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertIn("requires at least one accepted source", result.detail)
        self.assertIn("The run remains open", result.detail)
        self.assertIs(self.manager.get(empty_run).status, ResearchRunStatus.COLLECTING)

    def test_accepted_source_without_evidence_cannot_complete(self) -> None:
        run_id = self._run_id()
        self.acceptance.accept(
            ResearchSource(
                url="https://example.test/no-evidence",
                title="A source",
                content="Saturn has rings.",
                content_type="text/html",
                fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
            run_id,
        )

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertFalse(result.succeeded)
        self.assertIn("requires at least one evidence record", result.detail)
        self.assertIs(self.manager.get(run_id).status, ResearchRunStatus.COLLECTING)

    def test_completion_succeeds_when_the_domain_allows_it(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        self.assertIs(self.manager.get(run_id).status, ResearchRunStatus.COMPLETED)
        self.assertIn("closed as 'completed'", result.detail)
        self.assertIn("resolves nothing", result.detail)

    def test_unresolved_uncertainty_is_reported_and_preserved(self) -> None:
        run_id = self._run_id()
        evidence_id = self._with_evidence(run_id)
        for text, state in (
            ("A cautious hypothesis.", ResearchEpistemicState.HYPOTHESIS),
            ("An unknown outcome.", ResearchEpistemicState.UNKNOWN),
            ("A settled point.", ResearchEpistemicState.STRONG_EVIDENCE),
        ):
            self.manager.record_claim(run_id, [evidence_id], text, state)
        self.manager.record_failure(run_id, "source_discovery", "A recorded failure.")

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.succeeded)
        self.assertIn("2 unresolved claim(s)", result.detail)
        self.assertIn("1 failure(s)", result.detail)
        closed = self.manager.get(run_id)
        self.assertEqual(len(closed.claims), 3)
        self.assertEqual(len(closed.failures), 1)
        states = {claim.epistemic_state for claim in closed.claims}
        self.assertIn(ResearchEpistemicState.HYPOTHESIS, states)
        self.assertIn(ResearchEpistemicState.UNKNOWN, states)

    def test_contradictions_survive_completion(self) -> None:
        run_id = self._run_id()
        first_evidence = self._with_evidence(run_id, "a")
        second_evidence = self._with_evidence(run_id, "b")
        first = self.manager.record_claim(
            run_id,
            [first_evidence],
            "Saturn has rings.",
            ResearchEpistemicState.LIKELY,
        ).claims[-1]
        second = self.manager.record_claim(
            run_id,
            [second_evidence],
            "Saturn has no rings.",
            ResearchEpistemicState.LIKELY,
        ).claims[-1]
        self.manager.record_claim_contradiction(
            run_id,
            [first.claim_id, second.claim_id],
            "These cannot both hold.",
        )

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.succeeded)
        self.assertIn("1 contradiction(s)", result.detail)
        closed = self.manager.get(run_id)
        self.assertEqual(len(closed.claim_contradictions), 1)
        self.assertIs(closed.status, ResearchRunStatus.COMPLETED)

    def test_failed_status_requires_a_failure_record(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)

        result = self.operation.run(
            step(
                ResearchCompletionAuthorization(target_status=ResearchRunStatus.FAILED)
            ),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertFalse(result.succeeded)
        self.assertIn("requires at least one failure record", result.detail)
        self.assertIs(self.manager.get(run_id).status, ResearchRunStatus.COLLECTING)

    def test_already_closed_run_is_not_closed_again(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)
        self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertFalse(result.succeeded)
        self.assertIn("cannot change status", result.detail)

    def test_missing_authorization_and_cancellation_close_nothing(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self.operation.run(
                step(None),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(
                step(COMPLETE),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertIs(self.manager.get(run_id).status, ResearchRunStatus.COLLECTING)

    def test_unknown_and_unbound_runs_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(
                step(COMPLETE),
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )
        with self.assertRaises(ResearchError):
            self.operation.run(step(COMPLETE), ResearchPlanExecutionContext())

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()
        self._with_evidence(run_id)

        result = self.operation.run(
            step(COMPLETE),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)


class ResearchCompletionAuthorizationTests(unittest.TestCase):
    def test_accepts_terminal_statuses_including_text(self) -> None:
        for value in ("completed", "failed", "cancelled"):
            with self.subTest(value=value):
                authorization = ResearchCompletionAuthorization(
                    target_status=value  # type: ignore[arg-type]
                )
                self.assertTrue(authorization.target_status.terminal)

    def test_rejects_non_terminal_and_invalid_statuses(self) -> None:
        for value in ("collecting", "finished", 5, None):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    ResearchCompletionAuthorization(
                        target_status=value  # type: ignore[arg-type]
                    )


if __name__ == "__main__":
    unittest.main()
