"""Atomic persistence for human Kali operation authorizations."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)

MAX_KALI_OPERATION_AUTHORIZATION_STORE_BYTES = 1024 * 1024
MAX_KALI_OPERATION_AUTHORIZATION_STORE_ENTRIES = 500

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "authorizations"})
_ENTRY_FIELDS = frozenset(
    {
        "authorization_id",
        "operation_digest",
        "program_id",
        "scope_revision_id",
        "scope_revision_digest",
        "execution_policy_digest",
        "authorized_at",
        "expires_at",
        "authorized_by",
    }
)


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
        if self._byte_count + encoded_size > (
            MAX_KALI_OPERATION_AUTHORIZATION_STORE_BYTES
        ):
            raise OverflowError("Kali operation authorization store limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError(
                "Kali operation authorization temporary write was incomplete."
            )
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchKaliOperationAuthorizationStore:
    """Load and atomically replace strict operation authorization documents."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchKaliOperationAuthorization]:
        """Return validated operation authorizations, or empty when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded = file.read(MAX_KALI_OPERATION_AUTHORIZATION_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                "Unable to read the Kali operation authorization store."
            ) from error
        if len(encoded) > MAX_KALI_OPERATION_AUTHORIZATION_STORE_BYTES:
            raise ResearchError("The Kali operation authorization store is too large.")
        try:
            document = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read the Kali operation authorization store."
            ) from error
        return self._parse_document(document)

    def save(self, authorizations: list[ResearchKaliOperationAuthorization]) -> None:
        """Atomically replace the complete operation authorization document."""
        self._validate(authorizations)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "authorizations": [self._serialize(entry) for entry in authorizations],
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
            raise ResearchError(
                "The Kali operation authorization store is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the Kali operation authorization store."
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _serialize(
        entry: ResearchKaliOperationAuthorization,
    ) -> dict[str, Any]:
        return {
            "authorization_id": entry.authorization_id,
            "operation_digest": entry.operation_digest,
            "program_id": entry.program_id,
            "scope_revision_id": entry.scope_revision_id,
            "scope_revision_digest": entry.scope_revision_digest,
            "execution_policy_digest": entry.execution_policy_digest,
            "authorized_at": entry.authorized_at.isoformat(),
            "expires_at": entry.expires_at.isoformat(),
            "authorized_by": entry.authorized_by.value,
        }

    def _parse_document(
        self,
        document: object,
    ) -> list[ResearchKaliOperationAuthorization]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The Kali operation authorization document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError(
                "The Kali operation authorization schema version is not supported."
            )
        entries_value = document["authorizations"]
        if not isinstance(entries_value, list):
            raise ResearchError(
                "Kali operation authorization store entries must be a list."
            )
        entries = [self._parse_entry(value) for value in entries_value]
        self._validate(entries)
        return entries

    @staticmethod
    def _parse_entry(document: object) -> ResearchKaliOperationAuthorization:
        if not isinstance(document, dict) or set(document) != _ENTRY_FIELDS:
            raise ResearchError("A Kali operation authorization document is invalid.")
        store = JsonFileResearchKaliOperationAuthorizationStore
        return ResearchKaliOperationAuthorization(
            authorization_id=store._text(document["authorization_id"]),
            operation_digest=store._text(document["operation_digest"]),
            program_id=store._text(document["program_id"]),
            scope_revision_id=store._text(document["scope_revision_id"]),
            scope_revision_digest=store._text(document["scope_revision_digest"]),
            execution_policy_digest=store._text(document["execution_policy_digest"]),
            authorized_at=store._timestamp(document["authorized_at"]),
            expires_at=store._timestamp(document["expires_at"]),
            authorized_by=store._member(document["authorized_by"]),
        )

    @staticmethod
    def _member(value: object) -> ResearchAuthorizer:
        if not isinstance(value, str):
            raise ResearchError("A Kali operation authorizer is invalid.")
        try:
            return ResearchAuthorizer(value)
        except ValueError as error:
            raise ResearchError("A Kali operation authorizer is invalid.") from error

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(
                "A Kali operation authorization text field cannot be empty."
            )
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A Kali operation authorization timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError(
                "A Kali operation authorization timestamp is invalid."
            ) from error
        if parsed.utcoffset() is None:
            raise ResearchError(
                "A Kali operation authorization timestamp must be timezone-aware."
            )
        return parsed

    @staticmethod
    def _validate(authorizations: list[ResearchKaliOperationAuthorization]) -> None:
        if not isinstance(authorizations, list) or not all(
            isinstance(entry, ResearchKaliOperationAuthorization)
            for entry in authorizations
        ):
            raise ResearchError(
                "The Kali operation authorization store accepts authorizations."
            )
        if len(authorizations) > MAX_KALI_OPERATION_AUTHORIZATION_STORE_ENTRIES:
            raise ResearchError(
                "The Kali operation authorization store has too many entries."
            )
        identifiers = [entry.authorization_id for entry in authorizations]
        if len(identifiers) != len(set(identifiers)):
            raise ResearchError(
                "The Kali operation authorization store has duplicate identities."
            )
