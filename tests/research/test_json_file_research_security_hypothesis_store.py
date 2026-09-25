"""Persistence tests for the atomic, append-only security hypothesis JSON store."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchSecurityHypothesisStore import (
    MAX_SECURITY_HYPOTHESES,
    MAX_SECURITY_HYPOTHESIS_EVIDENCE_LINKS,
    MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITIONS,
    JsonFileResearchSecurityHypothesisStore,
    ResearchSecurityHypothesisDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
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
from research.ResearchSecurityHypothesisRecord import ResearchSecurityHypothesisRecord
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from research.ResearchSecurityHypothesisStatusTransitionRecord import (
    ResearchSecurityHypothesisStatusTransitionRecord,
)

RECORDED = datetime(2026, 9, 25, 10, tzinfo=UTC)


def hypothesis_record(
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    subject_value: str = "example.test",
) -> ResearchSecurityHypothesisRecord:
    return ResearchSecurityHypothesisRecord(
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        hypothesis_kind=ResearchSecurityHypothesisKind.AUTHORIZATION,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=canonicalize_asset_value(
            ResearchAssetKind.HOSTNAME, subject_value
        ),
        statement="An operator-authored conjecture about this subject.",
        rationale="A description of the evidence that suggests it.",
        required_validation="A description of what would still need testing.",
        origin=ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
    )


def evidence_link(
    link_id: str = "link-1",
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    evidence_id: str = "a" * 64,
) -> ResearchSecurityHypothesisEvidenceLinkRecord:
    return ResearchSecurityHypothesisEvidenceLinkRecord(
        link_id=link_id,
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityHypothesisEvidenceKind.HTTP_EVIDENCE,
        evidence_id=evidence_id,
        relation=ResearchSecurityHypothesisEvidenceRelation.SUPPORTS,
        recorded_at=RECORDED,
    )


def status_transition(
    transition_id: str = "transition-1",
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
) -> ResearchSecurityHypothesisStatusTransitionRecord:
    return ResearchSecurityHypothesisStatusTransitionRecord(
        transition_id=transition_id,
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        status=ResearchSecurityHypothesisStatus.NEEDS_EVIDENCE,
        reason="",
        recorded_at=RECORDED,
    )


HYPOTHESIS_JSON_FIELDS = {
    "hypothesis_id": "hypothesis-1",
    "program_id": "program-a",
    "hypothesis_kind": "authorization",
    "subject_kind": "hostname",
    "subject_canonical_value": "example.test",
    "statement": "statement",
    "rationale": "rationale",
    "required_validation": "required validation",
    "origin": "operator_authored",
    "created_at": RECORDED.isoformat(),
}

EVIDENCE_LINK_JSON_FIELDS = {
    "link_id": "link-1",
    "hypothesis_id": "hypothesis-1",
    "program_id": "program-a",
    "evidence_kind": "http_evidence",
    "evidence_id": "a" * 64,
    "relation": "supports",
    "recorded_at": RECORDED.isoformat(),
}

STATUS_TRANSITION_JSON_FIELDS = {
    "transition_id": "transition-1",
    "hypothesis_id": "hypothesis-1",
    "program_id": "program-a",
    "status": "needs_evidence",
    "reason": "",
    "recorded_at": RECORDED.isoformat(),
}


class ResearchSecurityHypothesisDocumentTests(unittest.TestCase):
    def test_default_document_is_empty(self) -> None:
        document = ResearchSecurityHypothesisDocument()
        self.assertEqual(document.hypotheses, ())
        self.assertEqual(document.evidence_links, ())
        self.assertEqual(document.status_transitions, ())

    def test_duplicate_hypothesis_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ResearchError, "duplicate hypothesis IDs"):
            ResearchSecurityHypothesisDocument(
                hypotheses=(
                    hypothesis_record(hypothesis_id="h1"),
                    hypothesis_record(hypothesis_id="h1", subject_value="other.test"),
                )
            )

    def test_duplicate_evidence_link_ids_are_rejected(self) -> None:
        record = hypothesis_record()
        with self.assertRaisesRegex(ResearchError, "duplicate evidence link IDs"):
            ResearchSecurityHypothesisDocument(
                hypotheses=(record,),
                evidence_links=(
                    evidence_link(link_id="link-1"),
                    evidence_link(link_id="link-1", evidence_id="b" * 64),
                ),
            )

    def test_duplicate_status_transition_ids_are_rejected(self) -> None:
        record = hypothesis_record()
        with self.assertRaisesRegex(ResearchError, "duplicate status transition IDs"):
            ResearchSecurityHypothesisDocument(
                hypotheses=(record,),
                status_transitions=(
                    status_transition(transition_id="t1"),
                    status_transition(transition_id="t1"),
                ),
            )

    def test_evidence_link_must_reference_a_recorded_hypothesis(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "must reference a recorded hypothesis"
        ):
            ResearchSecurityHypothesisDocument(evidence_links=(evidence_link(),))

    def test_evidence_link_cannot_reference_a_hypothesis_in_another_program(
        self,
    ) -> None:
        record = hypothesis_record(program_id="program-a")
        link = evidence_link(program_id="program-b")
        with self.assertRaisesRegex(
            ResearchError, "must reference a recorded hypothesis"
        ):
            ResearchSecurityHypothesisDocument(
                hypotheses=(record,), evidence_links=(link,)
            )

    def test_status_transition_must_reference_a_recorded_hypothesis(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "must reference a recorded hypothesis"
        ):
            ResearchSecurityHypothesisDocument(
                status_transitions=(status_transition(),)
            )

    def test_non_tuple_or_wrong_typed_members_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSecurityHypothesisDocument(hypotheses=[hypothesis_record()])  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchSecurityHypothesisDocument(hypotheses=("not-a-record",))  # type: ignore[arg-type]
        record = hypothesis_record()
        with self.assertRaises(ResearchError):
            ResearchSecurityHypothesisDocument(
                hypotheses=(record,), evidence_links=["not-a-tuple-member"]  # type: ignore[arg-type]
            )

    def test_bounded_counts_are_enforced(self) -> None:
        module = "research.JsonFileResearchSecurityHypothesisStore"
        with patch(f"{module}.MAX_SECURITY_HYPOTHESES", 1):
            with self.assertRaisesRegex(ResearchError, "too many records"):
                ResearchSecurityHypothesisDocument(
                    hypotheses=(
                        hypothesis_record(hypothesis_id="h1"),
                        hypothesis_record(hypothesis_id="h2", subject_value="b.test"),
                    )
                )
        record = hypothesis_record()
        with patch(f"{module}.MAX_SECURITY_HYPOTHESIS_EVIDENCE_LINKS", 1):
            with self.assertRaisesRegex(ResearchError, "too many evidence links"):
                ResearchSecurityHypothesisDocument(
                    hypotheses=(record,),
                    evidence_links=(
                        evidence_link(link_id="l1"),
                        evidence_link(link_id="l2", evidence_id="b" * 64),
                    ),
                )
        with patch(f"{module}.MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITIONS", 1):
            with self.assertRaisesRegex(ResearchError, "too many status transitions"):
                ResearchSecurityHypothesisDocument(
                    hypotheses=(record,),
                    status_transitions=(
                        status_transition(transition_id="t1"),
                        status_transition(transition_id="t2"),
                    ),
                )


class JsonFileResearchSecurityHypothesisStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "security_hypotheses.json"
        self.store = JsonFileResearchSecurityHypothesisStore(self.path)

    def test_loading_an_absent_file_returns_an_empty_document(self) -> None:
        document = self.store.load()
        self.assertEqual(document, ResearchSecurityHypothesisDocument())
        self.assertFalse(self.path.exists())

    def test_round_trip_preserves_every_record_kind(self) -> None:
        record = hypothesis_record()
        link = evidence_link()
        transition = status_transition()
        document = ResearchSecurityHypothesisDocument(
            hypotheses=(record,),
            evidence_links=(link,),
            status_transitions=(transition,),
        )

        self.store.save(document)
        reloaded = self.store.load()

        self.assertEqual(reloaded, document)

    def test_saving_twice_appends_to_the_existing_document(self) -> None:
        original = ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),))
        self.store.save(original)
        appended = ResearchSecurityHypothesisDocument(
            hypotheses=(
                *original.hypotheses,
                hypothesis_record(hypothesis_id="h2", subject_value="other.test"),
            )
        )

        self.store.save(appended)

        self.assertEqual(self.store.load(), appended)

    def test_save_rejects_removal_or_replacement_of_existing_records(self) -> None:
        original = ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),))
        self.store.save(original)
        replacement = ResearchSecurityHypothesisDocument(
            hypotheses=(
                hypothesis_record(hypothesis_id="h2", subject_value="other.test"),
            )
        )

        with self.assertRaisesRegex(ResearchError, "append-only"):
            self.store.save(replacement)

        self.assertEqual(self.store.load(), original)

    def test_save_rejects_anything_other_than_a_document(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save({"hypotheses": []})  # type: ignore[arg-type]

    def test_no_temporary_file_is_left_behind_after_a_clean_save(self) -> None:
        self.store.save(
            ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),))
        )
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    # -- malformed persisted content fails closed ---------------------------

    def _write_raw(self, payload: object) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def _empty_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 1,
            "hypotheses": [],
            "evidence_links": [],
            "status_transitions": [],
        }
        payload.update(overrides)
        return payload

    def test_non_dict_document_is_rejected(self) -> None:
        self._write_raw([])
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_wrong_field_set_is_rejected(self) -> None:
        self._write_raw({"schema_version": 1, "hypotheses": []})
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
        for field in ("hypotheses", "evidence_links", "status_transitions"):
            with self.subTest(field=field):
                self._write_raw(self._empty_payload(**{field: "not-a-list"}))
                with self.assertRaisesRegex(ResearchError, "must be a list"):
                    self.store.load()

    def test_hypothesis_document_with_wrong_field_set_is_rejected(self) -> None:
        broken = dict(HYPOTHESIS_JSON_FIELDS)
        del broken["created_at"]
        self._write_raw(self._empty_payload(hypotheses=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_evidence_link_document_with_wrong_field_set_is_rejected(self) -> None:
        broken = dict(EVIDENCE_LINK_JSON_FIELDS)
        del broken["recorded_at"]
        self._write_raw(
            self._empty_payload(
                hypotheses=[HYPOTHESIS_JSON_FIELDS], evidence_links=[broken]
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_status_transition_document_with_wrong_field_set_is_rejected(self) -> None:
        broken = dict(STATUS_TRANSITION_JSON_FIELDS)
        del broken["reason"]
        self._write_raw(
            self._empty_payload(
                hypotheses=[HYPOTHESIS_JSON_FIELDS], status_transitions=[broken]
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_hypothesis_id_in_persisted_content_is_rejected(self) -> None:
        self._write_raw(
            self._empty_payload(
                hypotheses=[HYPOTHESIS_JSON_FIELDS, dict(HYPOTHESIS_JSON_FIELDS)]
            )
        )
        with self.assertRaisesRegex(ResearchError, "duplicate hypothesis IDs"):
            self.store.load()

    def test_too_many_persisted_hypotheses_is_rejected(self) -> None:
        with patch(
            "research.JsonFileResearchSecurityHypothesisStore.MAX_SECURITY_HYPOTHESES",
            1,
        ):
            self._write_raw(
                self._empty_payload(
                    hypotheses=[HYPOTHESIS_JSON_FIELDS, HYPOTHESIS_JSON_FIELDS]
                )
            )
            with self.assertRaisesRegex(ResearchError, "too many records"):
                self.store.load()

    def test_naive_timestamp_in_persisted_content_fails_closed(self) -> None:
        broken = dict(HYPOTHESIS_JSON_FIELDS)
        broken["created_at"] = "2026-09-25T10:00:00"
        self._write_raw(self._empty_payload(hypotheses=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_invalid_enum_values_are_rejected(self) -> None:
        for field, value in (
            ("hypothesis_kind", "not-a-kind"),
            ("subject_kind", "url"),
            ("origin", "model_authored"),
        ):
            with self.subTest(field=field):
                broken = dict(HYPOTHESIS_JSON_FIELDS)
                broken[field] = value
                self._write_raw(self._empty_payload(hypotheses=[broken]))
                with self.assertRaises(ResearchError):
                    self.store.load()

    def test_oversized_store_is_rejected(self) -> None:
        module = "research.JsonFileResearchSecurityHypothesisStore"
        with patch(f"{module}.MAX_SECURITY_HYPOTHESIS_STORE_BYTES", 10):
            self._write_raw(self._empty_payload())
            with self.assertRaisesRegex(ResearchError, "too large"):
                self.store.load()

    def test_a_persisted_non_canonical_subject_value_fails_closed(self) -> None:
        broken = dict(HYPOTHESIS_JSON_FIELDS)
        broken["subject_canonical_value"] = "EXAMPLE.TEST."
        self._write_raw(self._empty_payload(hypotheses=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_secret_shaped_persisted_statement_fails_closed_on_load(self) -> None:
        broken = dict(HYPOTHESIS_JSON_FIELDS)
        broken["statement"] = "Authorization: Bearer distinct-store-secret-sentinel"
        self._write_raw(self._empty_payload(hypotheses=[broken]))
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_secret_shaped_persisted_status_reason_fails_closed_on_load(self) -> None:
        broken_reason = dict(STATUS_TRANSITION_JSON_FIELDS)
        broken_reason["reason"] = "password=distinct-store-secret-sentinel"
        self._write_raw(
            self._empty_payload(
                hypotheses=[HYPOTHESIS_JSON_FIELDS],
                status_transitions=[broken_reason],
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_malformed_http_evidence_id_in_persisted_link_fails_closed(self) -> None:
        broken = dict(EVIDENCE_LINK_JSON_FIELDS)
        broken["evidence_id"] = "not-a-real-evidence-id"
        self._write_raw(
            self._empty_payload(
                hypotheses=[HYPOTHESIS_JSON_FIELDS], evidence_links=[broken]
            )
        )
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_the_declared_ceilings_are_the_reviewed_values(self) -> None:
        self.assertEqual(MAX_SECURITY_HYPOTHESES, 5_000)
        self.assertEqual(MAX_SECURITY_HYPOTHESIS_EVIDENCE_LINKS, 5_000)
        self.assertEqual(MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITIONS, 5_000)


if __name__ == "__main__":
    unittest.main()
