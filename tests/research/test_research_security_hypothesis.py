"""Security hypothesis identity, status discipline, and derivation are honest.

`ResearchSecurityHypothesisRecord`/`EvidenceLinkRecord`/`StatusTransitionRecord`
are the only durable facts; `ResearchSecurityHypothesis`/`hypotheses_for_program`
are a pure, always-recomputed read model over them. No status this vocabulary
can produce ever asserts a validated vulnerability.
"""

from __future__ import annotations

import dataclasses
import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityHypothesis import (
    ResearchSecurityHypothesis,
    hypotheses_for_program,
)
from research.ResearchSecurityHypothesisEvidenceKind import (
    ResearchSecurityHypothesisEvidenceKind,
)
from research.ResearchSecurityHypothesisEvidenceLinkRecord import (
    ResearchSecurityHypothesisEvidenceLinkRecord,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSecurityHypothesisRecord import (
    MAX_SECURITY_HYPOTHESIS_RATIONALE_CHARACTERS,
    MAX_SECURITY_HYPOTHESIS_REQUIRED_VALIDATION_CHARACTERS,
    MAX_SECURITY_HYPOTHESIS_STATEMENT_CHARACTERS,
    ResearchSecurityHypothesisRecord,
)
from research.ResearchSecurityHypothesisStatus import (
    ResearchSecurityHypothesisStatus,
    is_valid_status_transition,
)
from research.ResearchSecurityHypothesisStatusTransitionRecord import (
    ResearchSecurityHypothesisStatusTransitionRecord,
)

RECORDED = datetime(2026, 9, 25, 10, tzinfo=UTC)
LATER = datetime(2026, 9, 25, 11, tzinfo=UTC)
LATEST = datetime(2026, 9, 25, 12, tzinfo=UTC)


def hypothesis_record(
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    hypothesis_kind: ResearchSecurityHypothesisKind = (
        ResearchSecurityHypothesisKind.AUTHORIZATION
    ),
    subject_kind: ResearchAssetKind = ResearchAssetKind.HOSTNAME,
    subject_value: str = "example.test",
    statement: str = "The order endpoint may accept a client-controlled order ID.",
    rationale: str = "Observed HTTP evidence shows a numeric ID in the request path.",
    required_validation: str = "Request the same order ID as a different account.",
    origin: ResearchSecurityHypothesisOrigin = (
        ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED
    ),
    created_at: datetime = RECORDED,
) -> ResearchSecurityHypothesisRecord:
    return ResearchSecurityHypothesisRecord(
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        hypothesis_kind=hypothesis_kind,
        subject_kind=subject_kind,
        subject_canonical_value=canonicalize_asset_value(subject_kind, subject_value),
        statement=statement,
        rationale=rationale,
        required_validation=required_validation,
        origin=origin,
        created_at=created_at,
    )


def evidence_link(
    link_id: str = "link-1",
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    evidence_id: str = "a" * 64,
    relation: ResearchSecurityHypothesisEvidenceRelation = (
        ResearchSecurityHypothesisEvidenceRelation.SUPPORTS
    ),
    recorded_at: datetime = RECORDED,
) -> ResearchSecurityHypothesisEvidenceLinkRecord:
    return ResearchSecurityHypothesisEvidenceLinkRecord(
        link_id=link_id,
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityHypothesisEvidenceKind.HTTP_EVIDENCE,
        evidence_id=evidence_id,
        relation=relation,
        recorded_at=recorded_at,
    )


def status_transition(
    transition_id: str = "transition-1",
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    status: ResearchSecurityHypothesisStatus = (
        ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE
    ),
    reason: str = "",
    recorded_at: datetime = RECORDED,
) -> ResearchSecurityHypothesisStatusTransitionRecord:
    return ResearchSecurityHypothesisStatusTransitionRecord(
        transition_id=transition_id,
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        status=status,
        reason=reason,
        recorded_at=recorded_at,
    )


class ResearchSecurityHypothesisRecordTests(unittest.TestCase):
    def test_valid_construction_round_trips(self) -> None:
        record = hypothesis_record()
        self.assertEqual(record.subject_canonical_value, "example.test")
        self.assertEqual(
            record.origin, ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED
        )

    def test_record_is_frozen(self) -> None:
        record = hypothesis_record()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.statement = "changed"  # type: ignore[misc]

    def test_invalid_hypothesis_kind_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis_record(hypothesis_kind="authorization")  # type: ignore[arg-type]

    def test_invalid_subject_kind_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityHypothesisRecord(
                hypothesis_id="hypothesis-1",
                program_id="program-a",
                hypothesis_kind=ResearchSecurityHypothesisKind.UNKNOWN,
                subject_kind="hostname",  # type: ignore[arg-type]
                subject_canonical_value="example.test",
                statement="statement",
                rationale="rationale",
                required_validation="required validation",
                origin=ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,
                created_at=RECORDED,
            )

    def test_non_canonical_subject_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not canonical"):
            ResearchSecurityHypothesisRecord(
                hypothesis_id="hypothesis-1",
                program_id="program-a",
                hypothesis_kind=ResearchSecurityHypothesisKind.UNKNOWN,
                subject_kind=ResearchAssetKind.HOSTNAME,
                subject_canonical_value="EXAMPLE.TEST.",
                statement="statement",
                rationale="rationale",
                required_validation="required validation",
                origin=ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,
                created_at=RECORDED,
            )

    def test_bounded_text_is_enforced_on_every_free_text_field(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis_record(
                statement="x" * (MAX_SECURITY_HYPOTHESIS_STATEMENT_CHARACTERS + 1)
            )
        with self.assertRaises(ResearchError):
            hypothesis_record(
                rationale="x" * (MAX_SECURITY_HYPOTHESIS_RATIONALE_CHARACTERS + 1)
            )
        with self.assertRaises(ResearchError):
            hypothesis_record(
                required_validation=(
                    "x" * (MAX_SECURITY_HYPOTHESIS_REQUIRED_VALIDATION_CHARACTERS + 1)
                )
            )

    def test_empty_required_free_text_field_is_rejected(self) -> None:
        for field in ("statement", "rationale", "required_validation"):
            with self.subTest(field=field):
                with self.assertRaises(ResearchError):
                    hypothesis_record(**{field: "   "})

    def test_naive_created_at_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis_record(created_at=datetime(2026, 9, 25, 10))


class SecurityHypothesisOriginAndEvidenceKindTests(unittest.TestCase):
    def test_origin_has_exactly_one_member(self) -> None:
        self.assertEqual(
            tuple(ResearchSecurityHypothesisOrigin),
            (ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,),
        )

    def test_evidence_kind_has_exactly_one_member(self) -> None:
        self.assertEqual(
            tuple(ResearchSecurityHypothesisEvidenceKind),
            (ResearchSecurityHypothesisEvidenceKind.HTTP_EVIDENCE,),
        )


class ResearchSecurityHypothesisEvidenceLinkRecordTests(unittest.TestCase):
    def test_valid_construction_round_trips(self) -> None:
        link = evidence_link()
        self.assertEqual(link.evidence_id, "a" * 64)
        self.assertIs(
            link.relation, ResearchSecurityHypothesisEvidenceRelation.SUPPORTS
        )

    def test_malformed_http_evidence_id_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            evidence_link(evidence_id="not-a-real-evidence-id")

    def test_link_is_frozen(self) -> None:
        link = evidence_link()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            link.evidence_id = "b" * 64  # type: ignore[misc]


class ResearchSecurityHypothesisStatusTests(unittest.TestCase):
    def test_only_refuted_is_terminal(self) -> None:
        for status in ResearchSecurityHypothesisStatus:
            with self.subTest(status=status):
                self.assertEqual(
                    status.terminal, status is ResearchSecurityHypothesisStatus.REFUTED
                )

    def test_no_status_means_a_validated_vulnerability(self) -> None:
        for status in ResearchSecurityHypothesisStatus:
            with self.subTest(status=status):
                self.assertFalse(status.means_validated_vulnerability)

    def test_every_valid_transition_succeeds(self) -> None:
        valid_pairs = (
            (
                ResearchSecurityHypothesisStatus.OPEN,
                ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            ),
            (
                ResearchSecurityHypothesisStatus.OPEN,
                ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
            ),
            (
                ResearchSecurityHypothesisStatus.OPEN,
                ResearchSecurityHypothesisStatus.REFUTED,
            ),
            (
                ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
                ResearchSecurityHypothesisStatus.OPEN,
            ),
            (
                ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
                ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
            ),
            (
                ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
                ResearchSecurityHypothesisStatus.REFUTED,
            ),
            (
                ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
                ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            ),
            (
                ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
                ResearchSecurityHypothesisStatus.REFUTED,
            ),
        )
        for current, new in valid_pairs:
            with self.subTest(current=current, new=new):
                self.assertTrue(is_valid_status_transition(current, new))

    def test_every_invalid_transition_fails_closed(self) -> None:
        invalid_pairs = (
            (
                ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
                ResearchSecurityHypothesisStatus.OPEN,
            ),
            (
                ResearchSecurityHypothesisStatus.REFUTED,
                ResearchSecurityHypothesisStatus.OPEN,
            ),
            (
                ResearchSecurityHypothesisStatus.REFUTED,
                ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            ),
            (
                ResearchSecurityHypothesisStatus.REFUTED,
                ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
            ),
        )
        for current, new in invalid_pairs:
            with self.subTest(current=current, new=new):
                self.assertFalse(is_valid_status_transition(current, new))

    def test_every_self_transition_is_invalid(self) -> None:
        for status in ResearchSecurityHypothesisStatus:
            with self.subTest(status=status):
                self.assertFalse(is_valid_status_transition(status, status))

    def test_refuted_has_no_outgoing_transition(self) -> None:
        for status in ResearchSecurityHypothesisStatus:
            with self.subTest(status=status):
                self.assertFalse(
                    is_valid_status_transition(
                        ResearchSecurityHypothesisStatus.REFUTED, status
                    )
                )


class ResearchSecurityHypothesisStatusTransitionRecordTests(unittest.TestCase):
    def test_empty_reason_is_accepted(self) -> None:
        transition = status_transition(reason="")
        self.assertEqual(transition.reason, "")

    def test_transition_is_frozen(self) -> None:
        transition = status_transition()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            transition.status = ResearchSecurityHypothesisStatus.REFUTED  # type: ignore[misc]

    def test_invalid_status_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            status_transition(status="open")  # type: ignore[arg-type]


class SecurityHypothesisSensitiveInputRefusalTests(unittest.TestCase):
    """Mirrors `AssetNoteSensitiveInputRefusalTests`'s category/benign shapes."""

    SENTINEL = "distinct-hypothesis-secret-sentinel"

    def _cases(self) -> dict[str, str]:
        sentinel = self.SENTINEL
        return {
            "credential_bearing_url": f"https://user:{sentinel}@example.test",
            "authentication_header": f"Authorization: Bearer {sentinel}",
            "private_key_material": "-----BEGIN PRIVATE KEY-----",
            "secret_assignment": f"password={sentinel}",
            "token_format": "sk-abcdefghijklmnopqrstuvwxyz123456",
        }

    def test_statement_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    hypothesis_record(statement=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_rationale_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    hypothesis_record(rationale=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_required_validation_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    hypothesis_record(required_validation=value)
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
        self.assertEqual(hypothesis_record(statement=benign).statement, benign)
        self.assertEqual(hypothesis_record(rationale=benign).rationale, benign)
        self.assertEqual(status_transition(reason=benign).reason, benign)


class HypothesesForProgramTests(unittest.TestCase):
    def test_derives_open_status_with_no_transitions(self) -> None:
        record = hypothesis_record()
        link = evidence_link()
        (derived,) = hypotheses_for_program("program-a", (record,), (link,), ())
        self.assertIs(derived.status, ResearchSecurityHypothesisStatus.OPEN)
        self.assertEqual(derived.supporting_evidence, (link,))
        self.assertEqual(derived.contradicting_evidence, ())
        self.assertEqual(derived.status_history, ())

    def test_derives_latest_status_by_recorded_at(self) -> None:
        record = hypothesis_record()
        earlier = status_transition(
            transition_id="t1",
            status=ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            recorded_at=RECORDED,
        )
        later = status_transition(
            transition_id="t2",
            status=ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
            recorded_at=LATER,
        )
        (derived,) = hypotheses_for_program(
            "program-a", (record,), (), (earlier, later)
        )
        self.assertIs(
            derived.status, ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION
        )
        self.assertEqual(derived.status_history, (earlier, later))

    def test_ties_broken_by_transition_id(self) -> None:
        record = hypothesis_record()
        first = status_transition(
            transition_id="a-transition",
            status=ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
            recorded_at=RECORDED,
        )
        second = status_transition(
            transition_id="b-transition",
            status=ResearchSecurityHypothesisStatus.REFUTED,
            recorded_at=RECORDED,
        )
        (derived,) = hypotheses_for_program("program-a", (record,), (), (first, second))
        self.assertIs(derived.status, ResearchSecurityHypothesisStatus.REFUTED)

    def test_multiple_evidence_links_are_preserved_and_returned(self) -> None:
        record = hypothesis_record()
        supporting_one = evidence_link(link_id="link-1", evidence_id="a" * 64)
        supporting_two = evidence_link(link_id="link-2", evidence_id="b" * 64)
        contradicting = evidence_link(
            link_id="link-3",
            evidence_id="c" * 64,
            relation=ResearchSecurityHypothesisEvidenceRelation.CONTRADICTS,
        )
        (derived,) = hypotheses_for_program(
            "program-a",
            (record,),
            (supporting_one, supporting_two, contradicting),
            (),
        )
        self.assertEqual(derived.supporting_evidence, (supporting_one, supporting_two))
        self.assertEqual(derived.contradicting_evidence, (contradicting,))

    def test_other_program_is_excluded(self) -> None:
        record = hypothesis_record(hypothesis_id="hypothesis-1", program_id="program-a")
        self.assertEqual(hypotheses_for_program("program-b", (record,), (), ()), ())

    def test_derived_model_is_frozen_and_validates_identity(self) -> None:
        record = hypothesis_record()
        derived = hypotheses_for_program("program-a", (record,), (), ())[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            derived.status = ResearchSecurityHypothesisStatus.REFUTED  # type: ignore[misc]
        foreign_link = evidence_link(hypothesis_id="other-hypothesis")
        with self.assertRaises(ResearchError):
            ResearchSecurityHypothesis(
                hypothesis_id=record.hypothesis_id,
                program_id=record.program_id,
                hypothesis_kind=record.hypothesis_kind,
                subject_kind=record.subject_kind,
                subject_canonical_value=record.subject_canonical_value,
                statement=record.statement,
                rationale=record.rationale,
                required_validation=record.required_validation,
                origin=record.origin,
                created_at=record.created_at,
                supporting_evidence=(foreign_link,),
                contradicting_evidence=(),
                status=ResearchSecurityHypothesisStatus.OPEN,
                status_history=(),
            )


if __name__ == "__main__":
    unittest.main()
