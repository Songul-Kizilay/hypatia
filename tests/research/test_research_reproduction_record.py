"""Validation tests for `ResearchReproductionRecord` and its outcome enum."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchReproductionRecord import (
    MAX_REPRODUCTION_EVIDENCE_IDS,
    MAX_REPRODUCTION_NOTES_CHARACTERS,
    ResearchReproductionRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 28, 12, tzinfo=UTC)


def reproduction(
    *,
    reproduction_id: str = "reproduction-1",
    program_id: str = "program-a",
    recipe_id: str = "recipe-1",
    subject_kind: ResearchSecurityValidationRecipeSubjectKind = (
        ResearchSecurityValidationRecipeSubjectKind.FINDING
    ),
    subject_id: str = "finding-1",
    outcome: ResearchReproductionOutcome = ResearchReproductionOutcome.REPRODUCED,
    notes: str = "notes",
    evidence_ids: tuple[str, ...] = ("a" * 64,),
) -> ResearchReproductionRecord:
    return ResearchReproductionRecord(
        reproduction_id=reproduction_id,
        program_id=program_id,
        recipe_id=recipe_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        outcome=outcome,
        notes=notes,
        evidence_ids=evidence_ids,
        recorded_at=RECORDED,
    )


class ResearchReproductionOutcomeTests(unittest.TestCase):
    def test_no_outcome_means_a_confirmed_vulnerability(self) -> None:
        for outcome in ResearchReproductionOutcome:
            with self.subTest(outcome=outcome):
                self.assertFalse(outcome.means_confirmed_vulnerability)

    def test_the_four_expected_members_exist_and_nothing_else_overclaims(self) -> None:
        values = {member.value for member in ResearchReproductionOutcome}
        self.assertEqual(
            values, {"not_run", "reproduced", "not_reproduced", "inconclusive"}
        )
        for forbidden in ("exploited", "owned", "confirmed", "validated"):
            self.assertNotIn(forbidden, values)


class ResearchReproductionRecordTests(unittest.TestCase):
    def test_a_valid_reproduction_round_trips_its_fields(self) -> None:
        value = reproduction()

        self.assertEqual(value.reproduction_id, "reproduction-1")
        self.assertEqual(value.recipe_id, "recipe-1")
        self.assertIs(
            value.subject_kind, ResearchSecurityValidationRecipeSubjectKind.FINDING
        )
        self.assertIs(value.outcome, ResearchReproductionOutcome.REPRODUCED)
        self.assertEqual(value.evidence_ids, ("a" * 64,))

    def test_empty_notes_are_allowed(self) -> None:
        value = reproduction(notes="")

        self.assertEqual(value.notes, "")

    def test_empty_evidence_ids_are_allowed(self) -> None:
        value = reproduction(evidence_ids=())

        self.assertEqual(value.evidence_ids, ())

    def test_reproduction_id_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            reproduction(reproduction_id="  ")

    def test_recipe_id_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            reproduction(recipe_id="")

    def test_subject_kind_must_be_a_real_member(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchReproductionRecord(
                reproduction_id="reproduction-1",
                program_id="program-a",
                recipe_id="recipe-1",
                subject_kind="finding",  # type: ignore[arg-type]
                subject_id="finding-1",
                outcome=ResearchReproductionOutcome.REPRODUCED,
                notes="",
                evidence_ids=(),
                recorded_at=RECORDED,
            )

    def test_outcome_must_be_a_real_member(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchReproductionRecord(
                reproduction_id="reproduction-1",
                program_id="program-a",
                recipe_id="recipe-1",
                subject_kind=ResearchSecurityValidationRecipeSubjectKind.FINDING,
                subject_id="finding-1",
                outcome="reproduced",  # type: ignore[arg-type]
                notes="",
                evidence_ids=(),
                recorded_at=RECORDED,
            )

    def test_notes_over_the_character_ceiling_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            reproduction(notes="a" * (MAX_REPRODUCTION_NOTES_CHARACTERS + 1))

    def test_secret_shaped_notes_are_refused(self) -> None:
        with self.assertRaisesRegex(ResearchError, "refused as"):
            reproduction(notes="password=not-a-real-secret-1234567890")

    def test_too_many_evidence_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "too many"):
            reproduction(
                evidence_ids=tuple(
                    f"{index:064d}"
                    for index in range(MAX_REPRODUCTION_EVIDENCE_IDS + 1)
                )
            )

    def test_a_duplicate_evidence_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "duplicate evidence ID"):
            reproduction(evidence_ids=("a" * 64, "a" * 64))

    def test_an_evidence_id_cannot_be_empty(self) -> None:
        with self.assertRaises(ResearchError):
            reproduction(evidence_ids=("a" * 64, "   "))

    def test_recorded_at_must_be_timezone_aware(self) -> None:
        with self.assertRaisesRegex(ResearchError, "timezone-aware"):
            ResearchReproductionRecord(
                reproduction_id="reproduction-1",
                program_id="program-a",
                recipe_id="recipe-1",
                subject_kind=ResearchSecurityValidationRecipeSubjectKind.FINDING,
                subject_id="finding-1",
                outcome=ResearchReproductionOutcome.REPRODUCED,
                notes="",
                evidence_ids=(),
                recorded_at=datetime(2026, 9, 28, 12),
            )


if __name__ == "__main__":
    unittest.main()
