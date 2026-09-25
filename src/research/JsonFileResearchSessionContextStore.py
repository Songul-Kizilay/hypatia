"""Strict atomic persistence for append-only research session contexts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchAuthenticationState import ResearchAuthenticationState
from research.ResearchSessionContextRecord import ResearchSessionContextRecord

MAX_SESSION_CONTEXT_STORE_BYTES = 2 * 1024 * 1024
MAX_SESSION_CONTEXT_RECORDS = 5_000

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "records"})
_RECORD_FIELDS = frozenset(
    {
        "session_context_id",
        "program_id",
        "authentication_state",
        "identity_label",
        "evidence_ids",
        "note",
        "recorded_at",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchSessionContextDocument:
    records: tuple[ResearchSessionContextRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple) or any(
            not isinstance(value, ResearchSessionContextRecord)
            for value in self.records
        ):
            raise ResearchError("Research session context records are invalid.")
        if len(self.records) > MAX_SESSION_CONTEXT_RECORDS:
            raise ResearchError(
                "The research session context store has too many records."
            )
        identities = [value.session_context_id for value in self.records]
        if len(identities) != len(set(identities)):
            raise ResearchError(
                "The research session context store has duplicate context IDs."
            )


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        if self._byte_count + len(encoded) > MAX_SESSION_CONTEXT_STORE_BYTES:
            raise OverflowError("Research session context store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != len(encoded):
            raise OSError("Research session context temporary write was incomplete.")
        self._byte_count += len(encoded)
        return len(value)


class JsonFileResearchSessionContextStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchSessionContextDocument:
        if not self._path.exists():
            return ResearchSessionContextDocument()
        try:
            with self._path.open("rb") as file:
                encoded = file.read(MAX_SESSION_CONTEXT_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                "Unable to read the research session context store."
            ) from error
        if len(encoded) > MAX_SESSION_CONTEXT_STORE_BYTES:
            raise ResearchError("The research session context store is too large.")
        try:
            document = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read the research session context store."
            ) from error
        return self._parse_document(document)

    def save(self, document: ResearchSessionContextDocument) -> None:
        if not isinstance(document, ResearchSessionContextDocument):
            raise ResearchError(
                "The research session context store accepts only a document."
            )
        existing = self.load()
        if document.records[: len(existing.records)] != existing.records:
            raise ResearchError(
                "Research session context records are append-only and cannot"
                " be replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "records": [self._serialize_record(record) for record in document.records],
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
                bounded = _BoundedUtf8Writer(file)
                json.dump(encoded, bounded, ensure_ascii=False, indent=2)
                bounded.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except OverflowError as error:
            raise ResearchError(
                "The research session context store is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the research session context store."
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _serialize_record(record: ResearchSessionContextRecord) -> dict[str, Any]:
        return {
            "session_context_id": record.session_context_id,
            "program_id": record.program_id,
            "authentication_state": record.authentication_state.value,
            "identity_label": record.identity_label,
            "evidence_ids": list(record.evidence_ids),
            "note": record.note,
            "recorded_at": record.recorded_at.isoformat(),
        }

    @staticmethod
    def _parse_document(document: object) -> ResearchSessionContextDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The research session context document is invalid.")
        version = document["schema_version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != _SCHEMA_VERSION
        ):
            raise ResearchError(
                "The research session context store schema version is not supported."
            )
        records = document["records"]
        if not isinstance(records, list) or len(records) > MAX_SESSION_CONTEXT_RECORDS:
            raise ResearchError(
                "Research session context records must be a bounded list."
            )
        return ResearchSessionContextDocument(
            records=tuple(
                JsonFileResearchSessionContextStore._parse_record(v) for v in records
            )
        )

    @staticmethod
    def _parse_record(document: object) -> ResearchSessionContextRecord:
        if not isinstance(document, dict) or set(document) != _RECORD_FIELDS:
            raise ResearchError(
                "A research session context record document is invalid."
            )
        state = document["authentication_state"]
        if not isinstance(state, str):
            raise ResearchError("Research session authentication state is invalid.")
        try:
            authentication_state = ResearchAuthenticationState(state)
        except ValueError as error:
            raise ResearchError(
                "Research session authentication state is invalid."
            ) from error
        evidence_ids = document["evidence_ids"]
        if not isinstance(evidence_ids, list) or any(
            not isinstance(value, str) for value in evidence_ids
        ):
            raise ResearchError("Research session evidence references are invalid.")
        recorded_at = document["recorded_at"]
        if not isinstance(recorded_at, str):
            raise ResearchError("Research session context timestamp is invalid.")
        try:
            timestamp = datetime.fromisoformat(recorded_at)
        except ValueError as error:
            raise ResearchError(
                "Research session context timestamp is invalid."
            ) from error
        return ResearchSessionContextRecord(
            session_context_id=JsonFileResearchSessionContextStore._text(
                document["session_context_id"]
            ),
            program_id=JsonFileResearchSessionContextStore._text(
                document["program_id"]
            ),
            authentication_state=authentication_state,
            identity_label=JsonFileResearchSessionContextStore._optional_text(
                document["identity_label"]
            ),
            evidence_ids=tuple(evidence_ids),
            note=JsonFileResearchSessionContextStore._optional_text(document["note"]),
            recorded_at=timestamp,
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(
                "A research session context identifier cannot be empty."
            )
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A research session context text field is invalid.")
        return value
