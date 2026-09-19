"""Discovery-candidate identity is recorded at selection and never matched by URL.

Each discovery records a stable identity per candidate.  A source selected from a
discovery records that identity on the run's own source observation.  Integrity
checks only confirm it: the candidate must be in this run's discoveries and its
URL must be the URL this run requested.  Nothing is recovered from URLs later.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate

URL = "https://example.test/advisory"
QUESTION = "What does the advisory say?"
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def candidate(url: str = URL, title: str = "Advisory") -> ResearchSourceCandidate:
    return ResearchSourceCandidate(url=url, title=title, snippet="A snippet.")


def fetched(url: str = URL) -> ResearchSource:
    return ResearchSource(
        url=url,
        title="Advisory",
        content="The advisory text.",
        content_type="text/plain",
        fetched_at=NOW,
    )


class DiscoveryCandidateProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "runs.json"
        self.runs = ResearchRunManager(
            JsonFileResearchRunStore(self.path),
            clock=lambda: NOW + timedelta(days=1),
        )
        self.acceptance = ResearchSourceAcceptanceService(KnowledgeEngine(), self.runs)
        self.run_a = self.runs.create(QUESTION).run_id
        self.run_b = self.runs.create(QUESTION).run_id

    def discover(self, run_id: str, *candidates: ResearchSourceCandidate):  # type: ignore[no-untyped-def]
        return self.runs.add_discovery(
            run_id, QUESTION, "fixture", list(candidates or (candidate(),))
        ).discoveries[-1]

    def accept_selected(self, run_id: str, discovery_id: str, url: str = URL) -> str:
        preview = self.runs.preview_candidate_acceptance(run_id, discovery_id, url)
        assert preview.candidate_id is not None
        result = self.acceptance.accept(
            fetched(url),
            run_id,
            requested_url=url,
            discovery_candidate_id=preview.candidate_id,
        )
        self.assertTrue(result.accepted, result)
        return preview.candidate_id

    def test_discovery_assigns_stable_unique_candidate_ids_that_survive_restart(self):
        discovery = self.discover(
            self.run_a, candidate(), candidate("https://example.test/other")
        )

        restored = JsonFileResearchRunStore(self.path).load()[0].discoveries[0]

        self.assertEqual(len(set(discovery.candidate_ids)), 2)
        self.assertEqual(restored.candidate_ids, discovery.candidate_ids)

    def test_selected_candidate_is_recorded_exactly_and_survives_restart(self):
        discovery = self.discover(self.run_a)

        selected = self.accept_selected(self.run_a, discovery.discovery_id)

        source = JsonFileResearchRunStore(self.path).load()[0].sources[0]
        self.assertEqual(source.discovery_candidate_id, selected)
        self.assertEqual(selected, discovery.candidate_ids[0])

    def test_same_url_in_two_discoveries_keeps_distinct_candidate_identities(self):
        first = self.discover(self.run_a)
        second = self.discover(self.run_a)

        selected = self.accept_selected(self.run_a, second.discovery_id)

        self.assertNotEqual(first.candidate_ids[0], second.candidate_ids[0])
        self.assertEqual(selected, second.candidate_ids[0])
        self.assertEqual(
            self.runs.get(self.run_a).sources[0].discovery_candidate_id,
            second.candidate_ids[0],
        )

    def test_same_url_in_two_runs_keeps_separate_candidate_provenance(self):
        discovery_a = self.discover(self.run_a)
        discovery_b = self.discover(self.run_b)

        selected_a = self.accept_selected(self.run_a, discovery_a.discovery_id)
        selected_b = self.accept_selected(self.run_b, discovery_b.discovery_id)

        self.assertNotEqual(selected_a, selected_b)
        self.assertEqual(
            self.runs.get(self.run_b).sources[0].discovery_candidate_id, selected_b
        )

    def test_a_source_cannot_cite_another_runs_candidate(self):
        discovery_a = self.discover(self.run_a)
        self.discover(self.run_b)

        result = self.acceptance.accept(
            fetched(),
            self.run_b,
            requested_url=URL,
            discovery_candidate_id=discovery_a.candidate_ids[0],
        )

        self.assertFalse(result.accepted)
        self.assertEqual(self.runs.get(self.run_b).sources, ())

    def test_tampered_candidate_references_fail_closed(self):
        discovery = self.discover(
            self.run_a, candidate(), candidate("https://example.test/other")
        )
        self.accept_selected(self.run_a, discovery.discovery_id)
        run = self.runs.get(self.run_a)
        source = run.sources[0]
        for tampered in (
            replace(source, discovery_candidate_id="unknown-candidate"),
            replace(source, discovery_candidate_id=discovery.candidate_ids[1]),
            replace(source, requested_url=None),
        ):
            with self.subTest(tampered=tampered), self.assertRaises(ResearchError):
                replace(run, sources=(tampered,))
        document = json.loads(self.path.read_text("utf-8"))
        document["runs"][0]["sources"][0]["discovery_candidate_id"] = (
            discovery.candidate_ids[1]
        )
        self.path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(ResearchError):
            JsonFileResearchRunStore(self.path).load()

    def test_legacy_records_load_without_candidate_identity(self):
        discovery = self.discover(self.run_a)
        self.accept_selected(self.run_a, discovery.discovery_id)
        document = json.loads(self.path.read_text("utf-8"))
        document["schema_version"] = 16
        for run in document["runs"]:
            for source in run["sources"]:
                source.pop("discovery_candidate_id")
                source.pop("observation_id", None)
            for record in run["discoveries"]:
                record.pop("candidate_ids")
        self.path.write_text(json.dumps(document), encoding="utf-8")

        loaded = JsonFileResearchRunStore(self.path).load()[0]

        self.assertEqual(loaded.discoveries[0].candidate_ids, ())
        self.assertIsNone(loaded.sources[0].discovery_candidate_id)
        self.assertIn(
            "- **Discovery candidate:** unrecorded",
            render_research_run_markdown(loaded),
        )

    def test_no_url_fallback_when_selection_did_not_record_a_candidate(self):
        self.discover(self.run_a)

        self.acceptance.accept(fetched(), self.run_a, requested_url=URL)

        # The URL matches a discovered candidate, but no selection was recorded.
        self.assertIsNone(self.runs.get(self.run_a).sources[0].discovery_candidate_id)

    def test_legacy_discovery_preview_has_no_candidate_identity(self):
        discovery = self.discover(self.run_a)
        run = self.runs.get(self.run_a)
        legacy = replace(run, discoveries=(replace(discovery, candidate_ids=()),))

        self.assertIsNone(
            legacy.discoveries[0].candidate_id_of(legacy.discoveries[0].candidates[0])
        )


if __name__ == "__main__":
    unittest.main()
