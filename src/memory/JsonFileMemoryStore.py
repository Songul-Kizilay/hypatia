"""JSON-backed persistence for complete memory snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from core.Exceptions import MemoryError
from memory.MemoryRecord import MemoryRecord


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
        if not self._path.exists():
            return []

        try:
            with self._path.open(encoding="utf-8") as file:
                document = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MemoryError(
                f"Unable to read memory store '{self._path}': {error}"
            ) from error

        return self._parse_document(document)

    def save(self, records: list[MemoryRecord]) -> None:
        """Persist the complete memory snapshot with the current schema version."""
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "records": [self._serialize_record(record) for record in records],
        }
        temporary_path: Path | None = None

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(document, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, self._path)
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise MemoryError(
                f"Unable to write memory store '{self._path}': {error}"
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _parse_document(self, document: Any) -> list[MemoryRecord]:
        if not isinstance(document, dict):
            raise MemoryError(f"Memory store '{self._path}' must contain an object.")

        schema_version = document.get("schema_version")
        if schema_version != self._SCHEMA_VERSION:
            raise MemoryError(
                f"Memory store '{self._path}' has an unsupported schema version."
            )

        records_data = document.get("records")
        if not isinstance(records_data, list):
            raise MemoryError(f"Memory store '{self._path}' records must be a list.")

        records = [self._parse_record(record_data) for record_data in records_data]
        memory_ids = [record.memory_id for record in records]
        if len(memory_ids) != len(set(memory_ids)):
            raise MemoryError(
                f"Memory store '{self._path}' contains duplicate memory IDs."
            )

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

        if not isinstance(memory_id, str) or not memory_id.strip():
            raise MemoryError(f"Memory store '{self._path}' has an invalid memory ID.")
        if not isinstance(content, str) or not content.strip():
            raise MemoryError(
                f"Memory store '{self._path}' has invalid memory content."
            )
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
