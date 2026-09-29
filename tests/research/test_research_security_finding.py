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

    def test_derives_latest_status_by_append_order(self) -> None:
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

    def test_a_backward_clock_step_does_not_hide_the_true_latest_transition(
        self,
    ) -> None:
        """F3: append order must win even when `recorded_at` regresses.

        `appended_second` is appended AFTER `appended_first` (its true,
        causal position) but carries an earlier wall-clock `recorded_at` —
        simulating a clock stepped backwards between the two writes. The
        derived status must still reflect the causally-latest transition.
        """
        record = finding_record()
        appended_first = status_transition(
            transition_id="t1",
            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            recorded_at=LATER,
        )
        appended_second = status_transition(
            transition_id="t2",
            status=ResearchSecurityFindingStatus.REFUTED,
            recorded_at=RECORDED,
        )
        (derived,) = findings_for_program(
            "program-a", (record,), (), (appended_first, appended_second)
        )
        self.assertIs(derived.status, ResearchSecurityFindingStatus.REFUTED)

    def test_append_order_wins_over_transition_id_at_the_same_instant(self) -> None:
        """Two same-`recorded_at` transitions must order by append position,
        never by a coincidental string comparison of `transition_id` (a
        random UUID in production, carrying no ordering meaning)."""
        record = finding_record()
        appended_first = status_transition(
            transition_id="z-transition",
            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            recorded_at=RECORDED,
        )
        appended_second = status_transition(
            transition_id="a-transition",
            status=ResearchSecurityFindingStatus.REFUTED,
            recorded_at=RECORDED,
        )
        (derived,) = findings_for_program(
            "program-a", (record,), (), (appended_first, appended_second)
        )
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


class NeedsAttentionTests(unittest.TestCase):
    """`needs_attention` is a current-state-only read: `VALIDATED` plus a
    currently-recorded `CONTRADICTS` link, nothing about which was recorded
    first (see the `ResearchSecurityFinding` docstring's `needs_attention`
    paragraph)."""

    def _derive(
        self,
        status_value: ResearchSecurityFindingStatus | None,
        contradicting_count: int,
        *,
        with_validates: bool = False,
        duplicate_of_finding_id: str | None = None,
        superseded_by_finding_id: str | None = None,
    ) -> ResearchSecurityFinding:
        record = finding_record()
        links = tuple(
            evidence_link(
                link_id=f"contradicts-{index}",
                evidence_id=chr(ord("b") + index) * 64,
                relation=ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
            )
            for index in range(contradicting_count)
        )
        if with_validates:
            links = (
                evidence_link(
                    link_id="validates-1",
                    evidence_id="9" * 64,
                    relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
                ),
                *links,
            )
        transitions: tuple[ResearchSecurityFindingStatusTransitionRecord, ...] = ()
        if status_value is not None:
            transitions = (
                status_transition(
                    status=status_value,
                    duplicate_of_finding_id=duplicate_of_finding_id,
                    superseded_by_finding_id=superseded_by_finding_id,
                ),
            )
        (derived,) = findings_for_program("program-a", (record,), links, transitions)
        return derived

    def test_validated_with_zero_contradicts_has_no_attention(self) -> None:
        derived = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 0, with_validates=True
        )
        self.assertFalse(derived.needs_attention)

    def test_validated_with_one_contradicts_needs_attention(self) -> None:
        derived = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 1, with_validates=True
        )
        self.assertTrue(derived.needs_attention)

    def test_validated_with_multiple_contradicts_needs_attention(self) -> None:
        derived = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 3, with_validates=True
        )
        self.assertTrue(derived.needs_attention)
        self.assertEqual(len(derived.contradicting_evidence), 3)

    def test_validated_with_validates_and_contradicts_needs_attention(self) -> None:
        """The `VALIDATES` link that gated the transition stays on record
        alongside the later `CONTRADICTS` link; both are counted, neither
        nets the other out."""
        derived = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 1, with_validates=True
        )
        self.assertTrue(derived.needs_attention)
        self.assertEqual(len(derived.validation_evidence), 1)
        self.assertEqual(len(derived.contradicting_evidence), 1)

    def test_candidate_with_contradicts_has_no_attention(self) -> None:
        derived = self._derive(None, 1)
        self.assertIs(derived.status, ResearchSecurityFindingStatus.CANDIDATE)
        self.assertFalse(derived.needs_attention)

    def test_validation_required_with_contradicts_has_no_attention(self) -> None:
        derived = self._derive(ResearchSecurityFindingStatus.VALIDATION_REQUIRED, 1)
        self.assertFalse(derived.needs_attention)

    def test_refuted_with_contradicts_has_no_attention(self) -> None:
        derived = self._derive(ResearchSecurityFindingStatus.REFUTED, 1)
        self.assertFalse(derived.needs_attention)

    def test_duplicate_with_contradicts_has_no_attention(self) -> None:
        derived = self._derive(
            ResearchSecurityFindingStatus.DUPLICATE,
            1,
            duplicate_of_finding_id="finding-2",
        )
        self.assertFalse(derived.needs_attention)

    def test_superseded_with_contradicts_has_no_attention(self) -> None:
        derived = self._derive(
            ResearchSecurityFindingStatus.SUPERSEDED,
            1,
            superseded_by_finding_id="finding-2",
        )
        self.assertFalse(derived.needs_attention)

    def test_recomputing_from_the_same_persisted_logs_is_deterministic(self) -> None:
        """Stands in for reload/restart: `findings_for_program` is pure, so
        calling it twice on byte-identical input must agree on
        `needs_attention` exactly as it already must agree on every other
        derived field -- restart can never fabricate a fresher answer than
        the persisted logs support."""
        record = finding_record()
        contradicting = evidence_link(
            link_id="c1",
            evidence_id="b" * 64,
            relation=ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
        )
        transition = status_transition(status=ResearchSecurityFindingStatus.VALIDATED)
        first = findings_for_program(
            "program-a", (record,), (contradicting,), (transition,)
        )
        second = findings_for_program(
            "program-a", (record,), (contradicting,), (transition,)
        )
        self.assertEqual(first, second)
        self.assertTrue(first[0].needs_attention)
        self.assertTrue(second[0].needs_attention)

    def test_reading_the_property_mutates_nothing(self) -> None:
        derived = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 1, with_validates=True
        )
        status_before = derived.status
        contradicting_before = derived.contradicting_evidence
        history_before = derived.status_history

        for _ in range(3):
            self.assertTrue(derived.needs_attention)

        self.assertIs(derived.status, status_before)
        self.assertEqual(derived.contradicting_evidence, contradicting_before)
        self.assertEqual(derived.status_history, history_before)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            derived.status = ResearchSecurityFindingStatus.REFUTED  # type: ignore[misc]

    def test_attention_requires_both_validated_status_and_contradiction_together(
        self,
    ) -> None:
        """Mutation-equivalent guard, without monkeypatching a property: a
        status-only implementation (`status is VALIDATED`, ignoring evidence)
        would wrongly return `True` for the second case below; a
        contradiction-only implementation (`len(contradicting) > 0`, ignoring
        status) would wrongly return `True` for the third. Only the real,
        both-conditions implementation gets all three right."""
        validated_with_contradiction = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 1, with_validates=True
        )
        validated_without_contradiction = self._derive(
            ResearchSecurityFindingStatus.VALIDATED, 0, with_validates=True
        )
        refuted_with_contradiction = self._derive(
            ResearchSecurityFindingStatus.REFUTED, 1
        )
        self.assertTrue(validated_with_contradiction.needs_attention)
        self.assertFalse(validated_without_contradiction.needs_attention)
        self.assertFalse(refuted_with_contradiction.needs_attention)


class EvidenceCeilingTests(unittest.TestCase):
    """`evidence_ceiling` is a current-state-only, presence-based read over
    the same three evidence tuples `needs_attention` already reads, plus
    `status`. See the property's own docstring for the exact rule."""

    def _derive(
        self,
        *,
        status_value: ResearchSecurityFindingStatus | None = None,
        supports_count: int = 0,
        contradicts_count: int = 0,
        validates_count: int = 0,
        title: str = "title",
        description: str = "description",
        required_followup: str = "required followup",
        duplicate_of_finding_id: str | None = None,
        superseded_by_finding_id: str | None = None,
    ) -> ResearchSecurityFinding:
        record = finding_record(
            title=title,
            description=description,
            required_followup=required_followup,
        )
        links: list[ResearchSecurityFindingEvidenceLinkRecord] = []
        # sha256-hex-shaped evidence IDs only (0-9a-f); each group draws from
        # its own slice of the hex alphabet so no two groups can collide.
        for index in range(supports_count):
            links.append(
                evidence_link(
                    link_id=f"supports-{index}",
                    evidence_id="0123456789ab"[index] * 64,
                    relation=ResearchSecurityFindingEvidenceRelation.SUPPORTS,
                )
            )
        for index in range(contradicts_count):
            links.append(
                evidence_link(
                    link_id=f"contradicts-{index}",
                    evidence_id="c" * 64 if index == 0 else f"c{index}".ljust(64, "0"),
                    relation=ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
                )
            )
        for index in range(validates_count):
            links.append(
                evidence_link(
                    link_id=f"validates-{index}",
                    evidence_id="d" * 64 if index == 0 else f"d{index}".ljust(64, "0"),
                    relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
                )
            )
        transitions: tuple[ResearchSecurityFindingStatusTransitionRecord, ...] = ()
        if status_value is not None:
            transitions = (
                status_transition(
                    status=status_value,
                    duplicate_of_finding_id=duplicate_of_finding_id,
                    superseded_by_finding_id=superseded_by_finding_id,
                ),
            )
        (derived,) = findings_for_program(
            "program-a", (record,), tuple(links), transitions
        )
        return derived

    # -- required scenarios 1-9: evidence combinations ------------------------

    def test_no_evidence_is_unassessed(self) -> None:
        self.assertIs(
            self._derive().evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )

    def test_supports_only_is_low(self) -> None:
        self.assertIs(
            self._derive(supports_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.LOW,
        )

    def test_multiple_supports_is_still_low_never_higher(self) -> None:
        """Independence is never inferred from quantity: three `SUPPORTS`
        links reach the identical ceiling as one."""
        self.assertIs(
            self._derive(supports_count=3).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.LOW,
        )

    def test_validates_only_is_medium(self) -> None:
        self.assertIs(
            self._derive(validates_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.MEDIUM,
        )

    def test_supports_and_validates_is_medium(self) -> None:
        """`VALIDATES` dominates `SUPPORTS`, never summed with it."""
        self.assertIs(
            self._derive(supports_count=1, validates_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.MEDIUM,
        )

    def test_contradicts_only_is_unassessed(self) -> None:
        self.assertIs(
            self._derive(contradicts_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )

    def test_supports_and_contradicts_is_unassessed(self) -> None:
        self.assertIs(
            self._derive(supports_count=1, contradicts_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )

    def test_validates_and_contradicts_is_unassessed(self) -> None:
        """Contradiction dominates even over validating evidence -- the
        identical dominance `ResearchClaimCalibrator._ceilings` already
        applies for the unrelated claim subsystem."""
        self.assertIs(
            self._derive(validates_count=1, contradicts_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )

    def test_supports_validates_and_contradicts_is_unassessed(self) -> None:
        self.assertIs(
            self._derive(
                supports_count=1, validates_count=1, contradicts_count=1
            ).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )

    def test_a_single_contradiction_dominates_regardless_of_how_much_else_exists(
        self,
    ) -> None:
        """Presence, never a vote: one `CONTRADICTS` link must force
        `UNASSESSED` even outnumbered five-to-one by `SUPPORTS`/`VALIDATES`
        links. A magnitude-comparing ("netting") implementation -- e.g.
        `UNASSESSED` only when `contradicts_count >= max(supports_count,
        validates_count)` -- would wrongly pass every *equal-count* test
        above but fails here."""
        self.assertIs(
            self._derive(supports_count=5, contradicts_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )
        self.assertIs(
            self._derive(validates_count=5, contradicts_count=1).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )
        self.assertIs(
            self._derive(
                supports_count=5, validates_count=5, contradicts_count=1
            ).evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )

    # -- required scenarios 10-15: every status --------------------------------

    def test_candidate_status_does_not_override_the_evidence_based_ceiling(
        self,
    ) -> None:
        derived = self._derive(status_value=None, validates_count=1)
        self.assertIs(derived.status, ResearchSecurityFindingStatus.CANDIDATE)
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.MEDIUM
        )

    def test_validation_required_status_does_not_override_the_ceiling(self) -> None:
        derived = self._derive(
            status_value=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            supports_count=1,
        )
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.LOW
        )

    def test_validated_status_does_not_override_the_ceiling(self) -> None:
        derived = self._derive(
            status_value=ResearchSecurityFindingStatus.VALIDATED, validates_count=1
        )
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.MEDIUM
        )

    def test_refuted_status_forces_unassessed_even_with_validating_evidence(
        self,
    ) -> None:
        """`REFUTED` is a bare operator judgement, gated by no evidence
        requirement of its own, so it can coexist with strong-looking
        `VALIDATES` evidence. The ceiling must not read `MEDIUM` beside an
        explicit refutation."""
        derived = self._derive(
            status_value=ResearchSecurityFindingStatus.REFUTED, validates_count=1
        )
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.UNASSESSED
        )

    def test_duplicate_status_does_not_override_the_ceiling(self) -> None:
        """`DUPLICATE` is an administrative disposition, not an evidentiary
        judgement -- deliberately given no special case."""
        derived = self._derive(
            status_value=ResearchSecurityFindingStatus.DUPLICATE,
            validates_count=1,
            duplicate_of_finding_id="finding-2",
        )
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.MEDIUM
        )

    def test_superseded_status_does_not_override_the_ceiling(self) -> None:
        derived = self._derive(
            status_value=ResearchSecurityFindingStatus.SUPERSEDED,
            supports_count=1,
            superseded_by_finding_id="finding-2",
        )
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.LOW
        )

    # -- required scenario 16: duplicate evidence IDs never inflate -----------

    def test_the_same_evidence_id_cited_twice_does_not_inflate_the_ceiling(
        self,
    ) -> None:
        record = finding_record()
        first = evidence_link(link_id="link-1", evidence_id="a" * 64)
        second = evidence_link(link_id="link-2", evidence_id="a" * 64)
        (derived,) = findings_for_program("program-a", (record,), (first, second), ())
        self.assertEqual(len(derived.supporting_evidence), 2)
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.LOW
        )

    # -- required scenario 17: free text never influences the ceiling --------

    def test_free_text_fields_never_influence_the_ceiling(self) -> None:
        plain = self._derive(validates_count=1)
        with_different_text = self._derive(
            validates_count=1,
            title="A completely different title",
            description="A completely different description mentioning"
            " CRITICAL EXPLOITED CONFIRMED HIGH.",
            required_followup="Different follow-up text.",
        )
        self.assertIs(plain.evidence_ceiling, with_different_text.evidence_ceiling)

    # -- HIGH is permanently unreachable today ---------------------------------

    def test_high_is_unreachable_across_every_combination_tried(self) -> None:
        statuses: tuple[ResearchSecurityFindingStatus | None, ...] = (
            None,
            ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            ResearchSecurityFindingStatus.VALIDATED,
            ResearchSecurityFindingStatus.REFUTED,
        )
        for status_value in statuses:
            for supports_count in (0, 1, 5):
                for validates_count in (0, 1, 5):
                    for contradicts_count in (0, 1, 5):
                        with self.subTest(
                            status=status_value,
                            supports=supports_count,
                            validates=validates_count,
                            contradicts=contradicts_count,
                        ):
                            derived = self._derive(
                                status_value=status_value,
                                supports_count=supports_count,
                                validates_count=validates_count,
                                contradicts_count=contradicts_count,
                            )
                            self.assertNotEqual(
                                derived.evidence_ceiling,
                                ResearchSecurityFindingEvidenceCeiling.HIGH,
                            )

    # -- required scenario 20: restart/reload determinism ----------------------

    def test_recomputing_from_the_same_persisted_logs_is_deterministic(self) -> None:
        record = finding_record()
        validates = evidence_link(
            link_id="v1",
            evidence_id="a" * 64,
            relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
        )
        first = findings_for_program("program-a", (record,), (validates,), ())
        second = findings_for_program("program-a", (record,), (validates,), ())
        self.assertEqual(first, second)
        self.assertIs(
            first[0].evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.MEDIUM
        )
        self.assertIs(
            second[0].evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.MEDIUM
        )

    # -- required scenario 21: reading the property mutates nothing -----------

    def test_reading_the_property_mutates_nothing(self) -> None:
        derived = self._derive(validates_count=1, contradicts_count=1)
        status_before = derived.status
        supporting_before = derived.supporting_evidence
        contradicting_before = derived.contradicting_evidence
        validation_before = derived.validation_evidence
        history_before = derived.status_history

        for _ in range(3):
            self.assertIs(
                derived.evidence_ceiling,
                ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
            )

        self.assertIs(derived.status, status_before)
        self.assertEqual(derived.supporting_evidence, supporting_before)
        self.assertEqual(derived.contradicting_evidence, contradicting_before)
        self.assertEqual(derived.validation_evidence, validation_before)
        self.assertEqual(derived.status_history, history_before)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            derived.status = ResearchSecurityFindingStatus.REFUTED  # type: ignore[misc]

    # -- required scenario 24: needs_attention is unaffected -------------------

    def test_needs_attention_and_evidence_ceiling_coexist_consistently(self) -> None:
        """A `VALIDATED` finding with a live `CONTRADICTS` link: both
        derived properties independently name the same underlying tension,
        neither overrides or depends on the other's implementation."""
        derived = self._derive(
            status_value=ResearchSecurityFindingStatus.VALIDATED,
            validates_count=1,
            contradicts_count=1,
        )
        self.assertTrue(derived.needs_attention)
        self.assertIs(
            derived.evidence_ceiling, ResearchSecurityFindingEvidenceCeiling.UNASSESSED
        )

    # -- mutation-equivalent guard: every branch is load-bearing ---------------

    def test_ceiling_requires_the_exact_precedence_order_not_a_shortcut(self) -> None:
        """A buggy implementation that ignored `REFUTED` entirely (checking
        only the evidence tuples) would wrongly return `MEDIUM` for the
        first case below; one that checked `SUPPORTS` before `CONTRADICTS`
        (or netted them) would wrongly return `LOW` for the second. Only
        the real, `REFUTED`-first-then-`CONTRADICTS`-then-`VALIDATES`-then-
        `SUPPORTS` precedence order gets both right."""
        refuted_with_validates = self._derive(
            status_value=ResearchSecurityFindingStatus.REFUTED, validates_count=1
        )
        supports_with_contradicts = self._derive(supports_count=1, contradicts_count=1)
        self.assertIs(
            refuted_with_validates.evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )
        self.assertIs(
            supports_with_contradicts.evidence_ceiling,
            ResearchSecurityFindingEvidenceCeiling.UNASSESSED,
        )


if __name__ == "__main__":
    unittest.main()
