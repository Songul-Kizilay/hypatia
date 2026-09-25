"""Atomic file persistence for the append-only HTTP evidence log.

Schema version 1 (a new store, no legacy version to carry). Modeled directly
on `JsonFileResearchAssetInventoryStore`'s flat-list shape: strict field-set
validation, bounded record count/size ceilings, duplicate-`evidence_id`
refusal at document-validation time (defense in depth — the application
service is what makes replay idempotent by returning the existing record
instead of writing a second one), atomic temp-file-then-`os.replace` write.
This store never mutates a previously saved record in place; `save` only ever
replaces the whole list with one that is a superset of what was already
persisted (append-only by construction, matching the asset inventory store).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchHttpHeaderRecord import ResearchHttpHeaderRecord

MAX_HTTP_EVIDENCE_STORE_BYTES = 4 * 1024 * 1024
MAX_HTTP_EVIDENCE_RECORDS = 5_000

_SCHEMA_VERSION = 1
_SUPPORTED_SCHEMA_VERSIONS = frozenset({_SCHEMA_VERSION})
_DOCUMENT_FIELDS = frozenset({"schema_version", "records"})
_HEADER_FIELDS = frozenset({"name", "value"})
_RECORD_FIELDS = frozenset(
    {
        "evidence_id",
        "program_id",
        "target_kind",
        "target_canonical_value",
        "scheme",
        "port",
        "path",
        "request_method",
        "request_headers_observed",
        "response_status_code",
        "response_headers",
        "response_body_observed",
        "provenance",
        "source_operation_digest",
        "recorded_at",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchHttpEvidenceDocument:
    """The complete, flat, append-only HTTP evidence log for every program."""

    records: tuple[ResearchHttpEvidenceRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple) or any(
            not isinstance(value, ResearchHttpEvidenceRecord) for value in self.records
        ):
            raise ResearchError("HTTP evidence records are invalid.")
        if len(self.records) > MAX_HTTP_EVIDENCE_RECORDS:
            raise ResearchError("The HTTP evidence store has too many records.")
        evidence_ids = [value.evidence_id for value in self.records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ResearchError("The HTTP evidence store has duplicate evidence IDs.")


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    """Stop temporary JSON output before its UTF-8 byte budget is exceeded."""

    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        encoded_size = len(encoded)
        if self._byte_count + encoded_size > MAX_HTTP_EVIDENCE_STORE_BYTES:
            raise OverflowError("HTTP evidence store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("HTTP evidence store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchHttpEvidenceStore:
    """Load and atomically replace the complete HTTP evidence document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchHttpEvidenceDocument:
        """Return the validated document, or an empty one when absent."""
        if not self._path.exists():
            return ResearchHttpEvidenceDocument()
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_HTTP_EVIDENCE_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the HTTP evidence store.") from error
        if len(encoded_document) > MAX_HTTP_EVIDENCE_STORE_BYTES:
            raise ResearchError("The HTTP evidence store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the HTTP evidence store.") from error
        return self._parse_document(document)

    def save(self, document: ResearchHttpEvidenceDocument) -> None:
        """Atomically append validated records without rewriting history."""
        if not isinstance(document, ResearchHttpEvidenceDocument):
            raise ResearchError("The HTTP evidence store accepts only a document.")
        existing = self.load()
        if document.records[: len(existing.records)] != existing.records:
            raise ResearchError(
                "HTTP evidence records are append-only and cannot be replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "records": [self._serialize_record(value) for value in document.records],
        }
        temporary_path: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                bounded_file = _BoundedUtf8Writer(file)
                json.dump(encoded, bounded_file, ensure_ascii=False, indent=2)
                bounded_file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except OverflowError as error:
            raise ResearchError("The HTTP evidence store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the HTTP evidence store.") from error
        finally:
            self._remove_temporary_file(temporary_path)

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _serialize_record(record: ResearchHttpEvidenceRecord) -> dict[str, Any]:
        return {
            "evidence_id": record.evidence_id,
            "program_id": record.program_id,
            "target_kind": record.target_kind.value,
            "target_canonical_value": record.target_canonical_value,
            "scheme": record.scheme,
            "port": record.port,
            "path": record.path,
            "request_method": record.request_method,
            "request_headers_observed": record.request_headers_observed,
            "response_status_code": record.response_status_code,
            "response_headers": [
                {"name": header.name, "value": header.value}
                for header in record.response_headers
            ],
            "response_body_observed": record.response_body_observed,
            "provenance": record.provenance.value,
            "source_operation_digest": record.source_operation_digest,
            "recorded_at": record.recorded_at.isoformat(),
        }

    def _parse_document(self, document: object) -> ResearchHttpEvidenceDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The HTTP evidence document is invalid.")
        schema_version = document["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version not in _SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ResearchError(
                "The HTTP evidence store schema version is not supported."
            )
        records_value = document["records"]
        if not isinstance(records_value, list):
            raise ResearchError("HTTP evidence records must be a list.")
        if len(records_value) > MAX_HTTP_EVIDENCE_RECORDS:
            raise ResearchError("The HTTP evidence store has too many records.")
        records = tuple(self._parse_record(value) for value in records_value)
        return ResearchHttpEvidenceDocument(records=records)

    @staticmethod
    def _parse_record(document: object) -> ResearchHttpEvidenceRecord:
        if not isinstance(document, dict) or set(document) != _RECORD_FIELDS:
            raise ResearchError("An HTTP evidence record document is invalid.")
        store = JsonFileResearchHttpEvidenceStore
        return ResearchHttpEvidenceRecord(
            evidence_id=store._text(document["evidence_id"]),
            program_id=store._text(document["program_id"]),
            target_kind=store._asset_kind(document["target_kind"]),
            target_canonical_value=store._text(document["target_canonical_value"]),
            scheme=store._text(document["scheme"]),
            port=store._int(document["port"]),
            path=store._text(document["path"]),
            request_method=store._text(document["request_method"]),
            request_headers_observed=store._bool(document["request_headers_observed"]),
            response_status_code=store._optional_int(document["response_status_code"]),
            response_headers=tuple(
                store._parse_header(value)
                for value in store._list(document["response_headers"])
            ),
            response_body_observed=store._bool(document["response_body_observed"]),
            provenance=store._provenance(document["provenance"]),
            source_operation_digest=store._text(document["source_operation_digest"]),
            recorded_at=store._timestamp(document["recorded_at"]),
        )

    @staticmethod
    def _parse_header(document: object) -> ResearchHttpHeaderRecord:
        if not isinstance(document, dict) or set(document) != _HEADER_FIELDS:
            raise ResearchError("An HTTP evidence header document is invalid.")
        store = JsonFileResearchHttpEvidenceStore
        return ResearchHttpHeaderRecord(
            name=store._text(document["name"]),
            value=store._optional_text(document["value"]),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("An HTTP evidence identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("An HTTP evidence text field is invalid.")
        return value

    @staticmethod
    def _list(value: object) -> list[Any]:
        if not isinstance(value, list):
            raise ResearchError("An HTTP evidence list field is invalid.")
        return value

    @staticmethod
    def _bool(value: object) -> bool:
        if not isinstance(value, bool):
            raise ResearchError("An HTTP evidence boolean field is invalid.")
        return value

    @staticmethod
    def _int(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ResearchError("An HTTP evidence integer field is invalid.")
        return value

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ResearchError("An HTTP evidence integer field is invalid.")
        return value

    @staticmethod
    def _asset_kind(value: object) -> ResearchAssetKind:
        if not isinstance(value, str):
            raise ResearchError("An HTTP evidence target kind is invalid.")
        try:
            return ResearchAssetKind(value)
        except ValueError as error:
            raise ResearchError("An HTTP evidence target kind is invalid.") from error

    @staticmethod
    def _provenance(value: object) -> ResearchHttpEvidenceProvenanceKind:
        if not isinstance(value, str):
            raise ResearchError("An HTTP evidence provenance is invalid.")
        try:
            return ResearchHttpEvidenceProvenanceKind(value)
        except ValueError as error:
            raise ResearchError("An HTTP evidence provenance is invalid.") from error

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("An HTTP evidence timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("An HTTP evidence timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("An HTTP evidence timestamp must be timezone-aware.")
        return parsed
