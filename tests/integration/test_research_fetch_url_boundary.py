"""Unsafe URLs are refused before any socket is opened.

A live test pasted http://127.0.0.1:11434 into ordinary chat and Hypatia only
explained what localhost means. That was correct behaviour, but it proved
nothing: ordinary chat never reaches the fetcher, so the fetch boundary was
never exercised at all.

These tests go through the real fetch path instead — the real validator, the
real HttpResearchSourceFetcher, and the real authorized-fetch step operation —
with an opener that records every call. The assertion is not merely that the
fetch fails. It is that the opener was never called, because rejection has to
happen before the request leaves the process, not after a connection reveals
what is listening.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.HttpResearchSourceFetcher import HttpResearchSourceFetcher
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.SourceFetchStepOperation import SourceFetchStepOperation

OLLAMA_URL = "http://127.0.0.1:11434"

REFUSED_URLS = (
    OLLAMA_URL,
    "http://127.0.0.1:11434/v1/chat/completions",
    "https://127.0.0.1:11434",
    "http://localhost:11434",
    "https://localhost/admin",
    "https://[::1]/",
    "https://10.0.0.5/internal",
    "https://192.168.1.1/router",
    "https://172.16.0.1/private",
    "https://169.254.169.254/latest/meta-data/",
    "https://user:secret@example.com/",
    "http://example.com/plain-http",
    "ftp://example.com/file.txt",
    "file:///etc/passwd",
    "https://example.com:8443/nonstandard-port",
)


class RecordingOpener:
    """Fail loudly if anything asks it to open a connection."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def open(self, request: object, timeout: float | None = None) -> object:
        self.calls.append(getattr(request, "full_url", repr(request)))
        raise AssertionError("A refused URL reached the network layer.")


class FetcherUrlBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.opener = RecordingOpener()
        self.fetcher = HttpResearchSourceFetcher(opener=self.opener)

    def test_the_local_ollama_endpoint_is_refused_before_any_connection(self) -> None:
        with self.assertRaises(ResearchError):
            self.fetcher.fetch(OLLAMA_URL)

        self.assertEqual(self.opener.calls, [])

    def test_every_unsafe_url_is_refused_before_any_connection(self) -> None:
        for url in REFUSED_URLS:
            with self.subTest(url=url):
                with self.assertRaises(ResearchError):
                    self.fetcher.fetch(url)

        self.assertEqual(self.opener.calls, [])

    def test_rejection_does_not_disclose_what_was_listening(self) -> None:
        with self.assertRaises(ResearchError) as raised:
            self.fetcher.fetch(OLLAMA_URL)

        message = str(raised.exception)
        self.assertNotIn("11434", message)
        self.assertNotIn("ollama", message.casefold())


class AuthorizedFetchStepBoundaryTests(unittest.TestCase):
    """The same refusal through the real authorized-fetch step operation."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.opener = RecordingOpener()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.manager.load()
        self.operation = SourceFetchStepOperation(
            HttpResearchSourceFetcher(opener=self.opener),
            self.manager,
        )
        self.run_id = self.manager.create("Which endpoint serves this model?").run_id

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def step(self, url: str) -> ResearchPlanStep:
        return ResearchPlanStep(
            step_id="step-1",
            instruction="Fetch the authorized source",
            capability=ResearchPlanStepCapability.SOURCE_FETCH,
            authorized_source_url=url,
        )

    def test_an_authorized_loopback_url_still_never_reaches_the_network(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(
                self.step(OLLAMA_URL),
                ResearchPlanExecutionContext(research_run_id=self.run_id),
            )

        self.assertEqual(self.opener.calls, [])

    def test_a_refused_fetch_accepts_no_source_and_records_no_evidence(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(
                self.step(OLLAMA_URL),
                ResearchPlanExecutionContext(research_run_id=self.run_id),
            )

        run = self.manager.get(self.run_id)
        self.assertEqual(run.sources, ())
        self.assertEqual(run.evidence, ())
        self.assertEqual(run.claims, ())

    def test_a_refused_fetch_records_a_bounded_failure_without_the_url(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(
                self.step("https://user:secret@example.com/"),
                ResearchPlanExecutionContext(research_run_id=self.run_id),
            )

        run = self.manager.get(self.run_id)
        recorded = " ".join(
            f"{failure.stage} {failure.reason}" for failure in run.failures
        )
        self.assertNotIn("secret", recorded)
        self.assertNotIn("user:", recorded)

    def test_every_unsafe_url_is_refused_through_the_step_operation(self) -> None:
        for url in REFUSED_URLS:
            with self.subTest(url=url):
                with self.assertRaises(ResearchError):
                    self.operation.run(
                        self.step(url),
                        ResearchPlanExecutionContext(research_run_id=self.run_id),
                    )

        self.assertEqual(self.opener.calls, [])
        self.assertEqual(self.manager.get(self.run_id).sources, ())


if __name__ == "__main__":
    unittest.main()
