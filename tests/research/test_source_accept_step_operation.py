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
from core.Exceptions import KnowledgeError, ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceAcceptanceResult import ResearchSourceAcceptanceResult
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceAcceptStepOperation import SourceAcceptStepOperation

AUTHORIZED_URL = "https://example.test/authorized"


class RecordingFetcher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return ResearchSource(
            url=url,
            title="Authorized source",
            content="Authorized source body text.",
            content_type="text/html",
            fetched_at=datetime(2026, 8, 1, tzinfo=UTC),
        )


class RejectingAcceptanceService:
    """Report a genuinely attempted transaction that accepted nothing."""

    def __init__(self) -> None:
        self.calls = 0

    def accept(
        self,
        source: ResearchSource,
        run_id: str = "",
        *,
        requested_url: str = "",
    ) -> ResearchSourceAcceptanceResult:
        del source, run_id, requested_url
        self.calls += 1
        return ResearchSourceAcceptanceResult(
            accepted=False,
            transaction_attempted=True,
            failure_reason="Research source audit could not be saved.",
        )


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


def step(url: str = AUTHORIZED_URL) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction="Accept the authorized source",
        capability=ResearchPlanStepCapability.SOURCE_ACCEPT,
        authorized_source_url=url,
    )


class SourceAcceptStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.content_store = InMemoryContentStore()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            self.content_store,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _operation(
        self,
        fetcher: RecordingFetcher,
        acceptance: object = None,
    ) -> SourceAcceptStepOperation:
        return SourceAcceptStepOperation(
            fetcher,  # type: ignore[arg-type]
            acceptance or self.acceptance,  # type: ignore[arg-type]
            self.manager,
        )

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(
            self._operation(RecordingFetcher()).operation_name,
            "source_accept",
        )

    def test_successful_acceptance_records_the_canonical_source(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher()

        result = self._operation(fetcher).run(
            step(),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertTrue(result.succeeded)
        self.assertEqual(fetcher.urls, [AUTHORIZED_URL])
        self.assertIn("Accepted", result.detail)
        self.assertIn("not evidence", result.detail)
        run = self.manager.get(run_id)
        self.assertEqual(len(run.sources), 1)
        self.assertEqual(run.evidence, ())
        self.assertEqual(run.claims, ())
        self.assertEqual(run.assessments, ())

    def test_attempted_transaction_is_not_reported_as_acceptance(self) -> None:
        run_id = self._run_id()
        rejecting = RejectingAcceptanceService()

        result = self._operation(RecordingFetcher(), rejecting).run(
            step(),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(rejecting.calls, 1)
        self.assertIn("did not accept the source", result.detail)
        self.assertIn("No source was added to the run", result.detail)
        self.assertNotIn("Accepted https", result.detail)
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_missing_authorization_prevents_fetch_and_acceptance(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher()

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(url=""),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_discovery_alone_never_authorizes_acceptance(self) -> None:
        run_id = self._run_id()
        self.manager.add_discovery(
            run_id,
            "What evidence supports the claim?",
            "stub_provider",
            [
                ResearchSourceCandidate(
                    url="https://example.test/discovered",
                    title="Discovered",
                    snippet="A snippet.",
                )
            ],
        )
        fetcher = RecordingFetcher()

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(url=""),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_cancellation_before_fetch_prevents_all_work(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher()
        signal = CancellationSignal()
        signal.cancel()

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(fetcher.urls, [])
        self.assertEqual(self.manager.get(run_id).sources, ())
        self.assertEqual(self.knowledge_engine.document_count(), 0)

    def test_cancellation_after_fetch_prevents_acceptance_mutation(self) -> None:
        run_id = self._run_id()
        signal = CancellationSignal()

        class CancellingFetcher(RecordingFetcher):
            def fetch(self, url: str) -> ResearchSource:
                result = super().fetch(url)
                signal.cancel()
                return result

        fetcher = CancellingFetcher()

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(fetcher.urls, [AUTHORIZED_URL])
        self.assertEqual(self.manager.get(run_id).sources, ())
        self.assertEqual(self.knowledge_engine.document_count(), 0)
        self.assertEqual(self.content_store.records, [])

    def test_fetch_failure_is_audited_and_raised(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher(
            error=ResearchError("Research source URL must be public HTTPS.")
        )

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(url="http://127.0.0.1/private"),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        run = self.manager.get(run_id)
        self.assertEqual(len(run.failures), 1)
        self.assertEqual(run.failures[0].stage, "source_load")
        self.assertEqual(run.sources, ())

    def test_indexing_failure_is_audited_and_normalized(self) -> None:
        run_id = self._run_id()

        class FailingAcceptance:
            def accept(  # type: ignore[no-untyped-def]
                self,
                source: ResearchSource,
                run_id: str = "",
                *,
                requested_url: str = "",
            ):
                raise KnowledgeError("Indexing unavailable.")

        with self.assertRaises(ResearchError):
            self._operation(RecordingFetcher(), FailingAcceptance()).run(
                step(),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        run = self.manager.get(run_id)
        self.assertEqual(len(run.failures), 1)
        self.assertEqual(run.sources, ())

    def test_closed_and_unknown_runs_prevent_any_work(self) -> None:
        closed = self._run_id()
        self.manager.transition_status(closed, ResearchRunStatus.CANCELLED)
        fetcher = RecordingFetcher()

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(research_run_id=closed),
            )
        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )
        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(step(), ResearchPlanExecutionContext())

        self.assertEqual(fetcher.urls, [])

    def test_detail_never_dumps_source_content(self) -> None:
        run_id = self._run_id()

        result = self._operation(RecordingFetcher()).run(
            step(),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertNotIn("Authorized source body text.", result.detail)
        self.assertLessEqual(len(result.detail), 500)


if __name__ == "__main__":
    unittest.main()
