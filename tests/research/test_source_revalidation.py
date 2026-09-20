"""Characterization coverage for explicit source-observation revalidation."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome

RESOURCE = "https://example.test/advisory"
FIRST = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
LATER = FIRST + timedelta(days=1)


def source(content: str, fetched_at: datetime) -> ResearchSource:
    return ResearchSource(
        url="https://cdn.example.test/advisory.txt",
        title="Advisory",
        content=content,
        content_type="text/plain",
        fetched_at=fetched_at,
    )


class SourceRevalidationCharacterizationTests(unittest.TestCase):
    def _manager(self, path: Path) -> ResearchRunManager:
        return ResearchRunManager(
            JsonFileResearchRunStore(path),
            clock=lambda: LATER,
            observation_id_factory=iter(("observation-a", "observation-b")).__next__,
            revalidation_id_factory=lambda: "revalidation-1",
        )

    def _two_observations(
        self,
        manager: ResearchRunManager,
        *,
        earlier_content: str = "Version one.",
        later_content: str = "Version two.",
        earlier_requested_url: str | None = RESOURCE,
        later_requested_url: str | None = RESOURCE,
    ) -> tuple[str, str]:
        earlier_run = manager.create("What did the advisory say?")
        later_run = manager.create("What does the advisory say now?")
        manager.add_source(
            earlier_run.run_id,
            source(earlier_content, FIRST),
            "document-one",
            requested_url=earlier_requested_url,
        )
        manager.add_source(
            later_run.run_id,
            source(later_content, LATER),
            "document-two",
            requested_url=later_requested_url,
        )
        return earlier_run.run_id, later_run.run_id

    def test_records_an_explicit_cross_run_relation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory) / "runs.json")
            earlier_run_id, later_run_id = self._two_observations(manager)

            relation = manager.record_source_revalidation(
                earlier_run_id,
                "observation-a",
                later_run_id,
                "observation-b",
            )

        self.assertEqual(relation.earlier_observation_id, "observation-a")
        self.assertEqual(
            relation.outcome, ResearchSourceRevalidationOutcome.CONTENT_CHANGED
        )

    def test_records_unchanged_content_only_when_exact_hashes_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory) / "runs.json")
            earlier_run_id, later_run_id = self._two_observations(
                manager,
                earlier_content="Identical content.",
                later_content="Identical content.",
            )

            relation = manager.record_source_revalidation(
                earlier_run_id,
                "observation-a",
                later_run_id,
                "observation-b",
            )

        self.assertEqual(
            relation.outcome, ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED
        )

    def test_matching_observations_do_not_create_a_relation_without_intent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory) / "runs.json")
            self._two_observations(manager)

            self.assertEqual(manager.source_revalidations(), [])

    def test_restart_restores_the_relation_and_suppresses_a_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            manager = self._manager(path)
            earlier_run_id, later_run_id = self._two_observations(manager)
            expected = manager.record_source_revalidation(
                earlier_run_id,
                "observation-a",
                later_run_id,
                "observation-b",
            )

            restored = self._manager(path)
            restored.load()
            (inspection,) = restored.source_revalidations()

            self.assertEqual(inspection.record, expected)
            with self.assertRaisesRegex(ResearchError, "already exists"):
                restored.record_source_revalidation(
                    earlier_run_id,
                    "observation-a",
                    later_run_id,
                    "observation-b",
                )

    def test_rejects_missing_or_different_resource_lineage_without_a_relation(
        self,
    ) -> None:
        cases = (
            (None, RESOURCE, "requested URL"),
            (RESOURCE, "https://other.example.test/advisory", "matching recorded"),
        )
        for earlier_url, later_url, message in cases:
            with self.subTest(earlier_url=earlier_url, later_url=later_url):
                with tempfile.TemporaryDirectory() as directory:
                    manager = self._manager(Path(directory) / "runs.json")
                    earlier_run_id, later_run_id = self._two_observations(
                        manager,
                        earlier_requested_url=earlier_url,
                        later_requested_url=later_url,
                    )

                    with self.assertRaisesRegex(ResearchError, message):
                        manager.record_source_revalidation(
                            earlier_run_id,
                            "observation-a",
                            later_run_id,
                            "observation-b",
                        )
                    self.assertEqual(manager.source_revalidations(), [])

    def test_rejects_reversed_observation_order_without_a_relation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory) / "runs.json")
            earlier_run_id, later_run_id = self._two_observations(manager)

            with self.assertRaisesRegex(ResearchError, "earlier"):
                manager.record_source_revalidation(
                    later_run_id,
                    "observation-b",
                    earlier_run_id,
                    "observation-a",
                )
            self.assertEqual(manager.source_revalidations(), [])

    def test_tampered_observation_binding_fails_closed_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            manager = self._manager(path)
            earlier_run_id, later_run_id = self._two_observations(manager)
            manager.record_source_revalidation(
                earlier_run_id,
                "observation-a",
                later_run_id,
                "observation-b",
            )
            document = json.loads(path.read_text(encoding="utf-8"))
            document["source_revalidations"][0]["outcome"] = "content_unchanged"
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(ResearchError, "outcome"):
                self._manager(path).load()

    def test_legacy_document_without_relations_remains_truthfully_readable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            manager = self._manager(path)
            self._two_observations(manager)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["schema_version"] = 18
            document.pop("source_revalidations")
            for run in document["runs"]:
                for source in run["sources"]:
                    source.pop("revalidation_of_observation_id")
                    source.pop("revalidation_execution_id")
            path.write_text(json.dumps(document), encoding="utf-8")

            restored = self._manager(path)
            restored.load()

            self.assertEqual(restored.source_revalidations(), [])

    def test_recording_a_relation_does_not_mutate_evidence_claims_or_run_lifecycle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = self._manager(Path(directory) / "runs.json")
            earlier_run_id, later_run_id = self._two_observations(manager)
            earlier_before = manager.get(earlier_run_id)
            later_before = manager.get(later_run_id)

            manager.record_source_revalidation(
                earlier_run_id,
                "observation-a",
                later_run_id,
                "observation-b",
            )

            self.assertEqual(manager.get(earlier_run_id), earlier_before)
            self.assertEqual(manager.get(later_run_id), later_before)
