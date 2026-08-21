"""Atomic JSON persistence for explicit local knowledge relationships."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeGraph import KnowledgeGraphRelation
from knowledge.KnowledgeRelationRecord import KnowledgeRelationRecord

MAX_KNOWLEDGE_RELATION_STORE_BYTES = 64 * 1024 * 1024
MAX_KNOWLEDGE_RELATIONS = 20_000
MAX_KNOWLEDGE_RELATION_DOCUMENT_ID_CHARACTERS = 1_024


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    """Write exact UTF-8 bytes without exceeding the relation-store limit."""

    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        encoded_size = len(encoded)
        if self._byte_count + encoded_size > MAX_KNOWLEDGE_RELATION_STORE_BYTES:
            raise OverflowError("Knowledge relation store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Knowledge relation temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileKnowledgeRelationStore:
    """Load and replace versioned relationship snapshots in a local JSON file."""

    _SCHEMA_VERSION = 1
    _RECORD_FIELDS = {"source_document_id", "relation", "target_document_id"}

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[KnowledgeRelationRecord]:
        """Load a complete validated relationship snapshot, or an empty one."""
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_KNOWLEDGE_RELATION_STORE_BYTES + 1)
        except FileNotFoundError:
            return []
        except OSError as error:
            raise KnowledgeError(
                f"Unable to read knowledge relation store '{self._path}': {error}"
            ) from error
        if len(encoded_document) > MAX_KNOWLEDGE_RELATION_STORE_BYTES:
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' is too large."
            )
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise KnowledgeError(
                f"Unable to read knowledge relation store '{self._path}': {error}"
            ) from error
        return self._parse_document(document)

    def save(self, records: list[KnowledgeRelationRecord]) -> None:
        """Atomically replace the persisted relationship snapshot."""
        self._validate_records(records)
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "relations": [self._serialize_record(record) for record in records],
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
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise KnowledgeError(
                f"Unable to write knowledge relation store '{self._path}': {error}"
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _parse_document(self, document: Any) -> list[KnowledgeRelationRecord]:
        if not isinstance(document, dict):
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' must contain an object."
            )
        schema_version = document.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != self._SCHEMA_VERSION
        ):
            raise KnowledgeError(
                "Knowledge relation store "
                f"'{self._path}' has an unsupported schema version."
            )
        relations_data = document.get("relations")
        if not isinstance(relations_data, list):
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' relations must be a list."
            )
        if len(relations_data) > MAX_KNOWLEDGE_RELATIONS:
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' has too many relations."
            )
        records = [self._parse_record(item) for item in relations_data]
        self._validate_records(records)
        return records

    def _parse_record(self, record_data: Any) -> KnowledgeRelationRecord:
        if not isinstance(record_data, dict) or set(record_data) != self._RECORD_FIELDS:
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' contains an invalid relation."
            )
        for document_id in (
            record_data["source_document_id"],
            record_data["target_document_id"],
        ):
            if (
                isinstance(document_id, str)
                and len(document_id.strip())
                > MAX_KNOWLEDGE_RELATION_DOCUMENT_ID_CHARACTERS
            ):
                raise KnowledgeError(
                    f"Knowledge relation store '{self._path}' has a document ID "
                    "that is too long."
                )
        try:
            relation = KnowledgeGraphRelation(record_data["relation"])
        except (TypeError, ValueError) as error:
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' has an invalid relation type."
            ) from error
        return KnowledgeRelationRecord(
            source_document_id=record_data["source_document_id"],
            relation=relation,
            target_document_id=record_data["target_document_id"],
        )

    @staticmethod
    def _serialize_record(record: KnowledgeRelationRecord) -> dict[str, str]:
        if not isinstance(record, KnowledgeRelationRecord):
            raise KnowledgeError(
                "Knowledge relation store accepts only relation records."
            )
        return {
            "source_document_id": record.source_document_id,
            "relation": record.relation.value,
            "target_document_id": record.target_document_id,
        }

    @staticmethod
    def _validate_records(records: list[KnowledgeRelationRecord]) -> None:
        if not isinstance(records, list):
            raise KnowledgeError("Knowledge relation store accepts a list of records.")
        if len(records) > MAX_KNOWLEDGE_RELATIONS:
            raise KnowledgeError("Knowledge relation store has too many relations.")
        if not all(isinstance(record, KnowledgeRelationRecord) for record in records):
            raise KnowledgeError(
                "Knowledge relation store accepts only relation records."
            )
        if any(
            len(document_id) > MAX_KNOWLEDGE_RELATION_DOCUMENT_ID_CHARACTERS
            for record in records
            for document_id in (
                record.source_document_id,
                record.target_document_id,
            )
        ):
            raise KnowledgeError(
                "Knowledge relation store has a document ID that is too long."
            )
        if len(records) != len(set(records)):
            raise KnowledgeError(
                "Knowledge relation store contains duplicate relations."
            )

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
