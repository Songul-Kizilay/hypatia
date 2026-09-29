"""Persistence tests for the atomic, append-only reproduction record store."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchReproductionStore import (
    JsonFileResearchReproductionStore,
    ResearchReproductionDocument,
)
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)


def reproduction(
    *, reproduction_id: str = "reproduction-1", program_id: str = "program-a"
) -> ResearchReproductionRecord:
    return ResearchReproductionRecord(
        reproduction_id=reproduction_id,
        program_id=program_id,
        recipe_id="recipe-1",
        subject_kind=ResearchSecurityValidationRecipeSubjectKind.FINDING,
        subject_id="finding-1",
        outcome=ResearchReproductionOutcome.REPRODUCED,
        notes="notes",
        evidence_ids=("a" * 64,),
        recorded_at=RECORDED,
    )


class ResearchReproductionDocumentTests(unittest.TestCase):
    def test_default_document_is_empty(self) -> None:
        self.assertEqual(ResearchReproductionDocument().reproductions, ())

    def test_duplicate_reproduction_ids_are_rejected(self) -> None:
        value = reproduction()
        with self.assertRaisesRegex(ResearchError, "duplicate reproduction IDs"):
            ResearchReproductionDocument(reproductions=(value, value))

    def test_non_tuple_or_wrong_typed_members_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchReproductionDocument(
                reproductions=[reproduction()]  # type: ignore[arg-type]
            )
        with self.assertRaises(ResearchError):
            ResearchReproductionDocument(
                reproductions=("not-a-reproduction",)  # type: ignore[arg-type]
            )


class JsonFileResearchReproductionStoreTests(unittest.TestCase):
    def test_missing_store_is_empty_and_round_trip_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            self.assertEqual(
                JsonFileResearchReproductionStore(path).load().reproductions, ()
            )

            JsonFileResearchReproductionStore(path).save(
                ResearchReproductionDocument(reproductions=(reproduction(),))
            )
            reloaded = JsonFileResearchReproductionStore(path).load()

            self.assertEqual(reloaded.reproductions, (reproduction(),))

    def test_store_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            store = JsonFileResearchReproductionStore(path)
            first = reproduction()
            store.save(ResearchReproductionDocument(reproductions=(first,)))

            with self.assertRaisesRegex(ResearchError, "append-only"):
                store.save(ResearchReproductionDocument())
            with self.assertRaisesRegex(ResearchError, "append-only"):
                store.save(
                    ResearchReproductionDocument(
                        reproductions=(reproduction(reproduction_id="reproduction-2"),)
                    )
                )

            second = reproduction(reproduction_id="reproduction-2")
            store.save(ResearchReproductionDocument(reproductions=(first, second)))
            self.assertEqual(store.load().reproductions, (first, second))

    def test_unknown_fields_and_schema_versions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            path.write_text(
                json.dumps({"schema_version": 1, "reproductions": [], "extra": True})
            )
            with self.assertRaises(ResearchError):
                JsonFileResearchReproductionStore(path).load()
            path.write_text(json.dumps({"schema_version": 2, "reproductions": []}))
            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchReproductionStore(path).load()
            path.write_text(json.dumps({"schema_version": True, "reproductions": []}))
            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchReproductionStore(path).load()

    def test_malformed_subject_kind_in_persisted_content_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "reproductions": [
                            {
                                "reproduction_id": "reproduction-1",
                                "program_id": "program-a",
                                "recipe_id": "recipe-1",
                                "subject_kind": "not-a-real-kind",
                                "subject_id": "finding-1",
                                "outcome": "reproduced",
                                "notes": "",
                                "evidence_ids": [],
                                "recorded_at": RECORDED.isoformat(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ResearchError, "subject kind"):
                JsonFileResearchReproductionStore(path).load()

    def test_malformed_outcome_in_persisted_content_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "reproductions": [
                            {
                                "reproduction_id": "reproduction-1",
                                "program_id": "program-a",
                                "recipe_id": "recipe-1",
                                "subject_kind": "finding",
                                "subject_id": "finding-1",
                                "outcome": "exploited",
                                "notes": "",
                                "evidence_ids": [],
                                "recorded_at": RECORDED.isoformat(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ResearchError, "outcome"):
                JsonFileResearchReproductionStore(path).load()

    def test_secret_shaped_persisted_notes_fail_closed_without_reflection(
        self,
    ) -> None:
        sentinel = "distinct-persisted-secret"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "reproductions": [
                            {
                                "reproduction_id": "reproduction-1",
                                "program_id": "program-a",
                                "recipe_id": "recipe-1",
                                "subject_kind": "finding",
                                "subject_id": "finding-1",
                                "outcome": "reproduced",
                                "notes": f"password={sentinel}",
                                "evidence_ids": [],
                                "recorded_at": RECORDED.isoformat(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ResearchError) as raised:
                JsonFileResearchReproductionStore(path).load()

            self.assertIn("refused as", str(raised.exception))
            self.assertNotIn(sentinel, str(raised.exception))

    def test_bounded_record_count_is_enforced(self) -> None:
        # The declared ceiling below is only a pinned value unless something
        # actually proves the document refuses to hold more records than it
        # names -- mirrors `JsonFileResearchSecurityHypothesisStore`'s own
        # `test_bounded_counts_are_enforced`.
        module = "research.JsonFileResearchReproductionStore"
        with patch(f"{module}.MAX_REPRODUCTIONS", 1):
            with self.assertRaisesRegex(ResearchError, "too many records"):
                ResearchReproductionDocument(
                    reproductions=(
                        reproduction(reproduction_id="reproduction-1"),
                        reproduction(reproduction_id="reproduction-2"),
                    )
                )

    def test_oversized_store_is_rejected_on_load(self) -> None:
        # Same reasoning as the record-count ceiling above, for the byte
        # ceiling -- mirrors `JsonFileResearchSecurityHypothesisStore`'s own
        # `test_oversized_store_is_rejected`.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            path.write_text(
                json.dumps({"schema_version": 1, "reproductions": []}),
                encoding="utf-8",
            )
            module = "research.JsonFileResearchReproductionStore"
            with patch(f"{module}.MAX_REPRODUCTION_STORE_BYTES", 10):
                with self.assertRaisesRegex(ResearchError, "too large"):
                    JsonFileResearchReproductionStore(path).load()

    def test_the_declared_ceilings_are_the_reviewed_values(self) -> None:
        from research.JsonFileResearchReproductionStore import (
            MAX_REPRODUCTION_STORE_BYTES,
            MAX_REPRODUCTIONS,
        )

        self.assertEqual(MAX_REPRODUCTIONS, 5_000)
        self.assertEqual(MAX_REPRODUCTION_STORE_BYTES, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
