"""Fail-closed invariants for the HTTP evidence ingestion preview/result types."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceIngestion import (
    ResearchHttpEvidenceIngestionPreview,
    ResearchHttpEvidenceIngestionResult,
)
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import (
    ResearchHttpEvidenceRecord,
    http_evidence_id,
)
from research.ResearchHttpHeaderRecord import ResearchHttpHeaderRecord

RECORDED = datetime(2026, 9, 24, 10, tzinfo=UTC)
OPERATION_DIGEST = "a" * 64


def make_evidence_id(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "program_id": "program-a",
        "operation_digest": OPERATION_DIGEST,
        "exit_code": 0,
        "timed_out": False,
        "stdout_lines": ("HTTP/1.1 200 OK",),
    }
    kwargs.update(overrides)
    return http_evidence_id(**kwargs)  # type: ignore[arg-type]


def make_record() -> ResearchHttpEvidenceRecord:
    return ResearchHttpEvidenceRecord(
        evidence_id=make_evidence_id(),
        program_id="program-a",
        target_kind=ResearchAssetKind.HOSTNAME,
        target_canonical_value="www.example.test",
        scheme="https",
        port=443,
        path="/",
        request_method="HEAD",
        request_headers_observed=False,
        response_status_code=200,
        response_headers=(
            ResearchHttpHeaderRecord(name="Content-Type", value="text/html"),
        ),
        response_body_observed=False,
        provenance=ResearchHttpEvidenceProvenanceKind.KALI_OPERATION_RESULT,
        source_operation_digest=OPERATION_DIGEST,
        recorded_at=RECORDED,
    )


def make_scope() -> ResearchAssetScopeResolutionView:
    return ResearchAssetScopeResolutionView(
        has_active_scope_revision=False, resolution=None
    )


def make_preview(**overrides: object) -> ResearchHttpEvidenceIngestionPreview:
    kwargs: dict[str, object] = {
        "program_id": "program-a",
        "operation_digest": OPERATION_DIGEST,
        "evidence_id": make_evidence_id(),
        "hostname": "www.example.test",
        "status_code": 200,
        "headers": (ResearchHttpHeaderRecord(name="Content-Type", value="text/html"),),
        "rejected_lines": (),
        "already_recorded": False,
        "scope": make_scope(),
    }
    kwargs.update(overrides)
    return ResearchHttpEvidenceIngestionPreview(**kwargs)  # type: ignore[arg-type]


class PreviewTests(unittest.TestCase):
    def test_a_valid_preview_constructs(self) -> None:
        preview = make_preview()

        self.assertFalse(preview.evidence_recorded)
        self.assertFalse(preview.already_recorded)

    def test_evidence_recorded_cannot_be_forced_true(self) -> None:
        with self.assertRaises(ResearchError):
            make_preview(evidence_recorded=True)

    def test_an_invalid_operation_digest_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            make_preview(operation_digest="not-a-digest")

    def test_an_invalid_evidence_id_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            make_preview(evidence_id="not-a-digest")

    def test_a_non_boolean_already_recorded_flag_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            make_preview(already_recorded="yes")

    def test_a_non_scope_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            make_preview(scope="not-a-scope")


class ResultTests(unittest.TestCase):
    def test_a_valid_result_constructs(self) -> None:
        result = ResearchHttpEvidenceIngestionResult(
            record=make_record(), already_recorded=False, scope=make_scope()
        )

        self.assertFalse(result.already_recorded)

    def test_a_non_record_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpEvidenceIngestionResult(
                record="not-a-record",  # type: ignore[arg-type]
                already_recorded=False,
                scope=make_scope(),
            )

    def test_a_non_boolean_already_recorded_flag_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpEvidenceIngestionResult(
                record=make_record(),
                already_recorded="yes",  # type: ignore[arg-type]
                scope=make_scope(),
            )

    def test_a_non_scope_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchHttpEvidenceIngestionResult(
                record=make_record(),
                already_recorded=False,
                scope="not-a-scope",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
