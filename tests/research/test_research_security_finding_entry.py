"""v0.3.427: `ResearchSecurityFindingEntry.reproductions` is purely additive,
live-recomputed display data -- fail-closed identical to how every other
foreign-keyed field in this codebase is validated against its owner's own
identity (finding_id/program_id), and `with_reproductions` never mutates the
original entry.
"""

from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityFindingEntry import ResearchSecurityFindingEntry
from research.ResearchSecurityFindingEvidenceCeiling import (
    ResearchSecurityFindingEvidenceCeiling,
)
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

RECORDED = datetime(2026, 9, 29, 10, tzinfo=UTC)

NO_SCOPE = ResearchAssetScopeResolutionView(
    has_active_scope_revision=False, resolution=None
)


def _finding(
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    validation_evidence: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...] = (),
) -> ResearchSecurityFinding:
    return ResearchSecurityFinding(
        finding_id=finding_id,
        program_id=program_id,
        source_hypothesis_id="hypothesis-1",
        finding_kind=ResearchSecurityHypothesisKind.AUTHORIZATION,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=canonicalize_asset_value(
            ResearchAssetKind.HOSTNAME, "example.test"
        ),
        title="title",
        description="description",
        required_followup="required followup",
        origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
        supporting_evidence=(),
        contradicting_evidence=(),
        validation_evidence=validation_evidence,
        status=ResearchSecurityFindingStatus.CANDIDATE,
        status_history=(),
    )


def _validates_link(
    finding_id: str = "finding-1", program_id: str = "program-a"
) -> ResearchSecurityFindingEvidenceLinkRecord:
    return ResearchSecurityFindingEvidenceLinkRecord(
        link_id="validates-1",
        finding_id=finding_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
        evidence_id="a" * 64,
        relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
        recorded_at=RECORDED,
    )


def _reproduction(
    *,
    reproduction_id: str = "reproduction-1",
    program_id: str = "program-a",
    recipe_id: str = "recipe-1",
    subject_kind: ResearchSecurityValidationRecipeSubjectKind = (
        ResearchSecurityValidationRecipeSubjectKind.FINDING
    ),
    subject_id: str = "finding-1",
    outcome: ResearchReproductionOutcome = ResearchReproductionOutcome.REPRODUCED,
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
        recorded_at=RECORDED,
    )


class ConstructionTests(unittest.TestCase):
    def test_no_reproductions_is_the_default(self) -> None:
        entry = ResearchSecurityFindingEntry(finding=_finding(), scope=NO_SCOPE)
        self.assertEqual(entry.reproductions, ())

    def test_a_matching_reproduction_is_accepted(self) -> None:
        reproduction = _reproduction()
        entry = ResearchSecurityFindingEntry(
            finding=_finding(), scope=NO_SCOPE, reproductions=(reproduction,)
        )
        self.assertEqual(entry.reproductions, (reproduction,))

    def test_multiple_matching_reproductions_are_accepted_in_given_order(self) -> None:
        first = _reproduction(reproduction_id="r1")
        second = _reproduction(reproduction_id="r2")
        entry = ResearchSecurityFindingEntry(
            finding=_finding(), scope=NO_SCOPE, reproductions=(first, second)
        )
        self.assertEqual(entry.reproductions, (first, second))

    def test_reproductions_must_be_a_tuple(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingEntry(
                finding=_finding(),
                scope=NO_SCOPE,
                reproductions=[_reproduction()],  # type: ignore[arg-type]
            )

    def test_a_reproduction_for_a_different_finding_id_is_rejected(self) -> None:
        mismatched = _reproduction(subject_id="finding-2")
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingEntry(
                finding=_finding(finding_id="finding-1"),
                scope=NO_SCOPE,
                reproductions=(mismatched,),
            )

    def test_a_reproduction_for_a_different_program_is_rejected(self) -> None:
        """Program isolation, enforced by construction: even a reproduction
        that happens to name the same `subject_id` string in a different
        program can never attach to this entry."""
        mismatched = _reproduction(program_id="program-b")
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingEntry(
                finding=_finding(program_id="program-a"),
                scope=NO_SCOPE,
                reproductions=(mismatched,),
            )

    def test_a_reproduction_whose_subject_is_a_hypothesis_is_rejected(self) -> None:
        """A recipe recorded against the source hypothesis, not the finding
        itself, must never leak into the finding's own reproduction view --
        `subject_kind` disambiguates identically-valued IDs across kinds."""
        hypothesis_subject = _reproduction(
            subject_kind=ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
            subject_id="finding-1",
        )
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingEntry(
                finding=_finding(finding_id="finding-1"),
                scope=NO_SCOPE,
                reproductions=(hypothesis_subject,),
            )


class WithReproductionsTests(unittest.TestCase):
    def test_returns_a_new_entry_carrying_the_given_history(self) -> None:
        original = ResearchSecurityFindingEntry(finding=_finding(), scope=NO_SCOPE)
        reproduction = _reproduction()

        updated = original.with_reproductions((reproduction,))

        self.assertEqual(updated.reproductions, (reproduction,))
        self.assertIs(updated.finding, original.finding)
        self.assertIs(updated.scope, original.scope)

    def test_the_original_entry_is_not_mutated(self) -> None:
        original = ResearchSecurityFindingEntry(finding=_finding(), scope=NO_SCOPE)

        original.with_reproductions((_reproduction(),))

        self.assertEqual(original.reproductions, ())

    def test_the_result_is_still_frozen(self) -> None:
        updated = ResearchSecurityFindingEntry(
            finding=_finding(), scope=NO_SCOPE
        ).with_reproductions((_reproduction(),))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            updated.reproductions = ()  # type: ignore[misc]

    def test_attaching_a_mismatched_reproduction_still_fails_closed(self) -> None:
        original = ResearchSecurityFindingEntry(
            finding=_finding(finding_id="finding-1"), scope=NO_SCOPE
        )
        with self.assertRaises(ResearchError):
            original.with_reproductions((_reproduction(subject_id="finding-2"),))


class ReproductionDoesNotAffectEvidenceCeilingTests(unittest.TestCase):
    """v0.3.428: `evidence_ceiling` is computed exclusively from
    `ResearchSecurityFinding`'s own evidence tuples -- it does not read
    `ResearchSecurityFindingEntry.reproductions` at all, for any outcome."""

    def test_no_reproduction_history_leaves_the_ceiling_unchanged(self) -> None:
        entry = ResearchSecurityFindingEntry(finding=_finding(), scope=NO_SCOPE)
        with_history = entry.with_reproductions((_reproduction(),))
        self.assertIs(
            entry.finding.evidence_ceiling, with_history.finding.evidence_ceiling
        )

    def test_every_reproduction_outcome_leaves_the_ceiling_unchanged(self) -> None:
        baseline = ResearchSecurityFindingEntry(
            finding=_finding(), scope=NO_SCOPE
        ).finding.evidence_ceiling
        for outcome in ResearchReproductionOutcome:
            with self.subTest(outcome=outcome):
                entry = ResearchSecurityFindingEntry(
                    finding=_finding(), scope=NO_SCOPE
                ).with_reproductions((_reproduction(outcome=outcome),))
                self.assertIs(entry.finding.evidence_ceiling, baseline)

    def test_every_reproduction_outcome_leaves_a_non_unassessed_ceiling_unchanged(
        self,
    ) -> None:
        """A non-trivial baseline: `MEDIUM`, not `UNASSESSED`, so this
        proves REPRODUCED cannot raise it and no outcome can lower it
        either -- not just that a floor stays a floor."""
        medium_finding = _finding(validation_evidence=(_validates_link(),))
        baseline = medium_finding.evidence_ceiling
        self.assertIs(baseline, ResearchSecurityFindingEvidenceCeiling.MEDIUM)
        for outcome in ResearchReproductionOutcome:
            with self.subTest(outcome=outcome):
                entry = ResearchSecurityFindingEntry(
                    finding=medium_finding, scope=NO_SCOPE
                ).with_reproductions((_reproduction(outcome=outcome),))
                self.assertIs(entry.finding.evidence_ceiling, baseline)


if __name__ == "__main__":
    unittest.main()
