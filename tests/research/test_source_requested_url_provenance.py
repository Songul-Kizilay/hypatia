"""Each run's source observation keeps the URL it requested beside the final URL.

A validated redirect makes the final URL differ from the requested one.  The
requested URL is the resource this run asked for; it is recorded on the run's
own source record, survives restart, is never copied from the final URL, and is
never shared between runs even when their content version is shared.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchSource import ResearchSource
from research.ResearchSourceRecord import ResearchSourceRecord

FINAL = "https://example.test/advisory"
FIRST = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def fetched(fetched_at: datetime = FIRST) -> ResearchSource:
    return ResearchSource(
        url=FINAL,
        title="Advisory",
        content="The advisory text.",
        content_type="text/plain",
        fetched_at=fetched_at,
    )


class RequestedUrlProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "runs.json"
        self.runs = ResearchRunManager(
            JsonFileResearchRunStore(self.path),
            clock=lambda: FIRST + timedelta(days=5),
        )
        self.acceptance = ResearchSourceAcceptanceService(KnowledgeEngine(), self.runs)
        self.run_a = self.runs.create("Question A").run_id
        self.run_b = self.runs.create("Question B").run_id

    def test_requested_and_final_url_are_both_recorded_and_survive_restart(self):
        self.acceptance.accept(
            fetched(), self.run_a, requested_url="https://old.example.test/advisory"
        )

        source = JsonFileResearchRunStore(self.path).load()[0].sources[0]

        self.assertEqual(source.url, FINAL)
        self.assertEqual(source.requested_url, "https://old.example.test/advisory")

    def test_shared_content_version_keeps_each_runs_own_requested_url(self):
        self.acceptance.accept(
            fetched(), self.run_a, requested_url="https://a.example.test/advisory"
        )
        self.acceptance.accept(
            fetched(FIRST + timedelta(days=1)),
            self.run_b,
            requested_url="https://b.example.test/advisory",
        )

        source_a = self.runs.get(self.run_a).sources[0]
        source_b = self.runs.get(self.run_b).sources[0]
        self.assertEqual(source_a.document_id, source_b.document_id)
        self.assertEqual(
            (source_a.requested_url, source_b.requested_url),
            ("https://a.example.test/advisory", "https://b.example.test/advisory"),
        )

    def test_unknown_requested_url_is_left_unrecorded_not_copied(self):
        self.acceptance.accept(fetched(), self.run_a)

        source = self.runs.get(self.run_a).sources[0]

        self.assertIsNone(source.requested_url)
        markdown = render_research_run_markdown(self.runs.get(self.run_a))
        self.assertIn("- **Requested URL:** unrecorded", markdown)

    def test_schema_15_sources_load_with_unrecorded_requested_url(self):
        self.acceptance.accept(fetched(), self.run_a, requested_url=FINAL)
        document = json.loads(self.path.read_text("utf-8"))
        document["schema_version"] = 15
        for run in document["runs"]:
            for source in run["sources"]:
                source.pop("requested_url")
                source.pop("discovery_candidate_id", None)
                source.pop("observation_id", None)
                source.pop("revalidation_of_observation_id", None)
                source.pop("revalidation_execution_id", None)
        self.path.write_text(json.dumps(document), encoding="utf-8")

        loaded = JsonFileResearchRunStore(self.path).load()

        self.assertIsNone(loaded[0].sources[0].requested_url)

    def test_invalid_requested_url_is_refused(self):
        for value in ("", "   ", "x" * 4_097):
            with self.subTest(length=len(value)), self.assertRaises(ResearchError):
                ResearchSourceRecord.from_source(
                    fetched(), "document-1", FIRST, requested_url=value
                )

    def test_markdown_export_shows_requested_url(self):
        self.acceptance.accept(
            fetched(), self.run_a, requested_url="https://old.example.test/advisory"
        )

        markdown = render_research_run_markdown(self.runs.get(self.run_a))

        self.assertIn(
            "- **Requested URL:** https://old.example.test/advisory", markdown
        )


if __name__ == "__main__":
    unittest.main()
