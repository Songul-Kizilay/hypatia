"""JSON-backed persistence for complete session registry snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from core.Exceptions import SessionError
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot


class JsonFileSessionStore:
    """Load and save versioned session registry snapshots in a local JSON file."""

    _SCHEMA_VERSION = 1
    _DOCUMENT_FIELDS = {"schema_version", "active_session_id", "sessions"}
    _SESSION_FIELDS = {"session_id", "created_at"}

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> SessionRegistrySnapshot | None:
        """Load and return a fully validated registry snapshot."""
        if not self._path.exists():
            return None

        try:
            with self._path.open(encoding="utf-8") as file:
                document = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SessionError(
                f"Unable to read session store '{self._path}': {error}"
            ) from error

        return self._parse_document(document)

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        """Persist a validated registry snapshot with an atomic replacement."""
        document = self._serialize_snapshot(snapshot)
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
            raise SessionError(
                f"Unable to write session store '{self._path}': {error}"
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _parse_document(self, document: Any) -> SessionRegistrySnapshot:
        if not isinstance(document, dict):
            raise SessionError(f"Session store '{self._path}' must contain an object.")
        if set(document) != self._DOCUMENT_FIELDS:
            raise SessionError(f"Session store '{self._path}' has invalid fields.")
        if document["schema_version"] != self._SCHEMA_VERSION:
            raise SessionError(
                f"Session store '{self._path}' has an unsupported schema version."
            )

        active_session_id = self._validate_session_id(
            document["active_session_id"],
            "active_session_id",
        )
        sessions_data = document["sessions"]
        if not isinstance(sessions_data, list) or not sessions_data:
            raise SessionError(
                f"Session store '{self._path}' sessions must be a non-empty list."
            )

        sessions = tuple(
            self._parse_session(session_data) for session_data in sessions_data
        )
        return self._validate_snapshot(
            SessionRegistrySnapshot(
                active_session_id=active_session_id,
                sessions=sessions,
            )
        )

    def _parse_session(self, session_data: Any) -> SessionRecord:
        if not isinstance(session_data, dict):
            raise SessionError(
                f"Session store '{self._path}' contains an invalid session record."
            )
        if set(session_data) != self._SESSION_FIELDS:
            raise SessionError(
                f"Session store '{self._path}' session record has invalid fields."
            )

        return SessionRecord(
            session_id=self._validate_session_id(
                session_data["session_id"], "session_id"
            ),
            created_at=self._parse_datetime(session_data["created_at"]),
        )

    def _parse_datetime(self, value: Any) -> datetime:
        if not isinstance(value, str):
            raise SessionError(
                f"Session store '{self._path}' created_at must be an ISO-8601 string."
            )

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise SessionError(
                f"Session store '{self._path}' has an invalid created_at value."
            ) from error

        if parsed.tzinfo is None:
            raise SessionError(
                f"Session store '{self._path}' created_at must include "
                "timezone information."
            )

        return parsed

    def _serialize_snapshot(
        self,
        snapshot: SessionRegistrySnapshot,
    ) -> dict[str, object]:
        validated_snapshot = self._validate_snapshot(snapshot)
        return {
            "schema_version": self._SCHEMA_VERSION,
            "active_session_id": validated_snapshot.active_session_id,
            "sessions": [
                {
                    "session_id": session.session_id,
                    "created_at": session.created_at.isoformat(),
                }
                for session in validated_snapshot.sessions
            ],
        }

    def _validate_snapshot(
        self,
        snapshot: SessionRegistrySnapshot,
    ) -> SessionRegistrySnapshot:
        if not isinstance(snapshot, SessionRegistrySnapshot):
            raise SessionError("Session snapshot must be a SessionRegistrySnapshot.")

        active_session_id = self._validate_session_id(
            snapshot.active_session_id,
            "active_session_id",
        )
        if not snapshot.sessions:
            raise SessionError("Session snapshot must contain at least one session.")

        session_ids: list[str] = []
        for session in snapshot.sessions:
            if not isinstance(session, SessionRecord):
                raise SessionError(
                    "Session snapshot contains an invalid session record."
                )
            session_ids.append(
                self._validate_session_id(session.session_id, "session_id")
            )
            if (
                not isinstance(session.created_at, datetime)
                or session.created_at.tzinfo is None
            ):
                raise SessionError(
                    "Session record created_at must include timezone information."
                )

        if len(session_ids) != len(set(session_ids)):
            raise SessionError("Session snapshot contains duplicate session IDs.")
        if "default" not in session_ids:
            raise SessionError("Session snapshot must contain the default session.")
        if active_session_id not in session_ids:
            raise SessionError("Active session ID must exist in the session registry.")

        return snapshot

    @staticmethod
    def _validate_session_id(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value or value != value.strip():
            raise SessionError(f"Session store has an invalid {field_name}.")
        return value

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return

        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
