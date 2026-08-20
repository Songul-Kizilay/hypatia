"""Persistence tests for strict atomic research-run JSON snapshots."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


class JsonFileResearchRunStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "research_runs.json"
        self.store = JsonFileResearchRunStore(self.path)
        self.now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_missing_store_loads_as_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_round_trip_preserves_sources_failures_and_unicode(self) -> None:
        run = ResearchRun(
            run_id="run-1",
            question="Songül için kanıt nedir?",
            status=ResearchRunStatus.COLLECTING,
            sources=(
                ResearchSourceRecord(
                    document_id="document-1",
                    url="https://example.com/research",
                    title="Example",
                    content_type="text/html",
                    fetched_at=self.now,
                    added_at=self.now,
                ),
            ),
            failures=(
                ResearchFailureRecord(
                    stage="source_fetch",
                    reason="Timed out.",
                    occurred_at=self.now,
                ),
            ),
            created_at=self.now,
            updated_at=self.now,
            evidence=(
                ResearchEvidenceRecord(
                    evidence_id="evidence-1",
                    source_document_id="document-1",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    excerpt="Evidence paragraph.",
                    excerpt_truncated=False,
                    chunk_sha256="a" * 64,
                    note="Supports the claim.",
                    recorded_at=self.now,
                ),
            ),
        )

        self.store.save([run])

        self.assertEqual(self.store.load(), [run])
        self.assertTrue(self.path.read_text(encoding="utf-8").endswith("\n"))

    def test_rejects_unknown_fields_schema_and_duplicate_ids(self) -> None:
        for document in (
            {"schema_version": 3, "runs": []},
            {"schema_version": True, "runs": []},
            {"schema_version": 1, "runs": [], "unexpected": True},
        ):
            with self.subTest(document=document):
                self.path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(ResearchError):
                    self.store.load()

        run = ResearchRun(
            run_id="run-1",
            question="Question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )
        with self.assertRaisesRegex(ResearchError, "duplicate run IDs"):
            self.store.save([run, run])

    def test_loads_v1_without_evidence_and_rewrites_as_v2(self) -> None:
        legacy_document = {
            "schema_version": 1,
            "runs": [
                {
                    "run_id": "legacy-run",
                    "question": "Legacy question",
                    "status": "collecting",
                    "sources": [],
                    "failures": [],
                    "created_at": self.now.isoformat(),
                    "updated_at": self.now.isoformat(),
                }
            ],
        }
        self.path.write_text(json.dumps(legacy_document), encoding="utf-8")

        runs = self.store.load()
        self.store.save(runs)

        self.assertEqual(runs[0].evidence, ())
        rewritten = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(rewritten["schema_version"], 2)
        self.assertEqual(rewritten["runs"][0]["evidence"], [])

    def test_invalid_json_is_reported_without_exposing_raw_content(self) -> None:
        self.path.write_text("{secret", encoding="utf-8")

        with self.assertRaisesRegex(ResearchError, "Unable to read") as context:
            self.store.load()

        self.assertNotIn("secret", str(context.exception))

    def test_failed_atomic_replace_preserves_previous_snapshot_and_cleans_temp(
        self,
    ) -> None:
        original = ResearchRun(
            run_id="run-1",
            question="Original question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )
        replacement = ResearchRun(
            run_id="run-2",
            question="Replacement question",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=self.now,
            updated_at=self.now,
        )
        self.store.save([original])
        original_document = self.path.read_text(encoding="utf-8")

        with patch(
            "research.JsonFileResearchRunStore.os.replace",
            side_effect=OSError("replace unavailable"),
        ):
            with self.assertRaisesRegex(ResearchError, "Unable to write"):
                self.store.save([replacement])

        self.assertEqual(self.path.read_text(encoding="utf-8"), original_document)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
