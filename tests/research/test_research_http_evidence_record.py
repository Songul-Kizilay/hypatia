"""Fail-closed invariants for `ResearchHttpEvidenceRecord` and `http_evidence_id`."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import (
    ResearchHttpEvidenceRecord,
    http_evidence_id,
    is_http_evidence_id,
)
from research.ResearchHttpHeaderRecord import ResearchHttpHeaderRecord

RECORDED = datetime(2026, 9, 24, 10, tzinfo=UTC)
OPERATION_DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


def evidence_id(**overrides: object) -> str:
    kwargs = {
        "program_id": "program-a",
        "operation_digest": OPERATION_DIGEST,
        "exit_code": 0,
        "timed_out": False,
        "stdout_lines": ("HTTP/1.1 200 OK",),
    }
    kwargs.update(overrides)
    return http_evidence_id(**kwargs)  # type: ignore[arg-type]


def record(**overrides: object) -> ResearchHttpEvidenceRecord:
    kwargs: dict[str, object] = {
        "evidence_id": evidence_id(),
        "program_id": "program-a",
        "target_kind": ResearchAssetKind.HOSTNAME,
        "target_canonical_value": "www.example.test",
        "scheme": "https",
        "port": 443,
        "path": "/",
        "request_method": "HEAD",
        "request_headers_observed": False,
        "response_status_code": 200,
        "response_headers": (
            ResearchHttpHeaderRecord(name="Content-Type", value="text/html"),
        ),
        "response_body_observed": False,
        "provenance": ResearchHttpEvidenceProvenanceKind.KALI_OPERATION_RESULT,
        "source_operation_digest": OPERATION_DIGEST,
        "recorded_at": RECORDED,
    }
    kwargs.update(overrides)
    return ResearchHttpEvidenceRecord(**kwargs)  # type: ignore[arg-type]


class ValidConstructionTests(unittest.TestCase):
    def test_a_successful_result_round_trips(self) -> None:
        evidence = record()

        self.assertEqual(evidence.target_canonical_value, "www.example.test")
        self.assertEqual(evidence.response_status_code, 200)
        self.assertFalse(evidence.request_headers_observed)
        self.assertFalse(evidence.response_body_observed)

    def test_an_unsuccessful_result_carries_no_status_or_headers(self) -> None:
        evidence = record(
            evidence_id=evidence_id(exit_code=1),
            response_status_code=None,
            response_headers=(),
        )

        self.assertIsNone(evidence.response_status_code)
        self.assertEqual(evidence.response_headers, ())


class MalformedFieldRejectionTests(unittest.TestCase):
    def test_a_random_evidence_id_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(evidence_id="not-a-digest")

    def test_a_non_hostname_target_kind_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(target_kind=ResearchAssetKind.IP_ADDRESS)

    def test_a_non_canonical_hostname_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(target_canonical_value="WWW.Example.TEST")

    def test_a_non_https_scheme_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(scheme="http")

    def test_a_non_443_port_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(port=80)

    def test_a_non_root_path_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(path="/status")

    def test_a_non_head_method_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(request_method="GET")

    def test_request_headers_observed_cannot_be_true(self) -> None:
        with self.assertRaises(ResearchError):
            record(request_headers_observed=True)

    def test_response_body_observed_cannot_be_true(self) -> None:
        with self.assertRaises(ResearchError):
            record(response_body_observed=True)

    def test_an_out_of_range_status_code_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(response_status_code=999999)

    def test_headers_without_an_observed_status_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(
                evidence_id=evidence_id(exit_code=1),
                response_status_code=None,
                response_headers=(ResearchHttpHeaderRecord(name="X-Foo", value="1"),),
            )

    def test_an_invalid_source_operation_digest_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(source_operation_digest="not-a-digest")

    def test_a_non_provenance_value_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(provenance="kali_operation_result")

    def test_a_naive_datetime_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            record(recorded_at=datetime(2026, 9, 24, 10))


class ImmutabilityTests(unittest.TestCase):
    def test_the_record_is_frozen(self) -> None:
        evidence = record()

        with self.assertRaises(FrozenInstanceError):
            evidence.response_status_code = 404  # type: ignore[misc]


class EvidenceIdDeterminismTests(unittest.TestCase):
    def test_identical_inputs_yield_the_same_id(self) -> None:
        first = evidence_id()
        second = evidence_id()

        self.assertEqual(first, second)
        self.assertTrue(is_http_evidence_id(first))

    def test_a_different_program_id_yields_a_different_id(self) -> None:
        self.assertNotEqual(evidence_id(), evidence_id(program_id="program-b"))

    def test_a_different_operation_digest_yields_a_different_id(self) -> None:
        self.assertNotEqual(evidence_id(), evidence_id(operation_digest=OTHER_DIGEST))

    def test_a_different_exit_code_yields_a_different_id(self) -> None:
        self.assertNotEqual(evidence_id(), evidence_id(exit_code=1))

    def test_a_different_timeout_flag_yields_a_different_id(self) -> None:
        self.assertNotEqual(evidence_id(), evidence_id(timed_out=True))

    def test_different_stdout_lines_yield_a_different_id(self) -> None:
        self.assertNotEqual(
            evidence_id(),
            evidence_id(stdout_lines=("HTTP/1.1 404 Not Found",)),
        )

    def test_is_http_evidence_id_rejects_non_digest_values(self) -> None:
        self.assertFalse(is_http_evidence_id("not-a-digest"))
        self.assertFalse(is_http_evidence_id(123))
        self.assertFalse(is_http_evidence_id(None))


if __name__ == "__main__":
    unittest.main()
