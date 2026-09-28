"""Validation tests for `ResearchSecurityValidationRecipeRecord`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchSecurityValidationRecipeRecord import (
    MAX_SECURITY_VALIDATION_RECIPE_NOTES_CHARACTERS,
    MAX_SECURITY_VALIDATION_RECIPE_STEP_CHARACTERS,
    MAX_SECURITY_VALIDATION_RECIPE_STEPS,
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)


def recipe(
    *,
    recipe_id: str = "recipe-1",
    program_id: str = "program-a",
    subject_kind: ResearchSecurityValidationRecipeSubjectKind = (
        ResearchSecurityValidationRecipeSubjectKind.FINDING
    ),
    subject_id: str = "finding-1",
    steps: tuple[str, ...] = ("Step one", "Step two"),
    notes: str = "notes",
) -> ResearchSecurityValidationRecipeRecord:
    return ResearchSecurityValidationRecipeRecord(
        recipe_id=recipe_id,
        program_id=program_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        steps=steps,
        notes=notes,
        created_at=RECORDED,
    )


class ResearchSecurityValidationRecipeRecordTests(unittest.TestCase):
    def test_a_valid_recipe_round_trips_its_fields(self) -> None:
        value = recipe()

        self.assertEqual(value.recipe_id, "recipe-1")
        self.assertEqual(value.program_id, "program-a")
        self.assertIs(
            value.subject_kind, ResearchSecurityValidationRecipeSubjectKind.FINDING
        )
        self.assertEqual(value.subject_id, "finding-1")
        self.assertEqual(value.steps, ("Step one", "Step two"))
        self.assertEqual(value.notes, "notes")

    def test_empty_notes_are_allowed(self) -> None:
        value = recipe(notes="")

        self.assertEqual(value.notes, "")

    def test_recipe_id_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            recipe(recipe_id="   ")

    def test_program_id_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            recipe(program_id="")

    def test_subject_id_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            recipe(subject_id="")

    def test_program_id_must_be_single_line(self) -> None:
        with self.assertRaisesRegex(ResearchError, "single-line"):
            recipe(program_id="program-a\nprogram-b")

    def test_subject_kind_must_be_a_real_member(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityValidationRecipeRecord(
                recipe_id="recipe-1",
                program_id="program-a",
                subject_kind="finding",  # type: ignore[arg-type]
                subject_id="finding-1",
                steps=("Step one",),
                notes="",
                created_at=RECORDED,
            )

    def test_steps_cannot_be_empty(self) -> None:
        with self.assertRaisesRegex(ResearchError, "at least one step"):
            recipe(steps=())

    def test_steps_must_be_a_tuple(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityValidationRecipeRecord(
                recipe_id="recipe-1",
                program_id="program-a",
                subject_kind=ResearchSecurityValidationRecipeSubjectKind.FINDING,
                subject_id="finding-1",
                steps=["Step one"],  # type: ignore[arg-type]
                notes="",
                created_at=RECORDED,
            )

    def test_too_many_steps_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "too many steps"):
            recipe(
                steps=tuple(
                    f"step {index}"
                    for index in range(MAX_SECURITY_VALIDATION_RECIPE_STEPS + 1)
                )
            )

    def test_a_step_at_the_character_ceiling_is_accepted(self) -> None:
        value = recipe(steps=("a" * MAX_SECURITY_VALIDATION_RECIPE_STEP_CHARACTERS,))

        self.assertEqual(
            len(value.steps[0]), MAX_SECURITY_VALIDATION_RECIPE_STEP_CHARACTERS
        )

    def test_a_step_over_the_character_ceiling_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            recipe(steps=("a" * (MAX_SECURITY_VALIDATION_RECIPE_STEP_CHARACTERS + 1),))

    def test_a_step_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            recipe(steps=("Step one", "   "))

    def test_a_step_must_be_single_line(self) -> None:
        with self.assertRaisesRegex(ResearchError, "single-line"):
            recipe(steps=("Step one\nStep two",))

    def test_a_secret_shaped_step_is_refused(self) -> None:
        with self.assertRaisesRegex(ResearchError, "refused as"):
            recipe(steps=("api_key: sk-not-a-real-secret-1234567890",))

    def test_notes_over_the_character_ceiling_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            recipe(notes="a" * (MAX_SECURITY_VALIDATION_RECIPE_NOTES_CHARACTERS + 1))

    def test_secret_shaped_notes_are_refused(self) -> None:
        with self.assertRaisesRegex(ResearchError, "refused as"):
            recipe(notes="password=not-a-real-secret-1234567890")

    def test_created_at_must_be_timezone_aware(self) -> None:
        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            recipe_with_naive_time = ResearchSecurityValidationRecipeRecord(
                recipe_id="recipe-1",
                program_id="program-a",
                subject_kind=ResearchSecurityValidationRecipeSubjectKind.FINDING,
                subject_id="finding-1",
                steps=("Step one",),
                notes="",
                created_at=datetime(2026, 9, 28, 12),
            )
            del recipe_with_naive_time


if __name__ == "__main__":
    unittest.main()
