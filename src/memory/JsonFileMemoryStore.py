"""JSON-backed persistence for complete memory snapshots."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import MemoryError
from memory.MemoryRecord import MemoryRecord

MAX_MEMORY_STORE_BYTES = 64 * 1024 * 1024
MAX_MEMORY_RECORDS = 20_000
MAX_MEMORY_ID_CHARACTERS = 1_024
MAX_MEMORY_CONTENT_CHARACTERS = 1_000_000
MAX_MEMORY_METADATA_UTF8_BYTES = 8 * 1024 * 1024
MAX_MEMORY_METADATA_ENTRIES = 100_000
MAX_MEMORY_TAGS = 100_000
MAX_MEMORY_TAG_CHARACTERS = 256


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    """Write exact UTF-8 bytes without exceeding the memory-store limit."""

    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        encoded_size = len(encoded)
        if self._byte_count + encoded_size > MAX_MEMORY_STORE_BYTES:
            raise OverflowError("Memory store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Memory store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class _Utf8ByteCounter:
    """Count streamed JSON bytes without retaining a serialized copy."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self.byte_count = 0

    def write(self, value: str) -> int:
        encoded_size = len(value.encode("utf-8"))
        if self.byte_count + encoded_size > self._limit:
            raise OverflowError("UTF-8 byte limit exceeded.")
        self.byte_count += encoded_size
        return len(value)


class JsonFileMemoryStore:
    """Load and save versioned memory snapshots in a local JSON file."""

    _SCHEMA_VERSION = 1
    _RECORD_FIELDS = {
        "memory_id",
        "content",
        "metadata",
        "tags",
        "created_at",
        "updated_at",
        "expires_at",
    }

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[MemoryRecord]:
        """Load and return a fully validated memory snapshot."""
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_MEMORY_STORE_BYTES + 1)
        except FileNotFoundError:
            return []
        except OSError as error:
            raise MemoryError(
                f"Unable to read memory store '{self._path}': {error}"
            ) from error
        if len(encoded_document) > MAX_MEMORY_STORE_BYTES:
            raise MemoryError(f"Memory store '{self._path}' is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
            raise MemoryError(
                f"Unable to read memory store '{self._path}': {error}"
            ) from error

        return self._parse_document(document)

    def save(self, records: list[MemoryRecord]) -> None:
        """Persist the complete memory snapshot with the current schema version."""
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
                bounded_file = _BoundedUtf8Writer(file)
                json.dump(document, bounded_file, ensure_ascii=False, indent=2)
                bounded_file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, self._path)
        except OverflowError as error:
            raise MemoryError(f"Memory store '{self._path}' is too large.") from error
        except (OSError, RecursionError, TypeError, ValueError) as error:
            raise MemoryError(
                f"Unable to write memory store '{self._path}': {error}"
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _parse_document(self, document: Any) -> list[MemoryRecord]:
        if not isinstance(document, dict):
            raise MemoryError(f"Memory store '{self._path}' must contain an object.")

        schema_version = document.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != self._SCHEMA_VERSION
        ):
            raise MemoryError(
                f"Memory store '{self._path}' has an unsupported schema version."
            )

        records_data = document.get("records")
        if not isinstance(records_data, list):
            raise MemoryError(f"Memory store '{self._path}' records must be a list.")
        if len(records_data) > MAX_MEMORY_RECORDS:
            raise MemoryError(f"Memory store '{self._path}' has too many records.")
        self._validate_persisted_tag_count(records_data)

        records = [self._parse_record(record_data) for record_data in records_data]
        self._validate_records(records)
        return records

    def _parse_record(self, record_data: Any) -> MemoryRecord:
        if not isinstance(record_data, dict):
            raise MemoryError(
                f"Memory store '{self._path}' contains an invalid record."
            )

        missing_fields = self._RECORD_FIELDS.difference(record_data)
        if missing_fields:
            fields = ", ".join(sorted(missing_fields))
            raise MemoryError(
                f"Memory store '{self._path}' record is missing fields: {fields}."
            )

        memory_id = record_data["memory_id"]
        content = record_data["content"]
        metadata = record_data["metadata"]
        tags = record_data["tags"]

        self._validate_memory_id(memory_id)
        self._validate_content(content)
        if not isinstance(metadata, dict):
            raise MemoryError(
                f"Memory store '{self._path}' metadata must be an object."
            )
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) and tag.strip() for tag in tags
        ):
            raise MemoryError(
                f"Memory store '{self._path}' tags must be a list of strings."
            )
        if len(tags) > MAX_MEMORY_TAGS:
            raise MemoryError(f"Memory store '{self._path}' has too many tags.")
        if any(len(tag) > MAX_MEMORY_TAG_CHARACTERS for tag in tags):
            raise MemoryError(
                f"Memory store '{self._path}' has a tag that is too long."
            )

        return MemoryRecord(
            memory_id=memory_id,
            content=content,
            metadata=metadata,
            tags=frozenset(tags),
            created_at=self._parse_datetime(record_data["created_at"], "created_at"),
            updated_at=self._parse_datetime(record_data["updated_at"], "updated_at"),
            expires_at=self._parse_datetime(record_data["expires_at"], "expires_at"),
        )

    def _parse_datetime(self, value: Any, field_name: str) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise MemoryError(
                f"Memory store '{self._path}' {field_name} must be an ISO-8601 string."
            )

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise MemoryError(
                f"Memory store '{self._path}' has an invalid {field_name} value."
            ) from error

        if parsed.tzinfo is None:
            raise MemoryError(
                f"Memory store '{self._path}' {field_name} must include "
                "timezone information."
            )

        return parsed

    def _validate_records(self, records: list[MemoryRecord]) -> None:
        if not isinstance(records, list):
            raise MemoryError("Memory store accepts a list of records.")
        if len(records) > MAX_MEMORY_RECORDS:
            raise MemoryError("Memory store has too many records.")
        if not all(isinstance(record, MemoryRecord) for record in records):
            raise MemoryError("Memory store accepts only memory records.")

        memory_ids: list[str] = []
        metadata_bytes = 0
        metadata_entries = 0
        tag_count = 0
        for record in records:
            memory_ids.append(self._validate_memory_id(record.memory_id))
            self._validate_content(record.content)
            if not isinstance(record.metadata, Mapping):
                raise MemoryError("Memory record metadata must be a mapping.")
            metadata_entries += len(record.metadata)
            if metadata_entries > MAX_MEMORY_METADATA_ENTRIES:
                raise MemoryError("Memory store has too many metadata entries.")
            remaining_metadata_bytes = MAX_MEMORY_METADATA_UTF8_BYTES - metadata_bytes
            metadata_bytes += self._measure_metadata_utf8_bytes(
                record.metadata,
                remaining_metadata_bytes,
            )
            if not isinstance(record.tags, frozenset) or not all(
                isinstance(tag, str) and tag.strip() for tag in record.tags
            ):
                raise MemoryError("Memory record tags must be a set of strings.")
            tag_count += len(record.tags)
            if tag_count > MAX_MEMORY_TAGS:
                raise MemoryError("Memory store has too many tags.")
            if any(len(tag) > MAX_MEMORY_TAG_CHARACTERS for tag in record.tags):
                raise MemoryError("Memory store has a tag that is too long.")
            for field_name in ("created_at", "updated_at", "expires_at"):
                value = getattr(record, field_name)
                if value is not None and (
                    not isinstance(value, datetime) or value.tzinfo is None
                ):
                    raise MemoryError(
                        f"Memory record {field_name} must include timezone information."
                    )

        if len(memory_ids) != len(set(memory_ids)):
            raise MemoryError("Memory store contains duplicate memory IDs.")

    def _validate_memory_id(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise MemoryError(f"Memory store '{self._path}' has an invalid memory ID.")
        if len(value) > MAX_MEMORY_ID_CHARACTERS:
            raise MemoryError(
                f"Memory store '{self._path}' has a memory ID that is too long."
            )
        return value

    def _validate_content(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise MemoryError(
                f"Memory store '{self._path}' has invalid memory content."
            )
        if len(value) > MAX_MEMORY_CONTENT_CHARACTERS:
            raise MemoryError(
                f"Memory store '{self._path}' has memory content that is too long."
            )
        return value

    def _validate_persisted_tag_count(self, records_data: list[Any]) -> None:
        tag_count = 0
        for record_data in records_data:
            if not isinstance(record_data, dict):
                continue
            tags = record_data.get("tags")
            if not isinstance(tags, list):
                continue
            tag_count += len(tags)
            if tag_count > MAX_MEMORY_TAGS:
                raise MemoryError(f"Memory store '{self._path}' has too many tags.")

    @staticmethod
    def _measure_metadata_utf8_bytes(
        metadata: Mapping[str, Any],
        limit: int,
    ) -> int:
        counter = _Utf8ByteCounter(limit)
        try:
            json.dump(
                dict(metadata),
                counter,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except OverflowError as error:
            raise MemoryError("Memory store metadata is too large.") from error
        except (RecursionError, TypeError, ValueError) as error:
            raise MemoryError("Memory store contains invalid metadata.") from error
        return counter.byte_count

    @staticmethod
    def _serialize_record(record: MemoryRecord) -> dict[str, Any]:
        return {
            "memory_id": record.memory_id,
            "content": record.content,
            "metadata": dict(record.metadata),
            "tags": sorted(record.tags),
            "created_at": (
                record.created_at.isoformat() if record.created_at is not None else None
            ),
            "updated_at": (
                record.updated_at.isoformat() if record.updated_at is not None else None
            ),
            "expires_at": (
                record.expires_at.isoformat() if record.expires_at is not None else None
            ),
        }

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return

        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
