"""Strict atomic JSON storage for bounded accepted research source text."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchSourceContentRecord import ResearchSourceContentRecord


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    """Write JSON text without exceeding its exact UTF-8 byte budget."""

    def __init__(self, stream: _BinaryWriter, maximum_bytes: int) -> None:
        self._stream = stream
        self._maximum_bytes = maximum_bytes
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        encoded_size = len(encoded)
        if self._byte_count + encoded_size > self._maximum_bytes:
            raise OverflowError("Research source content store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Research source content temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchSourceContentStore:
    """Persist a complete versioned content snapshot with integrity validation."""

    _SCHEMA_VERSION = 1
    _DOCUMENT_FIELDS = {"schema_version", "records"}
    _RECORD_FIELDS = {
        "document_id",
        "url",
        "title",
        "content",
        "content_type",
        "fetched_at",
        "stored_at",
        "content_byte_count",
        "content_sha256",
    }
    _MAXIMUM_RECORDS = 64
    _MAXIMUM_TOTAL_CONTENT_BYTES = 32_000_000
    _MAXIMUM_STORE_FILE_BYTES = 40_000_000

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchSourceContentRecord]:
        """Load a fully validated snapshot, or return empty when absent."""
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(self._MAXIMUM_STORE_FILE_BYTES + 1)
        except FileNotFoundError:
            return []
        except OSError as error:
            raise ResearchError(
                "Unable to read research source content store."
            ) from error
        if len(encoded_document) > self._MAXIMUM_STORE_FILE_BYTES:
            raise ResearchError("Research source content store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read research source content store."
            ) from error
        return self._parse_document(document)

    def save(self, records: list[ResearchSourceContentRecord]) -> None:
        """Atomically replace the complete content snapshot."""
        self._validate_records(records)
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "records": [self._serialize_record(record) for record in records],
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
                bounded_file = _BoundedUtf8Writer(
                    file,
                    self._MAXIMUM_STORE_FILE_BYTES,
                )
                json.dump(document, bounded_file, ensure_ascii=False, indent=2)
                bounded_file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
        except OverflowError as error:
            raise ResearchError(
                "Research source content store is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write research source content store."
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _parse_document(self, document: Any) -> list[ResearchSourceContentRecord]:
        if not isinstance(document, dict) or set(document) != self._DOCUMENT_FIELDS:
            raise ResearchError("Research source content store has invalid fields.")
        schema_version = document["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != self._SCHEMA_VERSION
        ):
            raise ResearchError(
                "Research source content store has an unsupported schema version."
            )
        records = document["records"]
        if not isinstance(records, list):
            raise ResearchError("Research source content store records must be a list.")
        parsed = [self._parse_record(value) for value in records]
        self._validate_records(parsed)
        return parsed

    def _parse_record(self, value: Any) -> ResearchSourceContentRecord:
        if not isinstance(value, dict) or set(value) != self._RECORD_FIELDS:
            raise ResearchError("Research source content store has an invalid record.")
        return ResearchSourceContentRecord(
            document_id=value["document_id"],
            url=value["url"],
            title=value["title"],
            content=value["content"],
            content_type=value["content_type"],
            fetched_at=self._parse_datetime(value["fetched_at"], "fetched_at"),
            stored_at=self._parse_datetime(value["stored_at"], "stored_at"),
            content_byte_count=value["content_byte_count"],
            content_sha256=value["content_sha256"],
        )

    @staticmethod
    def _parse_datetime(value: Any, label: str) -> datetime:
        if not isinstance(value, str):
            raise ResearchError(f"Research source content {label} must be text.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError(
                f"Research source content has invalid {label}."
            ) from error
        if parsed.utcoffset() is None:
            raise ResearchError(
                f"Research source content {label} must be timezone-aware."
            )
        return parsed

    @staticmethod
    def _serialize_record(record: ResearchSourceContentRecord) -> dict[str, object]:
        return {
            "document_id": record.document_id,
            "url": record.url,
            "title": record.title,
            "content": record.content,
            "content_type": record.content_type,
            "fetched_at": record.fetched_at.isoformat(),
            "stored_at": record.stored_at.isoformat(),
            "content_byte_count": record.content_byte_count,
            "content_sha256": record.content_sha256,
        }

    @classmethod
    def _validate_records(cls, records: list[ResearchSourceContentRecord]) -> None:
        if not isinstance(records, list) or not all(
            isinstance(record, ResearchSourceContentRecord) for record in records
        ):
            raise ResearchError(
                "Research source content store accepts only content records."
            )
        if len(records) > cls._MAXIMUM_RECORDS:
            raise ResearchError("Research source content store has too many records.")
        document_ids = [record.document_id for record in records]
        urls = [record.url for record in records]
        if len(document_ids) != len(set(document_ids)):
            raise ResearchError(
                "Research source content store has duplicate document IDs."
            )
        if len(urls) != len(set(urls)):
            raise ResearchError("Research source content store has duplicate URLs.")
        if (
            sum(record.content_byte_count for record in records)
            > cls._MAXIMUM_TOTAL_CONTENT_BYTES
        ):
            raise ResearchError("Research source content store content is too large.")

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
