from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceFetchStepOperation import SourceFetchStepOperation

AUTHORIZED_URL = "https://example.test/authorized"
ACQUISITION_BOUNDARY = "not accepted, not indexed, not evidence"


class RecordingFetcher:
    """Return a caller-supplied source and record every requested URL."""

    def __init__(
        self,
        source: ResearchSource | None = None,
        error: Exception | None = None,
    ) -> None:
        self.source = source
        self.error = error
        self.urls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        assert self.source is not None
        return self.source


def source(content: str = "Accepted source body text.") -> ResearchSource:
    return ResearchSource(
        url=AUTHORIZED_URL,
        title="Authorized source",
        content=content,
        content_type="text/html",
        fetched_at=datetime(2026, 8, 23, tzinfo=UTC),
    )


def step(
    url: str = AUTHORIZED_URL,
    instruction: str = "Acquire the authorized source",
) -> ResearchPlanStep:
    return ResearchPlanStep(
        step_id="step-1",
        instruction=instruction,
        capability=ResearchPlanStepCapability.SOURCE_FETCH,
        authorized_source_url=url,
    )


class SourceFetchStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _run_id(self) -> str:
        return self.manager.create("What evidence supports the claim?").run_id

    def _operation(self, fetcher: RecordingFetcher) -> SourceFetchStepOperation:
        return SourceFetchStepOperation(fetcher, self.manager)  # type: ignore[arg-type]

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(
            self._operation(RecordingFetcher()).operation_name,
            "source_fetch",
        )

    def test_fetches_only_the_explicitly_authorized_url(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher(source())

        result = self._operation(fetcher).run(
            step(),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertTrue(result.performed)
        self.assertEqual(fetcher.urls, [AUTHORIZED_URL])
        self.assertIn(AUTHORIZED_URL, result.detail)
        self.assertIn(ACQUISITION_BOUNDARY, result.detail)

    def test_missing_authorization_prevents_any_network_call(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher(source())

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(url=""),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(fetcher.urls, [])

    def test_instruction_text_urls_are_never_fetched(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher(source())

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(url="", instruction=f"Fetch {AUTHORIZED_URL} right now"),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(fetcher.urls, [])

    def test_discovered_candidates_are_never_auto_fetched(self) -> None:
        run_id = self._run_id()
        self.manager.add_discovery(
            run_id,
            "What evidence supports the claim?",
            "stub_provider",
            [
                ResearchSourceCandidate(
                    url="https://example.test/discovered",
                    title="Discovered candidate",
                    snippet="A snippet.",
                )
            ],
        )
        fetcher = RecordingFetcher(source())

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(url=""),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        self.assertEqual(fetcher.urls, [])

    def test_cancellation_before_fetch_means_zero_network_calls(self) -> None:
        run_id = self._run_id()
        fetcher = RecordingFetcher(source())
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

    def test_cancellation_after_fetch_persists_no_research_state(self) -> None:
        run_id = self._run_id()
        signal = CancellationSignal()

        class CancellingFetcher(RecordingFetcher):
            def fetch(self, url: str) -> ResearchSource:
                result = super().fetch(url)
                signal.cancel()
                return result

        fetcher = CancellingFetcher(source())

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(
                    research_run_id=run_id,
                    cancellation_token=signal,
                ),
            )

        self.assertEqual(fetcher.urls, [AUTHORIZED_URL])
        run = self.manager.get(run_id)
        self.assertEqual(run.sources, ())
        self.assertEqual(run.evidence, ())
        self.assertEqual(run.failures, ())

    def test_successful_fetch_accepts_nothing(self) -> None:
        run_id = self._run_id()

        self._operation(RecordingFetcher(source())).run(
            step(),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        run = self.manager.get(run_id)
        self.assertEqual(run.sources, ())
        self.assertEqual(run.evidence, ())
        self.assertEqual(run.assessments, ())
        self.assertEqual(run.claims, ())

    def test_pipeline_rejection_fails_honestly_and_is_audited(self) -> None:
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

    def test_domain_rejects_empty_source_content(self) -> None:
        for empty in ("", "   "):
            with self.subTest(empty=empty):
                with self.assertRaises(ResearchError):
                    source(content=empty)

    def test_empty_content_never_becomes_a_successful_fetch(self) -> None:
        run_id = self._run_id()

        class BlankSource:
            """A non-conforming fetcher result used as defence in depth."""

            content = "   "
            content_type = "text/html"

        class BlankFetcher(RecordingFetcher):
            def fetch(self, url: str) -> ResearchSource:
                self.urls.append(url)
                return BlankSource()  # type: ignore[return-value]

        fetcher = BlankFetcher()

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(research_run_id=run_id),
            )

        run = self.manager.get(run_id)
        self.assertEqual(run.sources, ())
        self.assertEqual(len(run.failures), 1)

    def test_closed_and_unknown_runs_prevent_network_calls(self) -> None:
        closed_run_id = self._run_id()
        self.manager.transition_status(closed_run_id, ResearchRunStatus.CANCELLED)
        fetcher = RecordingFetcher(source())

        with self.assertRaises(ResearchError):
            self._operation(fetcher).run(
                step(),
                ResearchPlanExecutionContext(research_run_id=closed_run_id),
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
        secret = "SENSITIVE-BODY-TEXT-THAT-MUST-NOT-LEAK"

        result = self._operation(RecordingFetcher(source(content=secret))).run(
            step(),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertNotIn(secret, result.detail)
        self.assertIn("character(s)", result.detail)
        self.assertLessEqual(len(result.detail), 500)

    def test_detail_bounds_a_hostile_url(self) -> None:
        run_id = self._run_id()
        long_url = "https://example.test/" + ("a" * 1_000)

        result = self._operation(RecordingFetcher(source())).run(
            step(url=long_url),
            ResearchPlanExecutionContext(research_run_id=run_id),
        )

        self.assertLessEqual(len(result.detail), 500)
        self.assertIn("...", result.detail)

    def test_authorized_url_is_validated_on_the_step(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanStep(
                step_id="step-1",
                instruction="Fetch",
                authorized_source_url="https://example.test/a\nHost: evil",
            )
        with self.assertRaises(ResearchError):
            ResearchPlanStep(
                step_id="step-1",
                instruction="Fetch",
                authorized_source_url="https://example.test/" + ("a" * 2_100),
            )


if __name__ == "__main__":
    unittest.main()
