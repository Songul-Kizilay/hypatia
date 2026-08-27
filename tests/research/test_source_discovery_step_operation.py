from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceDiscoveryStepOperation import SourceDiscoveryStepOperation

TRUST_BOUNDARY = "not accepted sources, not evidence, not trusted"


def candidate(slug: str) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        url=f"https://example.test/{slug}",
        title=f"Candidate {slug}",
        snippet="A short bounded snippet.",
    )


class RecordingProvider:
    """Return caller-supplied candidates and record every query."""

    def __init__(self, candidates: object = None, error: Exception | None = None):
        self.candidates = [] if candidates is None else candidates
        self.error = error
        self.queries: list[tuple[str, int]] = []

    @property
    def provider_name(self) -> str:
        return "recording_provider"

    def discover(self, query: str, *, limit: int) -> list[ResearchSourceCandidate]:
        self.queries.append((query, limit))
        if self.error is not None:
            raise self.error
        return self.candidates  # type: ignore[return-value]


class SourceDiscoveryStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.step = ResearchPlanStep(step_id="step-1", instruction="Find sources")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _operation(self, provider: RecordingProvider, **kwargs: object):  # type: ignore[no-untyped-def]
        return SourceDiscoveryStepOperation(provider, self.manager, **kwargs)  # type: ignore[arg-type]

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(
            self._operation(RecordingProvider()).operation_name,
            "source_discovery",
        )

    def test_discovery_records_unaccepted_candidates(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider([candidate("a"), candidate("b")])

        result = self._operation(provider).run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("returned 2 candidate(s)", result.detail)
        self.assertIn("recording_provider", result.detail)
        self.assertIn(TRUST_BOUNDARY, result.detail)
        run = self.manager.get(run_id)
        self.assertEqual(len(run.discoveries), 1)
        self.assertEqual(run.sources, ())
        self.assertEqual(run.evidence, ())
        self.assertEqual(run.claims, ())

    def test_zero_candidates_is_a_performed_discovery(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider([])

        result = self._operation(provider).run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("returned 0 candidate(s)", result.detail)
        self.assertIn("No candidates matched this question", result.detail)
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_query_uses_the_run_question_with_a_bounded_limit(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider([])

        self._operation(provider).run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertEqual(
            provider.queries,
            [("What evidence supports the claim?", 5)],
        )

    def test_provider_is_queried_exactly_once_without_retry(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider(error=ResearchError("provider unavailable"))

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(len(provider.queries), 1)

    def test_provider_failure_records_an_audit_failure(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider(error=ResearchError("provider unavailable"))

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        run = self.manager.get(run_id)
        self.assertEqual(len(run.failures), 1)
        self.assertEqual(run.failures[0].stage, "source_discovery")
        self.assertEqual(run.failures[0].provider, "recording_provider")
        self.assertEqual(run.discoveries, ())

    def test_oversized_provider_result_is_rejected(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider([candidate(str(index)) for index in range(6)])

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).discoveries, ())

    def test_invalid_provider_result_type_is_rejected(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider(["not a candidate"])

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(self.manager.get(run_id).discoveries, ())

    def test_cancellation_before_the_query_prevents_provider_contact(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider([candidate("a")])
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(provider.queries, [])
        self.assertEqual(self.manager.get(run_id).discoveries, ())

    def test_cancellation_after_the_query_prevents_the_audit_write(self) -> None:
        run_id = self._run_id()
        signal = CancellationSignal()

        class CancellingProvider(RecordingProvider):
            def discover(self, query: str, *, limit: int):  # type: ignore[no-untyped-def]
                result = super().discover(query, limit=limit)
                signal.cancel()
                return result

        provider = CancellingProvider([candidate("a")])

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(len(provider.queries), 1)
        self.assertEqual(self.manager.get(run_id).discoveries, ())

    def test_closed_run_is_rejected_before_provider_contact(self) -> None:
        run_id = self._run_id()
        self.manager.transition_status(run_id, ResearchRunStatus.CANCELLED)
        provider = RecordingProvider([candidate("a")])

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(provider.queries, [])

    def test_unknown_run_and_missing_binding_fail_safely(self) -> None:
        provider = RecordingProvider([candidate("a")])

        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )
        with self.assertRaises(ResearchError):
            self._operation(provider).run(
                self.step,
                ResearchPlanExecutionContext(),
            )

        self.assertEqual(provider.queries, [])

    def test_candidate_limit_is_validated(self) -> None:
        for invalid in (0, -1, 11, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ResearchError):
                    SourceDiscoveryStepOperation(
                        RecordingProvider(),  # type: ignore[arg-type]
                        self.manager,
                        candidate_limit=invalid,  # type: ignore[arg-type]
                    )

    def test_detail_stays_bounded(self) -> None:
        run_id = self._run_id()
        provider = RecordingProvider([candidate(str(index)) for index in range(5)])

        result = self._operation(provider).run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)


if __name__ == "__main__":
    unittest.main()
