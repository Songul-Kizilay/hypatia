"""Persistence tests for the atomic, append-only security finding JSON store."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchSecurityFindingStore import (
    MAX_SECURITY_FINDING_EVIDENCE_LINKS,
    MAX_SECURITY_FINDING_STATUS_TRANSITIONS,
    MAX_SECURITY_FINDINGS,
    JsonFileResearchSecurityFindingStore,
    ResearchSecurityFindingDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityFinding import findings_for_program
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
from research.ResearchSecurityFindingRecord import ResearchSecurityFindingRecord
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind

RECORDED = datetime(2026, 9, 26, 10, tzinfo=UTC)


def finding_record(
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    subject_value: str = "example.test",
) -> ResearchSecurityFindingRecord:
    return ResearchSecurityFindingRecord(
        finding_id=finding_id,
        program_id=program_id,
        source_hypothesis_id="hypothesis-1",
        finding_kind=ResearchSecurityHypothesisKind.AUTHORIZATION,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=canonicalize_asset_value(
            ResearchAssetKind.HOSTNAME, subject_value
        ),
        title="An operator-authored finding title.",
        description="A description of what was observed.",
        required_followup="A description of what would still need doing.",
        origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
    )


def evidence_link(
    link_id: str = "link-1",
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    evidence_id: str = "a" * 64,
) -> ResearchSecurityFindingEvidenceLinkRecord:
    return ResearchSecurityFindingEvidenceLinkRecord(
        link_id=link_id,
        finding_id=finding_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
        evidence_id=evidence_id,
        relation=ResearchSecurityFindingEvidenceRelation.SUPPORTS,
        recorded_at=RECORDED,
    )


def status_transition(
    transition_id: str = "transition-1",
    finding_id: str = "finding-1",
    program_id: str = "program-a",
) -> ResearchSecurityFindingStatusTransitionRecord:
    return ResearchSecurityFindingStatusTransitionRecord(
        transition_id=transition_id,
        finding_id=finding_id,
        program_id=program_id,
        status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
        reason="",
        duplicate_of_finding_id=None,
        superseded_by_finding_id=None,
        recorded_at=RECORDED,
    )


FINDING_JSON_FIELDS = {
    "finding_id": "finding-1",
    "program_id": "program-a",
    "source_hypothesis_id": "hypothesis-1",
    "finding_kind": "authorization",
    "subject_kind": "hostname",
    "subject_canonical_value": "example.test",
    "title": "title",
    "description": "description",
    "required_followup": "required followup",
    "origin": "operator_authored",
    "created_at": RECORDED.isoformat(),
}

EVIDENCE_LINK_JSON_FIELDS = {
    "link_id": "link-1",
    "finding_id": "finding-1",
    "program_id": "program-a",
    "evidence_kind": "http_evidence",
    "evidence_id": "a" * 64,
    "relation": "supports",
    "recorded_at": RECORDED.isoformat(),
}

STATUS_TRANSITION_JSON_FIELDS = {
    "transition_id": "transition-1",
    "finding_id": "finding-1",
    "program_id": "program-a",
    "status": "validation_required",
    "reason": "",
    "duplicate_of_finding_id": None,
    "superseded_by_finding_id": None,
    "recorded_at": RECORDED.isoformat(),
}


class ResearchSecurityFindingDocumentTests(unittest.TestCase):
    def test_default_document_is_empty(self) -> None:
        document = ResearchSecurityFindingDocument()
        self.assertEqual(document.findings, ())
        self.assertEqual(document.evidence_links, ())
        self.assertEqual(document.status_transitions, ())

    def test_duplicate_finding_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "duplicate finding IDs"):
            ResearchSecurityFindingDocument(
                findings=(
                    finding_record(finding_id="f1"),
                    finding_record(finding_id="f1", subject_value="other.test"),
                )
            )

    def test_duplicate_evidence_link_ids_are_rejected(self) -> None:
        record = finding_record()
        with self.assertRaisesRegex(ResearchError, "duplicate evidence link IDs"):
            ResearchSecurityFindingDocument(
                findings=(record,),
                evidence_links=(
                    evidence_link(link_id="link-1"),
                    evidence_link(link_id="link-1", evidence_id="b" * 64),
                ),
            )

    def test_duplicate_status_transition_ids_are_rejected(self) -> None:
        record = finding_record()
        with self.assertRaisesRegex(ResearchError, "duplicate status transition IDs"):
            ResearchSecurityFindingDocument(
                findings=(record,),
                status_transitions=(
                    status_transition(transition_id="t1"),
                    status_transition(transition_id="t1"),
                ),
            )

    def test_evidence_link_must_reference_a_recorded_finding(self) -> None:
        with self.assertRaisesRegex(ResearchError, "must reference a recorded finding"):
            ResearchSecurityFindingDocument(evidence_links=(evidence_link(),))

    def test_evidence_link_cannot_reference_a_finding_in_another_program(self) -> None:
        record = finding_record(program_id="program-a")
        link = evidence_link(program_id="program-b")
        with self.assertRaisesRegex(ResearchError, "must reference a recorded finding"):
            ResearchSecurityFindingDocument(findings=(record,), evidence_links=(link,))

    def test_status_transition_must_reference_a_recorded_finding(self) -> None:
        with self.assertRaisesRegex(ResearchError, "must reference a recorded finding"):
            ResearchSecurityFindingDocument(status_transitions=(status_transition(),))

    def _duplicate_transition(
        self,
        duplicate_of_finding_id: str | None,
        finding_id: str = "finding-1",
        program_id: str = "program-a",
    ) -> ResearchSecurityFindingStatusTransitionRecord:
        return ResearchSecurityFindingStatusTransitionRecord(
            transition_id="transition-1",
            finding_id=finding_id,
            program_id=program_id,
            status=ResearchSecurityFindingStatus.DUPLICATE,
            reason="",
            duplicate_of_finding_id=duplicate_of_finding_id,
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )

    def _superseded_transition(
        self,
        superseded_by_finding_id: str | None,
        finding_id: str = "finding-1",
        program_id: str = "program-a",
    ) -> ResearchSecurityFindingStatusTransitionRecord:
        return ResearchSecurityFindingStatusTransitionRecord(
            transition_id="transition-1",
            finding_id=finding_id,
            program_id=program_id,
            status=ResearchSecurityFindingStatus.SUPERSEDED,
            reason="",
            duplicate_of_finding_id=None,
            superseded_by_finding_id=superseded_by_finding_id,
            recorded_at=RECORDED,
        )

    def test_duplicate_of_reference_must_reference_a_recorded_finding(self) -> None:
        record = finding_record(finding_id="finding-1")
        with self.assertRaisesRegex(
            ResearchError, "duplicate-of reference must name a recorded finding"
        ):
            ResearchSecurityFindingDocument(
                findings=(record,),
                status_transitions=(self._duplicate_transition("ghost-finding"),),
            )

    def test_duplicate_of_reference_cannot_reference_a_finding_in_another_program(
        self,
    ) -> None:
        record_one = finding_record(finding_id="finding-1", program_id="program-a")
        record_two = finding_record(
            finding_id="finding-2", program_id="program-b", subject_value="other.test"
        )
        with self.assertRaisesRegex(
            ResearchError, "duplicate-of reference must name a recorded finding"
        ):
            ResearchSecurityFindingDocument(
                findings=(record_one, record_two),
                status_transitions=(self._duplicate_transition("finding-2"),),
            )

    def test_duplicate_of_reference_cannot_name_itself(self) -> None:
        record = finding_record(finding_id="finding-1")
        with self.assertRaisesRegex(
            ResearchError, "duplicate-of reference cannot name itself"
        ):
            ResearchSecurityFindingDocument(
                findings=(record,),
                status_transitions=(self._duplicate_transition("finding-1"),),
            )

    def test_superseded_by_reference_must_reference_a_recorded_finding(self) -> None:
        record = finding_record(finding_id="finding-1")
        with self.assertRaisesRegex(
            ResearchError, "superseded-by reference must name a recorded finding"
        ):
            ResearchSecurityFindingDocument(
                findings=(record,),
                status_transitions=(self._superseded_transition("ghost-finding"),),
            )

    def test_superseded_by_reference_cannot_reference_a_finding_in_another_program(
        self,
    ) -> None:
        record_one = finding_record(finding_id="finding-1", program_id="program-a")
        record_two = finding_record(
            finding_id="finding-2", program_id="program-b", subject_value="other.test"
        )
        with self.assertRaisesRegex(
            ResearchError, "superseded-by reference must name a recorded finding"
        ):
            ResearchSecurityFindingDocument(
                findings=(record_one, record_two),
                status_transitions=(self._superseded_transition("finding-2"),),
            )

    def test_superseded_by_reference_cannot_name_itself(self) -> None:
        record = finding_record(finding_id="finding-1")
        with self.assertRaisesRegex(
            ResearchError, "superseded-by reference cannot name itself"
        ):
            ResearchSecurityFindingDocument(
                findings=(record,),
                status_transitions=(self._superseded_transition("finding-1"),),
            )

    def test_status_transition_sequence_must_be_a_legal_walk_of_transitions(
        self,
    ) -> None:
        record = finding_record()
        with self.assertRaisesRegex(ResearchError, "not a legal sequence"):
            ResearchSecurityFindingDocument(
                findings=(record,),
                status_transitions=(
                    status_transition(transition_id="t1"),
                    status_transition(transition_id="t2"),
                ),
            )

    def test_a_legal_multi_hop_status_transition_sequence_is_accepted(self) -> None:
        record = finding_record()
        document = ResearchSecurityFindingDocument(
            findings=(record,),
            status_transitions=(
                status_transition(transition_id="t1"),
                ResearchSecurityFindingStatusTransitionRecord(
                    transition_id="t2",
                    finding_id="finding-1",
                    program_id="program-a",
                    status=ResearchSecurityFindingStatus.VALIDATED,
                    reason="",
                    duplicate_of_finding_id=None,
                    superseded_by_finding_id=None,
                    recorded_at=RECORDED,
                ),
                ResearchSecurityFindingStatusTransitionRecord(
                    transition_id="t3",
                    finding_id="finding-1",
                    program_id="program-a",
                    status=ResearchSecurityFindingStatus.REFUTED,
                    reason="",
                    duplicate_of_finding_id=None,
                    superseded_by_finding_id=None,
                    recorded_at=RECORDED,
                ),
            ),
        )
        self.assertEqual(len(document.status_transitions), 3)

    def test_a_legal_multi_hop_sequence_ending_in_duplicate_is_accepted(self) -> None:
        record = finding_record(finding_id="finding-1")
        other = finding_record(finding_id="finding-2", subject_value="other.test")
        document = ResearchSecurityFindingDocument(
            findings=(record, other),
            status_transitions=(
                status_transition(transition_id="t1"),
                ResearchSecurityFindingStatusTransitionRecord(
                    transition_id="t2",
                    finding_id="finding-1",
                    program_id="program-a",
                    status=ResearchSecurityFindingStatus.DUPLICATE,
                    reason="",
                    duplicate_of_finding_id="finding-2",
                    superseded_by_finding_id=None,
                    recorded_at=RECORDED,
                ),
            ),
        )
        self.assertEqual(len(document.status_transitions), 2)

    def test_a_legal_multi_hop_sequence_ending_in_superseded_is_accepted(self) -> None:
        record = finding_record(finding_id="finding-1")
        other = finding_record(finding_id="finding-2", subject_value="other.test")
        document = ResearchSecurityFindingDocument(
            findings=(record, other),
            status_transitions=(
                status_transition(transition_id="t1"),
                ResearchSecurityFindingStatusTransitionRecord(
                    transition_id="t2",
                    finding_id="finding-1",
                    program_id="program-a",
                    status=ResearchSecurityFindingStatus.SUPERSEDED,
                    reason="",
                    duplicate_of_finding_id=None,
                    superseded_by_finding_id="finding-2",
                    recorded_at=RECORDED,
                ),
            ),
        )
        self.assertEqual(len(document.status_transitions), 2)

    def test_non_tuple_or_wrong_typed_members_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingDocument(findings=[finding_record()])  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingDocument(findings=("not-a-record",))  # type: ignore[arg-type]
        record = finding_record()
        with self.assertRaises(ResearchError):
            ResearchSecurityFindingDocument(
                findings=(record,), evidence_links=["not-a-tuple-member"]  # type: ignore[arg-type]
            )

    def test_bounded_counts_are_enforced(self) -> None:
        module = "research.JsonFileResearchSecurityFindingStore"
        with patch(f"{module}.MAX_SECURITY_FINDINGS", 1):
            with self.assertRaisesRegex(ResearchError, "too many records"):
                ResearchSecurityFindingDocument(
                    findings=(
                        finding_record(finding_id="f1"),
                        finding_record(finding_id="f2", subject_value="b.test"),
                    )
                )
        record = finding_record()
        with patch(f"{module}.MAX_SECURITY_FINDING_EVIDENCE_LINKS", 1):
            with self.assertRaisesRegex(ResearchError, "too many evidence links"):
                ResearchSecurityFindingDocument(
                    findings=(record,),
                    evidence_links=(
                        evidence_link(link_id="l1"),
                        evidence_link(link_id="l2", evidence_id="b" * 64),
                    ),
                )
        with patch(f"{module}.MAX_SECURITY_FINDING_STATUS_TRANSITIONS", 1):
            with self.assertRaisesRegex(ResearchError, "too many status transitions"):
                ResearchSecurityFindingDocument(
                    findings=(record,),
                    status_transitions=(
                        status_transition(transition_id="t1"),
                        status_transition(transition_id="t2"),
                    ),
                )


class JsonFileResearchSecurityFindingStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "security_findings.json"
        self.store = JsonFileResearchSecurityFindingStore(self.path)

    def test_loading_an_absent_file_returns_an_empty_document(self) -> None:
        document = self.store.load()
        self.assertEqual(document, ResearchSecurityFindingDocument())
        self.assertFalse(self.path.exists())

    def test_round_trip_preserves_every_record_kind(self) -> None:
        record = finding_record()
        link = evidence_link()
        transition = status_transition()
        document = ResearchSecurityFindingDocument(
            findings=(record,),
            evidence_links=(link,),
            status_transitions=(transition,),
        )

        self.store.save(document)
        reloaded = self.store.load()

        self.assertEqual(reloaded, document)

    def test_needs_attention_survives_a_store_reload(self) -> None:
        """v0.3.426: `needs_attention` is derived fresh from persisted facts
        on every read, never stored as its own field -- so restart must
        reproduce the identical answer from the reloaded flat logs alone."""
        record = finding_record()
        validates = ResearchSecurityFindingEvidenceLinkRecord(
            link_id="link-1",
            finding_id="finding-1",
            program_id="program-a",
            evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
            evidence_id="a" * 64,
            relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
            recorded_at=RECORDED,
        )
        contradicts = ResearchSecurityFindingEvidenceLinkRecord(
            link_id="link-2",
            finding_id="finding-1",
            program_id="program-a",
            evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
            evidence_id="b" * 64,
            relation=ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
            recorded_at=RECORDED,
        )
        transition = ResearchSecurityFindingStatusTransitionRecord(
            transition_id="t1",
            finding_id="finding-1",
            program_id="program-a",
            status=ResearchSecurityFindingStatus.VALIDATED,
            reason="",
            duplicate_of_finding_id=None,
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )
        document = ResearchSecurityFindingDocument(
            findings=(record,),
            evidence_links=(validates, contradicts),
            status_transitions=(transition,),
        )

        self.store.save(document)
        reloaded = self.store.load()

        (derived,) = findings_for_program(
            "program-a",
            reloaded.findings,
            reloaded.evidence_links,
            reloaded.status_transitions,
        )
        self.assertIs(derived.status, ResearchSecurityFindingStatus.VALIDATED)
        self.assertTrue(derived.needs_attention)

    def test_round_trip_preserves_duplicate_and_superseded_linkage(self) -> None:
        record_one = finding_record(finding_id="f1")
        record_two = finding_record(finding_id="f2", subject_value="other.test")
        duplicate_transition = ResearchSecurityFindingStatusTransitionRecord(
            transition_id="t1",
            finding_id="f1",
            program_id="program-a",
            status=ResearchSecurityFindingStatus.DUPLICATE,
            reason="",
            duplicate_of_finding_id="f2",
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )
        document = ResearchSecurityFindingDocument(
            findings=(record_one, record_two),
            status_transitions=(duplicate_transition,),
        )

        self.store.save(document)
        reloaded = self.store.load()

        self.assertEqual(reloaded, document)
        self.assertEqual(reloaded.status_transitions[0].duplicate_of_finding_id, "f2")

    def test_saving_twice_appends_to_the_existing_document(self) -> None:
        original = ResearchSecurityFindingDocument(findings=(finding_record(),))
        self.store.save(original)
        appended = ResearchSecurityFindingDocument(
            findings=(
                *original.findings,
                finding_record(finding_id="f2", subject_value="other.test"),
            )
        )

        self.store.save(appended)

        self.assertEqual(self.store.load(), appended)

    def test_save_rejects_removal_or_replacement_of_existing_records(self) -> None:
        original = ResearchSecurityFindingDocument(findings=(finding_record(),))
        self.store.save(original)
        replacement = ResearchSecurityFindingDocument(
            findings=(finding_record(finding_id="f2", subject_value="other.test"),)
        )

        with self.assertRaisesRegex(ResearchError, "append-only"):
            self.store.save(replacement)

        self.assertEqual(self.store.load(), original)

    def test_save_rejects_removal_or_alteration_of_status_transition_history(
        self,
    ) -> None:
        # Uses two distinct, sequence-legal statuses (CANDIDATE ->
        # VALIDATION_REQUIRED -> VALIDATED) rather than repeating one status
        # twice: a real append-only violation must be caught even when the
        # tampered history would otherwise still be a legal walk of the
        # closed state-machine table, so this test deliberately keeps every
        # attempt's *content* legal wherever that is achievable and asserts
        # on the append-only guard specifically. Reordering these two
        # transitions is the one attempt that cannot stay sequence-legal by
        # construction: CANDIDATE and VALIDATION_REQUIRED are this graph's
        # only mutually-reachable pair, but VALIDATED is not reachable from
        # VALIDATION_REQUIRED's own successor set going backward — reversed,
        # the walk is CANDIDATE -> VALIDATED (legal) -> VALIDATION_REQUIRED,
        # and VALIDATION_REQUIRED is not in VALIDATED's allowed set (only
        # REFUTED/DUPLICATE/SUPERSEDED are) — so it is independently, and
        # correctly, caught by the newer sequence-legality replay instead,
        # asserted on its own message below.
        original = ResearchSecurityFindingDocument(
            findings=(finding_record(),),
            status_transitions=(
                status_transition(transition_id="transition-1"),
                ResearchSecurityFindingStatusTransitionRecord(
                    transition_id="transition-2",
                    finding_id="finding-1",
                    program_id="program-a",
                    status=ResearchSecurityFindingStatus.VALIDATED,
                    reason="",
                    duplicate_of_finding_id=None,
                    superseded_by_finding_id=None,
                    recorded_at=RECORDED,
                ),
            ),
        )
        self.store.save(original)
        altered = ResearchSecurityFindingStatusTransitionRecord(
            transition_id="transition-1",
            finding_id="finding-1",
            program_id="program-a",
            status=ResearchSecurityFindingStatus.VALIDATION_REQUIRED,
            reason="rewritten after the fact",
            duplicate_of_finding_id=None,
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )
        third = ResearchSecurityFindingStatusTransitionRecord(
            transition_id="transition-3",
            finding_id="finding-1",
            program_id="program-a",
            status=ResearchSecurityFindingStatus.REFUTED,
            reason="",
            duplicate_of_finding_id=None,
            superseded_by_finding_id=None,
            recorded_at=RECORDED,
        )
        append_only_attempts = {
            "removed": (),
            "truncated": (original.status_transitions[0],),
            "altered": (altered, original.status_transitions[1]),
            "replaced-then-appended": (
                altered,
                original.status_transitions[1],
                third,
            ),
        }

        for label, transitions in append_only_attempts.items():
            with self.subTest(attempt=label):
                with self.assertRaisesRegex(ResearchError, "append-only"):
                    self.store.save(
                        ResearchSecurityFindingDocument(
                            findings=original.findings,
                            status_transitions=transitions,
                        )
                    )
                self.assertEqual(self.store.load(), original)

        with self.assertRaisesRegex(ResearchError, "not a legal sequence"):
            self.store.save(
                ResearchSecurityFindingDocument(
                    findings=original.findings,
                    status_transitions=tuple(reversed(original.status_transitions)),
                )
            )
        self.assertEqual(self.store.load(), original)

    def test_a_failed_atomic_write_keeps_the_original_and_leaves_no_temp_file(
        self,
    ) -> None:
        original = ResearchSecurityFindingDocument(findings=(finding_record(),))
        self.store.save(original)
        original_bytes = self.path.read_bytes()
        appended = ResearchSecurityFindingDocument(
            findings=original.findings,
            status_transitions=(status_transition(),),
        )

        with patch(
            "research.JsonFileResearchSecurityFindingStore.os.replace",
            side_effect=OSError("simulated rename failure"),
        ):
            with self.assertRaisesRegex(ResearchError, "Unable to write"):
                self.store.save(appended)

        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(self.store.load(), original)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_save_rejects_anything_other_than_a_document(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save({"findings": []})  # type: ignore[arg-type]

    def test_no_temporary_file_is_left_behind_after_a_clean_save(self) -> None:
        self.store.save(ResearchSecurityFindingDocument(findings=(finding_record(),)))
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    # -- malformed persisted content fails closed ---------------------------

    def _write_raw(self, payload: object) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def _empty_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 1,
            "findings": [],
            "evidence_links": [],
            "status_transitions": [],
        }
        payload.update(overrides)
        return payload

    def test_truncated_or_non_json_content_fails_closed(self) -> None:
        self.store.save(
            ResearchSecurityFindingDocument(
                findings=(finding_record(),),
                evidence_links=(evidence_link(),),
                status_transitions=(status_transition(),),
            )
        )
        complete = self.path.read_bytes()
        payloads = {
            "truncated-half": complete[: len(complete) // 2],
            "truncated-last-byte": complete.rstrip()[:-1],
            "empty": b"",
            "not-json": b"this is not json",
            "invalid-utf8": b"\xff\xfe\x00{",
        }

        for label, payload in payloads.items():
            with self.subTest(payload=label):
                self.path.write_bytes(payload)
                with self.assertRaises(ResearchError):
                    self.store.load()

    def test_non_dict_document_is_rejected(self) -> None:
        self._write_raw([])
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_wrong_field_set_is_rejected(self) -> None:
        self._write_raw({"schema_version": 1, "findings": []})
        with self.assertRaises(ResearchError):
            self.store.load()
        self._write_raw({**self._empty_payload(), "extra": "field"})
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_unsupported_schema_version_is_rejected(self) -> None:
        self._write_raw(self._empty_payload(schema_version=2))
        with self.assertRaisesRegex(ResearchError, "schema version"):
            self.store.load()

    def test_zero_and_negative_and_boolean_schema_versions_are_rejected(self) -> None:
        for schema_version in (0, -1, True):
            with self.subTest(schema_version=schema_version):
                self._write_raw(self._empty_payload(schema_version=schema_version))
                with self.assertRaisesRegex(ResearchError, "schema version"):
                    self.store.load()

    def test_non_list_fields_are_rejected(self) -> None:
        for field in ("findings", "evidence_links", "status_transitions"):
            with self.subTest(field=field):
                self._write_raw(self._empty_payload(**{field: "not-a-list"}))
                with self.assertRaisesRegex(ResearchError, "must be a list"):
                    self.store.load()

    def test_finding_document_with_wrong_field_set_is_rejected(self) -> None:
        broken = dict(FINDING_JSON_FIELDS)
        del broken["created_at"]
        self._write_raw(self._empty_payload(findings=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_evidence_link_document_with_wrong_field_set_is_rejected(self) -> None:
        broken = dict(EVIDENCE_LINK_JSON_FIELDS)
        del broken["recorded_at"]
        self._write_raw(
            self._empty_payload(findings=[FINDING_JSON_FIELDS], evidence_links=[broken])
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_status_transition_document_with_wrong_field_set_is_rejected(self) -> None:
        broken = dict(STATUS_TRANSITION_JSON_FIELDS)
        del broken["reason"]
        self._write_raw(
            self._empty_payload(
                findings=[FINDING_JSON_FIELDS], status_transitions=[broken]
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_finding_id_in_persisted_content_is_rejected(self) -> None:
        self._write_raw(
            self._empty_payload(
                findings=[FINDING_JSON_FIELDS, dict(FINDING_JSON_FIELDS)]
            )
        )
        with self.assertRaisesRegex(ResearchError, "duplicate finding IDs"):
            self.store.load()

    def test_too_many_persisted_findings_is_rejected(self) -> None:
        with patch(
            "research.JsonFileResearchSecurityFindingStore.MAX_SECURITY_FINDINGS",
            1,
        ):
            self._write_raw(
                self._empty_payload(findings=[FINDING_JSON_FIELDS, FINDING_JSON_FIELDS])
            )
            with self.assertRaisesRegex(ResearchError, "too many records"):
                self.store.load()

    def test_naive_timestamp_in_persisted_content_fails_closed(self) -> None:
        broken = dict(FINDING_JSON_FIELDS)
        broken["created_at"] = "2026-09-26T10:00:00"
        self._write_raw(self._empty_payload(findings=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_invalid_enum_values_are_rejected(self) -> None:
        for field, value in (
            ("finding_kind", "not-a-kind"),
            ("subject_kind", "url"),
            ("origin", "model_authored"),
        ):
            with self.subTest(field=field):
                broken = dict(FINDING_JSON_FIELDS)
                broken[field] = value
                self._write_raw(self._empty_payload(findings=[broken]))
                with self.assertRaises(ResearchError):
                    self.store.load()

    def test_oversized_store_is_rejected(self) -> None:
        module = "research.JsonFileResearchSecurityFindingStore"
        with patch(f"{module}.MAX_SECURITY_FINDING_STORE_BYTES", 10):
            self._write_raw(self._empty_payload())
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.load()

    def test_a_persisted_non_canonical_subject_value_fails_closed(self) -> None:
        broken = dict(FINDING_JSON_FIELDS)
        broken["subject_canonical_value"] = "EXAMPLE.TEST."
        self._write_raw(self._empty_payload(findings=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_secret_shaped_persisted_title_fails_closed_on_load(self) -> None:
        broken = dict(FINDING_JSON_FIELDS)
        broken["title"] = "Authorization: Bearer distinct-store-secret-sentinel"
        self._write_raw(self._empty_payload(findings=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_secret_shaped_persisted_status_reason_fails_closed_on_load(self) -> None:
        broken_reason = dict(STATUS_TRANSITION_JSON_FIELDS)
        broken_reason["reason"] = "password=distinct-store-secret-sentinel"
        self._write_raw(
            self._empty_payload(
                findings=[FINDING_JSON_FIELDS],
                status_transitions=[broken_reason],
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_malformed_http_evidence_id_in_persisted_link_fails_closed(self) -> None:
        broken = dict(EVIDENCE_LINK_JSON_FIELDS)
        broken["evidence_id"] = "not-a-real-evidence-id"
        self._write_raw(
            self._empty_payload(findings=[FINDING_JSON_FIELDS], evidence_links=[broken])
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_status_without_a_reference_fails_closed_on_load(self) -> None:
        broken = dict(STATUS_TRANSITION_JSON_FIELDS)
        broken["status"] = "duplicate"
        self._write_raw(
            self._empty_payload(
                findings=[FINDING_JSON_FIELDS], status_transitions=[broken]
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_hand_tampered_dangling_duplicate_of_reference_fails_closed_on_load(
        self,
    ) -> None:
        broken = dict(STATUS_TRANSITION_JSON_FIELDS)
        broken["status"] = "duplicate"
        broken["duplicate_of_finding_id"] = "ghost-finding-999"
        self._write_raw(
            self._empty_payload(
                findings=[FINDING_JSON_FIELDS], status_transitions=[broken]
            )
        )
        with self.assertRaisesRegex(
            ResearchError, "duplicate-of reference must name a recorded finding"
        ):
            self.store.load()

    def test_a_hand_tampered_illegal_status_sequence_fails_closed_on_load(
        self,
    ) -> None:
        first = dict(STATUS_TRANSITION_JSON_FIELDS)
        first["transition_id"] = "transition-1"
        first["status"] = "validation_required"
        second = dict(STATUS_TRANSITION_JSON_FIELDS)
        second["transition_id"] = "transition-2"
        second["status"] = "validation_required"
        self._write_raw(
            self._empty_payload(
                findings=[FINDING_JSON_FIELDS], status_transitions=[first, second]
            )
        )
        with self.assertRaisesRegex(ResearchError, "not a legal sequence"):
            self.store.load()

    def test_the_declared_ceilings_are_the_reviewed_values(self) -> None:
        self.assertEqual(MAX_SECURITY_FINDINGS, 5_000)
        self.assertEqual(MAX_SECURITY_FINDING_EVIDENCE_LINKS, 5_000)
        self.assertEqual(MAX_SECURITY_FINDING_STATUS_TRANSITIONS, 5_000)


if __name__ == "__main__":
    unittest.main()
