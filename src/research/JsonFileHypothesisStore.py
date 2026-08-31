"""Atomic versioned persistence for authored research hypotheses.

A seventh separate store, following the failure-lesson store pattern exactly.
Runs, executions, background tasks, curiosity questions, reflections, and
lessons are untouched, so no migration runs and deleting this file simply means
no hypotheses.

The discriminating test is persisted with every hypothesis and refused if
missing, here as at construction. A stored hypothesis that has lost its defeater
would be indistinguishable from a belief, and a file is exactly where that loss
would happen quietly.

Status is not stored, because it is derived from the evidence on each side. A
persisted status could disagree with the evidence beside it, and whichever the
reader trusted would sometimes be wrong.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchHypothesis import ResearchHypothesis

MAX_HYPOTHESIS_STORE_BYTES = 4 * 1024 * 1024
MAX_HYPOTHESIS_STORE_ENTRIES = 500

#: Version 2 records which evidence an operator said addresses the
#: discriminating test. A version 1 hypothesis has no such statement, and the
#: honest reading of that is silence rather than consent: its supporting and
#: opposing evidence keeps meaning exactly what it meant, and none of it is
#: promoted into an association nobody authored. An open hypothesis restored
#: from version 1 therefore still reads as having no test evidence, which is
#: true — and which curiosity will say out loud.
_SCHEMA_VERSION = 2
_SUPPORTED_SCHEMA_VERSIONS = (1, 2)
_DOCUMENT_FIELDS = frozenset({"schema_version", "hypotheses"})
_ENTRY_FIELDS_V1 = frozenset(
    {
        "hypothesis_id",
        "run_id",
        "statement",
        "discriminating_test",
        "supporting_evidence_ids",
        "opposing_evidence_ids",
        "withdrawn",
        "created_at",
        "updated_at",
    }
)
_ENTRY_FIELDS_V2 = _ENTRY_FIELDS_V1 | {"discriminating_test_evidence_ids"}


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
        if self._byte_count + encoded_size > MAX_HYPOTHESIS_STORE_BYTES:
            raise OverflowError("Hypothesis store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Hypothesis store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileHypothesisStore:
    """Load and atomically replace a strict versioned hypothesis document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchHypothesis]:
        """Return validated hypotheses, or an empty list when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_HYPOTHESIS_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the hypothesis store.") from error
        if len(encoded_document) > MAX_HYPOTHESIS_STORE_BYTES:
            raise ResearchError("The hypothesis store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the hypothesis store.") from error
        return self._parse_document(document)

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        """Atomically replace the complete hypothesis document."""
        self._validate(hypotheses)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "hypotheses": [self._serialize(entry) for entry in hypotheses],
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
            temporary_path = None
        except OverflowError as error:
            raise ResearchError("The hypothesis store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the hypothesis store.") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _serialize(entry: ResearchHypothesis) -> dict[str, Any]:
        return {
            "hypothesis_id": entry.hypothesis_id,
            "run_id": entry.run_id,
            "statement": entry.statement,
            "discriminating_test": entry.discriminating_test,
            "supporting_evidence_ids": list(entry.supporting_evidence_ids),
            "opposing_evidence_ids": list(entry.opposing_evidence_ids),
            "discriminating_test_evidence_ids": list(
                entry.discriminating_test_evidence_ids
            ),
            "withdrawn": entry.withdrawn,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        }

    def _parse_document(self, document: object) -> list[ResearchHypothesis]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The hypothesis document is invalid.")
        schema_version = document["schema_version"]
        if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise ResearchError("The hypothesis store schema version is not supported.")
        entries_value = document["hypotheses"]
        if not isinstance(entries_value, list):
            raise ResearchError("Hypothesis store entries must be a list.")
        if len(entries_value) > MAX_HYPOTHESIS_STORE_ENTRIES:
            raise ResearchError("The hypothesis store has too many entries.")
        entries = [self._parse_entry(value, schema_version) for value in entries_value]
        self._validate(entries)
        return entries

    @staticmethod
    def _parse_entry(document: object, schema_version: int) -> ResearchHypothesis:
        expected = _ENTRY_FIELDS_V1 if schema_version == 1 else _ENTRY_FIELDS_V2
        if not isinstance(document, dict) or set(document) != expected:
            raise ResearchError("A hypothesis document is invalid.")
        store = JsonFileHypothesisStore
        withdrawn = document["withdrawn"]
        if not isinstance(withdrawn, bool):
            raise ResearchError("A hypothesis withdrawal flag is invalid.")
        return ResearchHypothesis(
            hypothesis_id=store._text(document["hypothesis_id"]),
            run_id=store._text(document["run_id"]),
            statement=store._text(document["statement"]),
            discriminating_test=store._text(document["discriminating_test"]),
            supporting_evidence_ids=store._ids(document["supporting_evidence_ids"]),
            opposing_evidence_ids=store._ids(document["opposing_evidence_ids"]),
            discriminating_test_evidence_ids=(
                ()
                if schema_version == 1
                else store._ids(document["discriminating_test_evidence_ids"])
            ),
            withdrawn=withdrawn,
            created_at=store._timestamp(document["created_at"]),
            updated_at=store._timestamp(document["updated_at"]),
        )

    @staticmethod
    def _ids(value: object) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(
            isinstance(entry, str) for entry in value
        ):
            raise ResearchError("A hypothesis evidence list is invalid.")
        return tuple(value)

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A hypothesis text field cannot be empty.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A hypothesis timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("A hypothesis timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("A hypothesis timestamp must be timezone-aware.")
        return parsed

    def _validate(self, hypotheses: list[ResearchHypothesis]) -> None:
        if not isinstance(hypotheses, list):
            raise ResearchError("The hypothesis store accepts a list.")
        if len(hypotheses) > MAX_HYPOTHESIS_STORE_ENTRIES:
            raise ResearchError("The hypothesis store has too many entries.")
        if not all(isinstance(entry, ResearchHypothesis) for entry in hypotheses):
            raise ResearchError("The hypothesis store accepts only hypotheses.")
        identifiers = [entry.hypothesis_id for entry in hypotheses]
        if len(identifiers) != len(set(identifiers)):
            raise ResearchError("The hypothesis store has duplicate IDs.")
