"""Pure derivation tests for `ResearchSecurityValidationRecipe`.

`validation_recipes_for`/`current_validation_recipe_for` are the only two
reads over persisted `ResearchSecurityValidationRecipeRecord`s; both must be
pure, dependency-free, and ordered by persisted append order only, never by
`created_at` (a wall-clock regression must never reorder "current").
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from research.ResearchSecurityValidationRecipe import (
    current_validation_recipe_for,
    validation_recipes_for,
)
from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)
EARLIER = RECORDED - timedelta(hours=1)


def recipe(
    *,
    recipe_id: str,
    program_id: str = "program-a",
    subject_kind: ResearchSecurityValidationRecipeSubjectKind = (
        ResearchSecurityValidationRecipeSubjectKind.FINDING
    ),
    subject_id: str = "finding-1",
    created_at: datetime = RECORDED,
) -> ResearchSecurityValidationRecipeRecord:
    return ResearchSecurityValidationRecipeRecord(
        recipe_id=recipe_id,
        program_id=program_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        steps=("Step one",),
        notes="",
        created_at=created_at,
    )


class ValidationRecipesForTests(unittest.TestCase):
    def test_empty_input_yields_empty_output(self) -> None:
        self.assertEqual(
            validation_recipes_for(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                "finding-1",
                (),
            ),
            (),
        )

    def test_filters_by_program_subject_kind_and_subject_id_together(self) -> None:
        target = recipe(recipe_id="r1")
        other_program = recipe(recipe_id="r2", program_id="program-b")
        other_subject = recipe(recipe_id="r3", subject_id="finding-2")
        other_kind = recipe(
            recipe_id="r4",
            subject_kind=ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
            subject_id="finding-1",
        )

        result = validation_recipes_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            "finding-1",
            (target, other_program, other_subject, other_kind),
        )

        self.assertEqual(result, (target,))

    def test_preserves_persisted_append_order_not_created_at_order(self) -> None:
        # `second` is appended after `first` but carries an *earlier*
        # `created_at` — a wall-clock regression must not reorder this.
        first = recipe(recipe_id="r1", created_at=RECORDED)
        second = recipe(recipe_id="r2", created_at=EARLIER)

        result = validation_recipes_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            "finding-1",
            (first, second),
        )

        self.assertEqual(result, (first, second))


class CurrentValidationRecipeForTests(unittest.TestCase):
    def test_none_when_no_recipe_is_recorded(self) -> None:
        self.assertIsNone(
            current_validation_recipe_for(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                "finding-1",
                (),
            )
        )

    def test_is_the_most_recently_appended_matching_recipe(self) -> None:
        first = recipe(recipe_id="r1", created_at=RECORDED)
        second = recipe(recipe_id="r2", created_at=EARLIER)
        unrelated = recipe(recipe_id="r3", program_id="program-b")

        current = current_validation_recipe_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            "finding-1",
            (first, second, unrelated),
        )

        self.assertEqual(current, second)


if __name__ == "__main__":
    unittest.main()
