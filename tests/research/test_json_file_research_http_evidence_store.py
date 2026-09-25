"""Persistence tests for the atomic, append-only HTTP evidence JSON store."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import (
    JsonFileResearchHttpEvidenceStore,
    ResearchHttpEvidenceDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
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


def evidence(
    *,
    program_id: str = "program-a",
    hostname: str = "www.example.test",
    status_code: int | None = 200,
    headers: tuple[ResearchHttpHeaderRecord, ...] = (
        ResearchHttpHeaderRecord(name="Content-Type", value="text/html"),
    ),
    stdout_lines: tuple[str, ...] = ("HTTP/1.1 200 OK",),
    exit_code: int = 0,
    timed_out: bool = False,
    operation_digest: str = OPERATION_DIGEST,
) -> ResearchHttpEvidenceRecord:
    identity = http_evidence_id(
        program_id=program_id,
        operation_digest=operation_digest,
        exit_code=exit_code,
        timed_out=timed_out,
        stdout_lines=stdout_lines,
    )
    return ResearchHttpEvidenceRecord(
        evidence_id=identity,
        program_id=program_id,
        target_kind=ResearchAssetKind.HOSTNAME,
        target_canonical_value=hostname,
        scheme="https",
        port=443,
        path="/",
        request_method="HEAD",
        request_headers_observed=False,
        response_status_code=status_code,
        response_headers=headers if status_code is not None else (),
        response_body_observed=False,
        provenance=ResearchHttpEvidenceProvenanceKind.KALI_OPERATION_RESULT,
        source_operation_digest=operation_digest,
        recorded_at=RECORDED,
    )


class ResearchHttpEvidenceDocumentTests(unittest.TestCase):
    def test_default_document_is_empty(self) -> None:
        document = ResearchHttpEvidenceDocument()
        self.assertEqual(document.records, ())

    def test_duplicate_evidence_ids_are_rejected(self) -> None:
        record = evidence()
        with self.assertRaisesRegex(ResearchError, "duplicate evidence IDs"):
            ResearchHttpEvidenceDocument(records=(record, record))


class RoundTripTests(unittest.TestCase):
    def test_save_then_load_preserves_provenance_and_digest_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            store = JsonFileResearchHttpEvidenceStore(path)
            record = evidence()

            store.save(ResearchHttpEvidenceDocument(records=(record,)))
            reloaded = store.load()

            self.assertEqual(reloaded.records, (record,))
            [loaded_record] = reloaded.records
            self.assertIs(
                loaded_record.provenance,
                ResearchHttpEvidenceProvenanceKind.KALI_OPERATION_RESULT,
            )
            self.assertEqual(loaded_record.source_operation_digest, OPERATION_DIGEST)

    def test_a_fresh_store_instance_at_the_same_path_sees_the_same_records(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            JsonFileResearchHttpEvidenceStore(path).save(
                ResearchHttpEvidenceDocument(records=(evidence(),))
            )

            reloaded = JsonFileResearchHttpEvidenceStore(path).load()

            self.assertEqual(len(reloaded.records), 1)

    def test_headers_and_duplicate_names_survive_reload_identically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            record = evidence(
                headers=(
                    ResearchHttpHeaderRecord(name="Set-Cookie", value="a=1"),
                    ResearchHttpHeaderRecord(name="Set-Cookie", value="b=2"),
                )
            )
            JsonFileResearchHttpEvidenceStore(path).save(
                ResearchHttpEvidenceDocument(records=(record,))
            )

            [reloaded] = JsonFileResearchHttpEvidenceStore(path).load().records

            self.assertEqual(len(reloaded.response_headers), 2)
            self.assertEqual(
                [header.value for header in reloaded.response_headers],
                ["a=1", "b=2"],
            )

    def test_an_unsuccessful_records_none_status_survives_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            record = evidence(status_code=None, exit_code=1)
            JsonFileResearchHttpEvidenceStore(path).save(
                ResearchHttpEvidenceDocument(records=(record,))
            )

            [reloaded] = JsonFileResearchHttpEvidenceStore(path).load().records

            self.assertIsNone(reloaded.response_status_code)
            self.assertEqual(reloaded.response_headers, ())


class AppendOnlyTests(unittest.TestCase):
    def test_replacing_a_previously_saved_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            store = JsonFileResearchHttpEvidenceStore(path)
            store.save(ResearchHttpEvidenceDocument(records=(evidence(),)))

            with self.assertRaisesRegex(ResearchError, "append-only"):
                store.save(ResearchHttpEvidenceDocument(records=()))

    def test_appending_a_second_record_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            store = JsonFileResearchHttpEvidenceStore(path)
            first = evidence()
            second = evidence(stdout_lines=("HTTP/1.1 404 Not Found",), status_code=404)
            store.save(ResearchHttpEvidenceDocument(records=(first,)))

            store.save(ResearchHttpEvidenceDocument(records=(first, second)))

            self.assertEqual(len(store.load().records), 2)


class DocumentValidationTests(unittest.TestCase):
    def test_an_unrecognised_field_set_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            path.write_text(json.dumps({"schema_version": 1, "unexpected": []}))

            with self.assertRaises(ResearchError):
                JsonFileResearchHttpEvidenceStore(path).load()

    def test_an_unsupported_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "http_evidence.json"
            path.write_text(json.dumps({"schema_version": 2, "records": []}))

            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchHttpEvidenceStore(path).load()

    def test_a_missing_file_loads_as_an_empty_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "does-not-exist.json"

            document = JsonFileResearchHttpEvidenceStore(path).load()

            self.assertEqual(document.records, ())


if __name__ == "__main__":
    unittest.main()
