"""Atomic strict persistence for one-shot deferred schedules."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule
from research.OneShotDeferredExecutionScheduleStatus import (
    OneShotDeferredExecutionScheduleStatus,
)

MAX_ONE_SHOT_SCHEDULE_STORE_BYTES = 4 * 1024 * 1024
MAX_ONE_SHOT_SCHEDULE_STORE_ENTRIES = 500
_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "schedules"})
_ENTRY_FIELDS = frozenset(
    {
        "schedule_id",
        "task_id",
        "grant_id",
        "run_at",
        "created_at",
        "created_by",
        "status",
        "resolved_at",
        "outcome",
    }
)


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        if self._byte_count + len(encoded) > MAX_ONE_SHOT_SCHEDULE_STORE_BYTES:
            raise OverflowError
        written = self._stream.write(encoded)
        if written != len(encoded):
            raise OSError("One-shot schedule temporary write was incomplete.")
        self._byte_count += written
        return len(value)


class JsonFileOneShotDeferredExecutionScheduleStore:
    """Load and atomically replace a bounded one-shot schedule history."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[OneShotDeferredExecutionSchedule]:
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                payload = file.read(MAX_ONE_SHOT_SCHEDULE_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read one-shot schedules.") from error
        if len(payload) > MAX_ONE_SHOT_SCHEDULE_STORE_BYTES:
            raise ResearchError("One-shot schedule store is too large.")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read one-shot schedules.") from error
        return self._parse_document(document)

    def save(self, schedules: list[OneShotDeferredExecutionSchedule]) -> None:
        self._validate(schedules)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "schedules": [self._serialize(value) for value in schedules],
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
                json.dump(document, bounded, ensure_ascii=False, indent=2)
                bounded.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write one-shot schedules.") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _serialize(value: OneShotDeferredExecutionSchedule) -> dict[str, Any]:
        return {
            "schedule_id": value.schedule_id,
            "task_id": value.task_id,
            "grant_id": value.grant_id,
            "run_at": value.run_at.isoformat(),
            "created_at": value.created_at.isoformat(),
            "created_by": value.created_by.value,
            "status": value.status.value,
            "resolved_at": (
                value.resolved_at.isoformat() if value.resolved_at is not None else None
            ),
            "outcome": value.outcome,
        }

    def _parse_document(
        self, document: object
    ) -> list[OneShotDeferredExecutionSchedule]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("One-shot schedule document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError("One-shot schedule schema is unsupported.")
        entries = document["schedules"]
        if not isinstance(entries, list):
            raise ResearchError("One-shot schedules must be a list.")
        schedules = [self._parse_entry(entry) for entry in entries]
        self._validate(schedules)
        return schedules

    @staticmethod
    def _parse_entry(document: object) -> OneShotDeferredExecutionSchedule:
        if not isinstance(document, dict) or set(document) != _ENTRY_FIELDS:
            raise ResearchError("A one-shot schedule is invalid.")
        store = JsonFileOneShotDeferredExecutionScheduleStore
        resolved_at = document["resolved_at"]
        outcome = document["outcome"]
        if outcome is not None and not isinstance(outcome, str):
            raise ResearchError("One-shot schedule outcome is invalid.")
        return OneShotDeferredExecutionSchedule(
            schedule_id=store._text(document["schedule_id"]),
            task_id=store._text(document["task_id"]),
            grant_id=store._text(document["grant_id"]),
            run_at=store._timestamp(document["run_at"]),
            created_at=store._timestamp(document["created_at"]),
            created_by=store._member(
                DeferredGrantAuthorizer, document["created_by"], "provenance"
            ),
            status=store._member(
                OneShotDeferredExecutionScheduleStatus,
                document["status"],
                "status",
            ),
            resolved_at=(
                None if resolved_at is None else store._timestamp(resolved_at)
            ),
            outcome=outcome,
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("One-shot schedule text is invalid.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("One-shot schedule timestamp is invalid.")
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("One-shot schedule timestamp is invalid.") from error

    @staticmethod
    def _member(enum_type, value: object, label: str):
        if not isinstance(value, str):
            raise ResearchError(f"One-shot schedule {label} is invalid.")
        try:
            return enum_type(value)
        except ValueError as error:
            raise ResearchError(f"One-shot schedule {label} is invalid.") from error

    @staticmethod
    def _validate(schedules: list[OneShotDeferredExecutionSchedule]) -> None:
        if not isinstance(schedules, list) or not all(
            isinstance(value, OneShotDeferredExecutionSchedule) for value in schedules
        ):
            raise ResearchError("One-shot schedule store accepts only schedules.")
        if len(schedules) > MAX_ONE_SHOT_SCHEDULE_STORE_ENTRIES:
            raise ResearchError("One-shot schedule store has too many entries.")
        ids = [value.schedule_id for value in schedules]
        if len(ids) != len(set(ids)):
            raise ResearchError("One-shot schedule IDs must be unique.")
        pending_tasks = [value.task_id for value in schedules if value.pending]
        if len(pending_tasks) != len(set(pending_tasks)):
            raise ResearchError("A task has multiple pending one-shot schedules.")
