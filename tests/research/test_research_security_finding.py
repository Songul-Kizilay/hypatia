"""Security finding identity, status discipline, and derivation are honest.

`ResearchSecurityFindingRecord`/`EvidenceLinkRecord`/`StatusTransitionRecord`
are the only durable facts; `ResearchSecurityFinding`/`findings_for_program`
are a pure, always-recomputed read model over them. No status this vocabulary
can produce ever asserts a confirmed vulnerability, including `VALIDATED`.
"""

from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityFinding import (
    ResearchSecurityFinding,
    findings_for_program,
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
from research.ResearchSecurityFindingRecord import (
    MAX_SECURITY_FINDING_DESCRIPTION_CHARACTERS,
    MAX_SECURITY_FINDING_REQUIRED_FOLLOWUP_CHARACTERS,
    MAX_SECURITY_FINDING_TITLE_CHARACTERS,
    ResearchSecurityFindingRecord,
)
from research.ResearchSecurityFindingStatus import (
    ResearchSecurityFindingStatus,
    is_valid_status_transition,
)
from research.ResearchSecurityFindingStatusTransitionRecord import (
    MAX_SECURITY_FINDING_STATUS_TRANSITION_REASON_CHARACTERS,
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind

RECORDED = datetime(2026, 9, 26, 10, tzinfo=UTC)
LATER = datetime(2026, 9, 26, 11, tzinfo=UTC)


def finding_record(
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    source_hypothesis_id: str = "hypothesis-1",
    finding_kind: ResearchSecurityHypothesisKind = (
        ResearchSecurityHypothesisKind.AUTHORIZATION
    ),
    subject_kind: ResearchAssetKind = ResearchAssetKind.HOSTNAME,
    subject_value: str = "example.test",
    title: str = "Order endpoint exposes a sequential order ID.",
    description: str = "Observed HTTP evidence shows a numeric ID in the path.",
    required_followup: str = "Request the same order ID as a different account.",
    origin: ResearchSecurityFindingOrigin = (
        ResearchSecurityFindingOrigin.OPERATOR_AUTHORED
    ),
    created_at: datetime = RECORDED,
) -> ResearchSecurityFindingRecord:
    return ResearchSecurityFindingRecord(
        finding_id=finding_id,
        program_id=program_id,
        source_hypothesis_id=source_hypothesis_id,
        finding_kind=finding_kind,
        subject_kind=subject_kind,
        subject_canonical_value=canonicalize_asset_value(subject_kind, subject_value),
        title=title,
        description=description,
        required_followup=required_followup,
        origin=origin,
        created_at=created_at,
    )


def evidence_link(
    link_id: str = "link-1",
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    evidence_id: str = "a" * 64,
    relation: ResearchSecurityFindingEvidenceRelation = (
        ResearchSecurityFindingEvidenceRelation.SUPPORTS
    ),
    recorded_at: datetime = RECORDED,
) -> ResearchSecurityFindingEvidenceLinkRecord:
    return ResearchSecurityFindingEvidenceLinkRecord(
        link_id=link_id,
        finding_id=finding_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
        evidence_id=evidence_id,
        relation=relation,
        recorded_at=recorded_at,
    )


def status_transition(
    transition_id: str = "transition-1",
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    status: ResearchSecurityFindingStatus = (
        ResearchSecurityFindingStatus.VALIDATION_REQUIRED
    ),
    reason: str = "",
    duplicate_of_finding_id: str | None = None,
    superseded_by_finding_id: str | None = None,
    recorded_at: datetime = RECORDED,
) -> ResearchSecurityFindingStatusTransitionRecord:
    return ResearchSecurityFindingStatusTransitionRecord(
        transition_id=transition_id,
        finding_id=finding_id,
        program_id=program_id,
        status=status,
        reason=reason,
        duplicate_of_finding_id=duplicate_of_finding_id,
        superseded_by_finding_id=superseded_by_finding_id,
        recorded_at=recorded_at,
    )


class ResearchSecurityFindingRecordTests(unittest.TestCase):
    def test_valid_construction_round_trips(self) -> None:
        record = finding_record()
        self.assertEqual(record.subject_canonical_value, "example.test")
        self.assertEqual(record.origin, ResearchSecurityFindingOrigin.OPERATOR_AUTHORED)

    def test_record_is_frozen(self) -> None:
        record = finding_record()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.title = "changed"  # type: ignore[misc]

    def test_invalid_finding_kind_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            finding_record(finding_kind="authorization")  # type: ignore[arg-type]

    def test_invalid_subject_kind_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingRecord(
                finding_id="finding-1",
                program_id="program-a",
                source_hypothesis_id="hypothesis-1",
                finding_kind=ResearchSecurityHypothesisKind.UNKNOWN,
                subject_kind="hostname",  # type: ignore[arg-type]
                subject_canonical_value="example.test",
                title="title",
                description="description",
                required_followup="required followup",
                origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
                created_at=RECORDED,
            )

    def test_non_canonical_subject_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not canonical"):
            ResearchSecurityFindingRecord(
                finding_id="finding-1",
                program_id="program-a",
                source_hypothesis_id="hypothesis-1",
                finding_kind=ResearchSecurityHypothesisKind.UNKNOWN,
                subject_kind=ResearchAssetKind.HOSTNAME,
                subject_canonical_value="EXAMPLE.TEST.",
                title="title",
                description="description",
                required_followup="required followup",
                origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
                created_at=RECORDED,
            )

    def test_bounded_text_is_enforced_on_every_free_text_field(self) -> None:
        with self.assertRaises(ResearchError):
            finding_record(title="x" * (MAX_SECURITY_FINDING_TITLE_CHARACTERS + 1))
        with self.assertRaises(ResearchError):
            finding_record(
                description="x" * (MAX_SECURITY_FINDING_DESCRIPTION_CHARACTERS + 1)
            )
        with self.assertRaises(ResearchError):
            finding_record(
                required_followup=(
                    "x" * (MAX_SECURITY_FINDING_REQUIRED_FOLLOWUP_CHARACTERS + 1)
                )
            )

    def test_empty_required_free_text_field_is_rejected(self) -> None:
        for field in ("title", "description", "required_followup"):
            with self.subTest(field=field):
                with self.assertRaises(ResearchError):
                    finding_record(**{field: "   "})

    def test_naive_created_at_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            finding_record(created_at=datetime(2026, 9, 26, 10))


class SecurityFindingOriginAndEvidenceKindTests(unittest.TestCase):
    def test_origin_has_exactly_one_member(self) -> None:
        self.assertEqual(
            tuple(ResearchSecurityFindingOrigin),
            (ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,),
        )

    def test_evidence_kind_has_exactly_one_member(self) -> None:
        self.assertEqual(
            tuple(ResearchSecurityFindingEvidenceKind),
            (ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,),
        )

    def test_evidence_relation_has_exactly_three_members(self) -> None:
        self.assertEqual(
            tuple(ResearchSecurityFindingEvidenceRelation),
            (
                ResearchSecurityFindingEvidenceRelation.SUPPORTS,
                ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
                ResearchSecurityFindingEvidenceRelation.VALIDATES,
            ),
        )


class ResearchSecurityFindingEvidenceLinkRecordTests(unittest.TestCase):
    def test_valid_construction_round_trips(self) -> None:
        link = evidence_link()
        self.assertEqual(link.evidence_id, "a" * 64)
        self.assertIs(link.relation, ResearchSecurityFindingEvidenceRelation.SUPPORTS)

    def test_validates_relation_round_trips(self) -> None:
        link = evidence_link(relation=ResearchSecurityFindingEvidenceRelation.VALIDATES)
        self.assertIs(link.relation, ResearchSecurityFindingEvidenceRelation.VALIDATES)

    def test_malformed_http_evidence_id_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            evidence_link(evidence_id="not-a-real-evidence-id")

    def test_link_is_frozen(self) -> None:
        link = evidence_link()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            link.evidence_id = "b" * 64  # type: ignore[misc]


class ResearchSecurityFindingStatusTests(unittest.TestCase):
    def test_only_the_three_terminal_states_are_terminal(self) -> None:
        terminal = {
            ResearchSecurityFindingStatus.REFUTED,
            ResearchSecurityFindingStatus.DUPLICATE,
            ResearchSecurityFindingStatus.SUPERSEDED,
        }
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                self.assertEqual(status.terminal, status in terminal)

    def test_no_status_means_a_confirmed_vulnerability(self) -> None:
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                self.assertFalse(status.means_confirmed_vulnerability)

    def test_candidate_to_validation_required_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.CANDIDATE,
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            )
        )

    def test_candidate_to_validated_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.CANDIDATE,
                ResearchSecurityFindingStatus.VALIDATED,
            )
        )

    def test_candidate_to_refuted_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.CANDIDATE,
                ResearchSecurityFindingStatus.REFUTED,
            )
        )

    def test_candidate_to_duplicate_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.CANDIDATE,
                ResearchSecurityFindingStatus.DUPLICATE,
            )
        )

    def test_candidate_to_superseded_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.CANDIDATE,
                ResearchSecurityFindingStatus.SUPERSEDED,
            )
        )

    def test_validation_required_to_candidate_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
                ResearchSecurityFindingStatus.CANDIDATE,
            )
        )

    def test_validation_required_to_validated_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
                ResearchSecurityFindingStatus.VALIDATED,
            )
        )

    def test_validation_required_to_refuted_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
                ResearchSecurityFindingStatus.REFUTED,
            )
        )

    def test_validation_required_to_duplicate_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
                ResearchSecurityFindingStatus.DUPLICATE,
            )
        )

    def test_validation_required_to_superseded_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
                ResearchSecurityFindingStatus.SUPERSEDED,
            )
        )

    def test_validated_to_refuted_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATED,
                ResearchSecurityFindingStatus.REFUTED,
            )
        )

    def test_validated_to_duplicate_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATED,
                ResearchSecurityFindingStatus.DUPLICATE,
            )
        )

    def test_validated_to_superseded_is_valid(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATED,
                ResearchSecurityFindingStatus.SUPERSEDED,
            )
        )

    def test_validated_to_candidate_is_invalid(self) -> None:
        self.assertFalse(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATED,
                ResearchSecurityFindingStatus.CANDIDATE,
            )
        )

    def test_validated_to_validation_required_is_invalid(self) -> None:
        self.assertFalse(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.VALIDATED,
                ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            )
        )

    def test_every_self_transition_is_invalid(self) -> None:
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                self.assertFalse(is_valid_status_transition(status, status))

    def test_refuted_has_no_outgoing_transition(self) -> None:
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                self.assertFalse(
                    is_valid_status_transition(
                        ResearchSecurityFindingStatus.REFUTED, status
                    )
                )

    def test_duplicate_has_no_outgoing_transition(self) -> None:
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                self.assertFalse(
                    is_valid_status_transition(
                        ResearchSecurityFindingStatus.DUPLICATE, status
                    )
                )

    def test_superseded_has_no_outgoing_transition(self) -> None:
        for status in ResearchSecurityFindingStatus:
            with self.subTest(status=status):
                self.assertFalse(
                    is_valid_status_transition(
                        ResearchSecurityFindingStatus.SUPERSEDED, status
                    )
                )

    def test_invalid_type_arguments_return_false(self) -> None:
        refuted = ResearchSecurityFindingStatus.REFUTED
        self.assertFalse(is_valid_status_transition("candidate", refuted))  # type: ignore[arg-type]


class ResearchSecurityFindingStatusTransitionRecordTests(unittest.TestCase):
    def test_empty_reason_is_accepted(self) -> None:
        transition = status_transition(reason="")
        self.assertEqual(transition.reason, "")

    def test_reason_is_bounded_at_exactly_500_characters(self) -> None:
        self.assertEqual(MAX_SECURITY_FINDING_STATUS_TRANSITION_REASON_CHARACTERS, 500)
        at_limit = status_transition(reason="r" * 500)
        self.assertEqual(len(at_limit.reason), 500)
        with self.assertRaisesRegex(ResearchError, "too long"):
            status_transition(reason="r" * 501)

    def test_transition_is_frozen(self) -> None:
        transition = status_transition()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            transition.status = ResearchSecurityFindingStatus.REFUTED  # type: ignore[misc]

    def test_invalid_status_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(status="validation_required")  # type: ignore[arg-type]

    def test_duplicate_status_requires_duplicate_of_finding_id(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(status=ResearchSecurityFindingStatus.DUPLICATE)

    def test_duplicate_status_rejects_a_superseded_by_reference(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(
                status=ResearchSecurityFindingStatus.DUPLICATE,
                duplicate_of_finding_id="finding-2",
                superseded_by_finding_id="finding-3",
            )

    def test_duplicate_status_with_a_valid_reference_round_trips(self) -> None:
        transition = status_transition(
            status=ResearchSecurityFindingStatus.DUPLICATE,
            duplicate_of_finding_id="finding-2",
        )
        self.assertEqual(transition.duplicate_of_finding_id, "finding-2")
        self.assertIsNone(transition.superseded_by_finding_id)

    def test_superseded_status_requires_superseded_by_finding_id(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(status=ResearchSecurityFindingStatus.SUPERSEDED)

    def test_superseded_status_rejects_a_duplicate_of_reference(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(
                status=ResearchSecurityFindingStatus.SUPERSEDED,
                duplicate_of_finding_id="finding-2",
                superseded_by_finding_id="finding-3",
            )

    def test_superseded_status_with_a_valid_reference_round_trips(self) -> None:
        transition = status_transition(
            status=ResearchSecurityFindingStatus.SUPERSEDED,
            superseded_by_finding_id="finding-2",
        )
        self.assertEqual(transition.superseded_by_finding_id, "finding-2")
        self.assertIsNone(transition.duplicate_of_finding_id)

    def test_non_duplicate_non_superseded_status_rejects_duplicate_of(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(
                status=ResearchSecurityFindingStatus.CANDIDATE,
                duplicate_of_finding_id="finding-2",
            )

    def test_non_duplicate_non_superseded_status_rejects_superseded_by(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(
                status=ResearchSecurityFindingStatus.VALIDATED,
                superseded_by_finding_id="finding-2",
            )


class SecurityFindingSensitiveInputRefusalTests(unittest.TestCase):
    """Mirrors `SecurityHypothesisSensitiveInputRefusalTests`'s categories/near-miss."""

    SENTINEL = "distinct-finding-secret-sentinel"

    def _cases(self) -> dict[str, str]:
        sentinel = self.SENTINEL
        return {
            "credential_bearing_url": f"https://user:{sentinel}@example.test",
            "authentication_header": f"Authorization: Bearer {sentinel}",
            "private_key_material": "-----BEGIN PRIVATE KEY-----",
            "secret_assignment": f"password={sentinel}",
            "token_format": "sk-abcdefghijklmnopqrstuvwxyz123456",
        }

    def test_title_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    finding_record(title=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_description_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    finding_record(description=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_required_followup_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    finding_record(required_followup=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_status_transition_reason_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    status_transition(reason=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_benign_near_miss_still_constructs(self) -> None:
        benign = "No password was used and no token was recorded."
        self.assertEqual(finding_record(title=benign).title, benign)
        self.assertEqual(finding_record(description=benign).description, benign)
        self.assertEqual(status_transition(reason=benign).reason, benign)


class FindingsForProgramTests(unittest.TestCase):
    def test_derives_candidate_status_with_no_transitions(self) -> None:
        record = finding_record()
        link = evidence_link()
        (derived,) = findings_for_program("program-a", (record,), (link,), ())
        self.assertIs(derived.status, ResearchSecurityFindingStatus.CANDIDATE)
        self.assertEqual(derived.supporting_evidence, (link,))
        self.assertEqual(derived.contradicting_evidence, ())
        self.assertEqual(derived.validation_evidence, ())
        self.assertEqual(derived.status_history, ())

    def test_derives_latest_status_by_recorded_at(self) -> None:
        record = finding_record()
        earlier = status_transition(
            transition_id="t1",
            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            recorded_at=RECORDED,
        )
        later = status_transition(
            transition_id="t2",
            status=ResearchSecurityFindingStatus.REFUTED,
            recorded_at=LATER,
        )
        (derived,) = findings_for_program("program-a", (record,), (), (earlier, later))
        self.assertIs(derived.status, ResearchSecurityFindingStatus.REFUTED)
        self.assertEqual(derived.status_history, (earlier, later))

    def test_ties_broken_by_transition_id(self) -> None:
        record = finding_record()
        first = status_transition(
            transition_id="a-transition",
            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            recorded_at=RECORDED,
        )
        second = status_transition(
            transition_id="b-transition",
            status=ResearchSecurityFindingStatus.REFUTED,
            recorded_at=RECORDED,
        )
        (derived,) = findings_for_program("program-a", (record,), (), (first, second))
        self.assertIs(derived.status, ResearchSecurityFindingStatus.REFUTED)

    def test_three_way_evidence_split_is_preserved(self) -> None:
        record = finding_record()
        supporting = evidence_link(link_id="link-1", evidence_id="a" * 64)
        contradicting = evidence_link(
            link_id="link-2",
            evidence_id="b" * 64,
            relation=ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
        )
        validating = evidence_link(
            link_id="link-3",
            evidence_id="c" * 64,
            relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
        )
        (derived,) = findings_for_program(
            "program-a", (record,), (supporting, contradicting, validating), ()
        )
        self.assertEqual(derived.supporting_evidence, (supporting,))
        self.assertEqual(derived.contradicting_evidence, (contradicting,))
        self.assertEqual(derived.validation_evidence, (validating,))

    def test_other_program_is_excluded(self) -> None:
        record = finding_record(finding_id="finding-1", program_id="program-a")
        self.assertEqual(findings_for_program("program-b", (record,), (), ()), ())

    def test_derived_model_is_frozen_and_validates_identity(self) -> None:
        record = finding_record()
        derived = findings_for_program("program-a", (record,), (), ())[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            derived.status = ResearchSecurityFindingStatus.REFUTED  # type: ignore[misc]
        foreign_link = evidence_link(finding_id="other-finding")
        with self.assertRaises(ResearchError):
            ResearchSecurityFinding(
                finding_id=record.finding_id,
                program_id=record.program_id,
                source_hypothesis_id=record.source_hypothesis_id,
                finding_kind=record.finding_kind,
                subject_kind=record.subject_kind,
                subject_canonical_value=record.subject_canonical_value,
                title=record.title,
                description=record.description,
                required_followup=record.required_followup,
                origin=record.origin,
                created_at=record.created_at,
                supporting_evidence=(foreign_link,),
                contradicting_evidence=(),
                validation_evidence=(),
                status=ResearchSecurityFindingStatus.CANDIDATE,
                status_history=(),
            )


if __name__ == "__main__":
    unittest.main()
