"""Pure derivation tests for `research.ResearchReproduction`.

`reproductions_for_recipe`/`reproductions_for_subject`/
`current_reproduction_for_recipe` are the only reads over persisted
`ResearchReproductionRecord`s; all three must be pure, dependency-free, and
ordered by persisted append order only, never by `recorded_at` (a wall-clock
regression must never reorder "current") -- the same discipline
`research.ResearchSecurityValidationRecipe` already follows.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from research.ResearchReproduction import (
    current_reproduction_for_recipe,
    reproductions_for_recipe,
    reproductions_for_subject,
)
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)
EARLIER = RECORDED - timedelta(hours=1)


def reproduction(
    *,
    reproduction_id: str,
    program_id: str = "program-a",
    recipe_id: str = "recipe-1",
    subject_kind: ResearchSecurityValidationRecipeSubjectKind = (
        ResearchSecurityValidationRecipeSubjectKind.FINDING
    ),
    subject_id: str = "finding-1",
    outcome: ResearchReproductionOutcome = ResearchReproductionOutcome.REPRODUCED,
    recorded_at: datetime = RECORDED,
) -> ResearchReproductionRecord:
    return ResearchReproductionRecord(
        reproduction_id=reproduction_id,
        program_id=program_id,
        recipe_id=recipe_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        outcome=outcome,
        notes="",
        evidence_ids=(),
        recorded_at=recorded_at,
    )


class ReproductionsForRecipeTests(unittest.TestCase):
    def test_empty_input_yields_empty_output(self) -> None:
        self.assertEqual(
            reproductions_for_recipe("program-a", "recipe-1", ()),
            (),
        )

    def test_filters_by_program_and_recipe_together(self) -> None:
        target = reproduction(reproduction_id="r1")
        other_program = reproduction(reproduction_id="r2", program_id="program-b")
        other_recipe = reproduction(reproduction_id="r3", recipe_id="recipe-2")

        result = reproductions_for_recipe(
            "program-a", "recipe-1", (target, other_program, other_recipe)
        )

        self.assertEqual(result, (target,))

    def test_preserves_persisted_append_order_not_recorded_at_order(self) -> None:
        # `second` is appended after `first` but carries an *earlier*
        # `recorded_at` -- a wall-clock regression must not reorder this.
        first = reproduction(reproduction_id="r1", recorded_at=RECORDED)
        second = reproduction(reproduction_id="r2", recorded_at=EARLIER)

        result = reproductions_for_recipe("program-a", "recipe-1", (first, second))

        self.assertEqual(result, (first, second))


class ReproductionsForSubjectTests(unittest.TestCase):
    def test_empty_input_yields_empty_output(self) -> None:
        self.assertEqual(
            reproductions_for_subject(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                "finding-1",
                (),
            ),
            (),
        )

    def test_gathers_every_recipe_naming_the_same_subject(self) -> None:
        first_recipe = reproduction(reproduction_id="r1", recipe_id="recipe-1")
        second_recipe = reproduction(reproduction_id="r2", recipe_id="recipe-2")
        other_subject = reproduction(
            reproduction_id="r3", recipe_id="recipe-3", subject_id="finding-2"
        )
        other_kind = reproduction(
            reproduction_id="r4",
            recipe_id="recipe-4",
            subject_kind=ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
            subject_id="finding-1",
        )
        other_program = reproduction(
            reproduction_id="r5", recipe_id="recipe-5", program_id="program-b"
        )

        result = reproductions_for_subject(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            "finding-1",
            (
                first_recipe,
                second_recipe,
                other_subject,
                other_kind,
                other_program,
            ),
        )

        self.assertEqual(result, (first_recipe, second_recipe))


class CurrentReproductionForRecipeTests(unittest.TestCase):
    def test_none_when_no_reproduction_is_recorded(self) -> None:
        self.assertIsNone(current_reproduction_for_recipe("program-a", "recipe-1", ()))

    def test_is_the_most_recently_appended_matching_reproduction(self) -> None:
        first = reproduction(reproduction_id="r1", recorded_at=RECORDED)
        second = reproduction(reproduction_id="r2", recorded_at=EARLIER)
        unrelated = reproduction(reproduction_id="r3", program_id="program-b")

        current = current_reproduction_for_recipe(
            "program-a", "recipe-1", (first, second, unrelated)
        )

        self.assertEqual(current, second)


if __name__ == "__main__":
    unittest.main()
