"""Atomic versioned persistence for background research tasks.

A third separate store, following the execution-store pattern exactly.
`ResearchRun` and the execution store are untouched, so no migration runs and
deleting this file simply means no scheduled tasks.

Only scheduling bookkeeping is written: identifiers, status, declared budget,
retry counters, a bounded outcome category, an exception class name, and
timestamps. No question text, URL, source body, evidence text, or claim text is
ever stored here.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.BackgroundResearchTask import BackgroundResearchTask
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.ResearchAutonomyBudget import ResearchAutonomyBudget

MAX_BACKGROUND_TASK_STORE_BYTES = 4 * 1024 * 1024
MAX_BACKGROUND_TASK_STORE_TASKS = 500

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "tasks"})
_TASK_FIELDS = frozenset(
    {
        "task_id",
        "execution_id",
        "status",
        "retry_count",
        "max_retries",
        "outcome",
        "failure_cause",
        "created_at",
        "updated_at",
        "budget",
    }
)
_BUDGET_FIELDS = frozenset(
    {
        "max_step_advances",
        "max_network_operations",
        "max_llm_operations",
        "max_seconds",
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
        if self._byte_count + encoded_size > MAX_BACKGROUND_TASK_STORE_BYTES:
            raise OverflowError("Background task store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Background task store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileBackgroundTaskStore:
    """Load and atomically replace a strict versioned task document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[BackgroundResearchTask]:
        """Return validated tasks, or an empty list when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_BACKGROUND_TASK_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the background task store.") from error
        if len(encoded_document) > MAX_BACKGROUND_TASK_STORE_BYTES:
            raise ResearchError("The background task store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the background task store.") from error
        return self._parse_document(document)

    def save(self, tasks: list[BackgroundResearchTask]) -> None:
        """Atomically replace the complete task document."""
        self._validate_tasks(tasks)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "tasks": [self._serialize(task) for task in tasks],
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
            raise ResearchError("The background task store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the background task store.") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _serialize(task: BackgroundResearchTask) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "execution_id": task.execution_id,
            "status": task.status.value,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "outcome": task.outcome,
            "failure_cause": task.failure_cause,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "budget": {
                "max_step_advances": task.budget.max_step_advances,
                "max_network_operations": task.budget.max_network_operations,
                "max_llm_operations": task.budget.max_llm_operations,
                "max_seconds": task.budget.max_seconds,
            },
        }

    def _parse_document(self, document: object) -> list[BackgroundResearchTask]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The background task document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError(
                "The background task store schema version is not supported."
            )
        tasks_value = document["tasks"]
        if not isinstance(tasks_value, list):
            raise ResearchError("Background task store tasks must be a list.")
        if len(tasks_value) > MAX_BACKGROUND_TASK_STORE_TASKS:
            raise ResearchError("The background task store has too many tasks.")
        tasks = [self._parse_task(value) for value in tasks_value]
        self._validate_tasks(tasks)
        return tasks

    @staticmethod
    def _parse_task(document: object) -> BackgroundResearchTask:
        if not isinstance(document, dict) or set(document) != _TASK_FIELDS:
            raise ResearchError("A background task document is invalid.")
        budget_document = document["budget"]
        if (
            not isinstance(budget_document, dict)
            or set(budget_document) != _BUDGET_FIELDS
        ):
            raise ResearchError("A background task budget document is invalid.")
        status = document["status"]
        if not isinstance(status, str):
            raise ResearchError("A background task status is invalid.")
        try:
            parsed_status = BackgroundResearchTaskStatus(status)
        except ValueError as error:
            raise ResearchError("A background task status is invalid.") from error
        store = JsonFileBackgroundTaskStore
        return BackgroundResearchTask(
            task_id=store._text(document["task_id"]),
            execution_id=store._text(document["execution_id"]),
            budget=ResearchAutonomyBudget(
                max_step_advances=budget_document["max_step_advances"],
                max_network_operations=budget_document["max_network_operations"],
                max_llm_operations=budget_document["max_llm_operations"],
                max_seconds=budget_document["max_seconds"],
            ),
            created_at=store._timestamp(document["created_at"]),
            updated_at=store._timestamp(document["updated_at"]),
            status=parsed_status,
            retry_count=document["retry_count"],
            max_retries=document["max_retries"],
            outcome=store._optional_text(document["outcome"]),
            failure_cause=store._optional_text(document["failure_cause"]),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A background task identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A background task text field is invalid.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A background task timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("A background task timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("A background task timestamp must be timezone-aware.")
        return parsed

    def _validate_tasks(self, tasks: list[BackgroundResearchTask]) -> None:
        if not isinstance(tasks, list):
            raise ResearchError("The background task store accepts a list.")
        if len(tasks) > MAX_BACKGROUND_TASK_STORE_TASKS:
            raise ResearchError("The background task store has too many tasks.")
        if not all(isinstance(task, BackgroundResearchTask) for task in tasks):
            raise ResearchError("The background task store accepts only tasks.")
        task_ids = [task.task_id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ResearchError("The background task store has duplicate task IDs.")
