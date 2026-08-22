from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.AcceptedSourceListingStepOperation import (
    AcceptedSourceListingStepOperation,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource


def _source(slug: str) -> ResearchSource:
    return ResearchSource(
        url=f"https://example.test/{slug}",
        title=f"Source {slug}",
        content="Example accepted source content.",
        content_type="text/html",
        fetched_at=datetime(2026, 8, 23, tzinfo=UTC),
    )


class AcceptedSourceListingStepOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        path = Path(self.temporary_directory.name) / "runs.json"
        self.event_bus = EventBus()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(path))
        self.operation = AcceptedSourceListingStepOperation(self.manager)
        self.step = ResearchPlanStep(step_id="step-1", instruction="List sources")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_operation_name_is_stable(self) -> None:
        self.assertEqual(self.operation.operation_name, "accepted_source_listing")

    def test_zero_accepted_sources_is_a_performed_listing(self) -> None:
        run = self.manager.create("What evidence exists?")

        result = self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run.run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("Listed 0 accepted source(s)", result.detail)
        self.assertIn("no accepted sources yet", result.detail)
        self.assertIn("no evidence was established", result.detail)

    def test_listing_reports_document_identifiers_only(self) -> None:
        run = self.manager.create("What evidence exists?")
        self.manager.add_source(run.run_id, _source("a"), "doc-1")

        result = self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run.run_id),
        )

        self.assertTrue(result.performed)
        self.assertIn("Listed 1 accepted source(s)", result.detail)
        self.assertIn("doc-1", result.detail)
        self.assertIn("no source content was read", result.detail)

    def test_large_catalogs_stay_bounded(self) -> None:
        run = self.manager.create("What evidence exists?")
        for index in range(8):
            self.manager.add_source(run.run_id, _source(str(index)), f"doc-{index}")

        result = self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run.run_id),
        )

        self.assertIn("Listed 8 accepted source(s)", result.detail)
        self.assertIn("(+5 more)", result.detail)
        self.assertNotIn("doc-7", result.detail)
        self.assertLessEqual(len(result.detail), 500)

    def test_unknown_run_fails_safely(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(
                self.step,
                ResearchPlanExecutionContext(research_run_id="missing-run"),
            )

    def test_missing_run_binding_fails_safely(self) -> None:
        with self.assertRaises(ResearchError):
            self.operation.run(self.step, ResearchPlanExecutionContext())

    def test_listing_performs_no_mutation(self) -> None:
        run = self.manager.create("What evidence exists?")
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        self.operation.run(
            self.step,
            ResearchPlanExecutionContext(research_run_id=run.run_id),
        )

        self.assertEqual(events, [])
        self.assertEqual(self.manager.get(run.run_id), run)


class ResearchPlanExecutionContextTests(unittest.TestCase):
    def test_defaults_to_no_research_run(self) -> None:
        context = ResearchPlanExecutionContext()

        self.assertIsNone(context.research_run_id)
        self.assertFalse(context.has_research_run)

    def test_normalizes_and_validates_the_run_id(self) -> None:
        self.assertEqual(
            ResearchPlanExecutionContext(research_run_id="  run-1  ").research_run_id,
            "run-1",
        )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionContext(research_run_id="   ")
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionContext(research_run_id="x" * 201)
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionContext(research_run_id=5)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
