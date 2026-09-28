"""Persistence tests for the atomic, append-only security validation recipe store."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from core.Exceptions import ResearchError
from research.JsonFileResearchSecurityValidationRecipeStore import (
    JsonFileResearchSecurityValidationRecipeStore,
    ResearchSecurityValidationRecipeDocument,
)
from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)


def recipe(
    *, recipe_id: str = "recipe-1", program_id: str = "program-a"
) -> ResearchSecurityValidationRecipeRecord:
    return ResearchSecurityValidationRecipeRecord(
        recipe_id=recipe_id,
        program_id=program_id,
        subject_kind=ResearchSecurityValidationRecipeSubjectKind.FINDING,
        subject_id="finding-1",
        steps=("Step one", "Step two"),
        notes="notes",
        created_at=RECORDED,
    )


class ResearchSecurityValidationRecipeDocumentTests(unittest.TestCase):
    def test_default_document_is_empty(self) -> None:
        self.assertEqual(ResearchSecurityValidationRecipeDocument().recipes, ())

    def test_duplicate_recipe_ids_are_rejected(self) -> None:
        value = recipe()
        with self.assertRaisesRegex(ResearchError, "duplicate recipe IDs"):
            ResearchSecurityValidationRecipeDocument(recipes=(value, value))

    def test_non_tuple_or_wrong_typed_members_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityValidationRecipeDocument(
                recipes=[recipe()]  # type: ignore[arg-type]
            )
        with self.assertRaises(ResearchError):
            ResearchSecurityValidationRecipeDocument(
                recipes=("not-a-recipe",)  # type: ignore[arg-type]
            )


class JsonFileResearchSecurityValidationRecipeStoreTests(unittest.TestCase):
    def test_missing_store_is_empty_and_round_trip_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            self.assertEqual(
                JsonFileResearchSecurityValidationRecipeStore(path).load().recipes, ()
            )

            JsonFileResearchSecurityValidationRecipeStore(path).save(
                ResearchSecurityValidationRecipeDocument(recipes=(recipe(),))
            )
            reloaded = JsonFileResearchSecurityValidationRecipeStore(path).load()

            self.assertEqual(reloaded.recipes, (recipe(),))

    def test_store_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            store = JsonFileResearchSecurityValidationRecipeStore(path)
            first = recipe()
            store.save(ResearchSecurityValidationRecipeDocument(recipes=(first,)))

            with self.assertRaisesRegex(ResearchError, "append-only"):
                store.save(ResearchSecurityValidationRecipeDocument())
            with self.assertRaisesRegex(ResearchError, "append-only"):
                store.save(
                    ResearchSecurityValidationRecipeDocument(
                        recipes=(recipe(recipe_id="recipe-2"),)
                    )
                )

            second = recipe(recipe_id="recipe-2")
            store.save(
                ResearchSecurityValidationRecipeDocument(recipes=(first, second))
            )
            self.assertEqual(store.load().recipes, (first, second))

    def test_unknown_fields_and_schema_versions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(
                json.dumps({"schema_version": 1, "recipes": [], "extra": True})
            )
            with self.assertRaises(ResearchError):
                JsonFileResearchSecurityValidationRecipeStore(path).load()
            path.write_text(json.dumps({"schema_version": 2, "recipes": []}))
            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchSecurityValidationRecipeStore(path).load()
            path.write_text(json.dumps({"schema_version": True, "recipes": []}))
            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchSecurityValidationRecipeStore(path).load()

    def test_malformed_subject_kind_in_persisted_content_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipes": [
                            {
                                "recipe_id": "recipe-1",
                                "program_id": "program-a",
                                "subject_kind": "not-a-real-kind",
                                "subject_id": "finding-1",
                                "steps": ["Step one"],
                                "notes": "",
                                "created_at": RECORDED.isoformat(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ResearchError, "subject kind"):
                JsonFileResearchSecurityValidationRecipeStore(path).load()

    def test_secret_shaped_persisted_notes_fail_closed_without_reflection(
        self,
    ) -> None:
        sentinel = "distinct-persisted-secret"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipes": [
                            {
                                "recipe_id": "recipe-1",
                                "program_id": "program-a",
                                "subject_kind": "finding",
                                "subject_id": "finding-1",
                                "steps": ["Step one"],
                                "notes": f"password={sentinel}",
                                "created_at": RECORDED.isoformat(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ResearchError) as raised:
                JsonFileResearchSecurityValidationRecipeStore(path).load()

            self.assertIn("refused as", str(raised.exception))
            self.assertNotIn(sentinel, str(raised.exception))

    def test_the_declared_ceilings_are_the_reviewed_values(self) -> None:
        from research.JsonFileResearchSecurityValidationRecipeStore import (
            MAX_SECURITY_VALIDATION_RECIPE_STORE_BYTES,
            MAX_SECURITY_VALIDATION_RECIPES,
        )

        self.assertEqual(MAX_SECURITY_VALIDATION_RECIPES, 5_000)
        self.assertEqual(MAX_SECURITY_VALIDATION_RECIPE_STORE_BYTES, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
