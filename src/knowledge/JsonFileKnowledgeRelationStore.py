"""Atomic JSON persistence for explicit local knowledge relationships."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeGraph import KnowledgeGraphRelation
from knowledge.KnowledgeRelationRecord import KnowledgeRelationRecord


class JsonFileKnowledgeRelationStore:
    """Load and replace versioned relationship snapshots in a local JSON file."""

    _SCHEMA_VERSION = 1
    _RECORD_FIELDS = {"source_document_id", "relation", "target_document_id"}

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[KnowledgeRelationRecord]:
        """Load a complete validated relationship snapshot, or an empty one."""
        if not self._path.exists():
            return []
        try:
            with self._path.open(encoding="utf-8") as file:
                document = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise KnowledgeError(
                f"Unable to read knowledge relation store '{self._path}': {error}"
            ) from error
        return self._parse_document(document)

    def save(self, records: list[KnowledgeRelationRecord]) -> None:
        """Atomically replace the persisted relationship snapshot."""
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "relations": [self._serialize_record(record) for record in records],
        }
        self._validate_records(records)
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
        if document.get("schema_version") != self._SCHEMA_VERSION:
            raise KnowledgeError(
                "Knowledge relation store "
                f"'{self._path}' has an unsupported schema version."
            )
        relations_data = document.get("relations")
        if not isinstance(relations_data, list):
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' relations must be a list."
            )
        records = [self._parse_record(item) for item in relations_data]
        self._validate_records(records)
        return records

    def _parse_record(self, record_data: Any) -> KnowledgeRelationRecord:
        if not isinstance(record_data, dict) or set(record_data) != self._RECORD_FIELDS:
            raise KnowledgeError(
                f"Knowledge relation store '{self._path}' contains an invalid relation."
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
        if not all(isinstance(record, KnowledgeRelationRecord) for record in records):
            raise KnowledgeError(
                "Knowledge relation store accepts only relation records."
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
