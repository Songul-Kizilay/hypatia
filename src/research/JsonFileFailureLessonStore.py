"""Atomic versioned persistence for remembered failure lessons.

A sixth separate store, following the reflection store pattern exactly. Runs,
executions, background tasks, curiosity questions, and reflections are
untouched, so no migration runs and deleting this file simply means Hypatia
remembers no lessons.

Provenance is persisted with every lesson, and a lesson without it is refused
here as it is at construction. That is the property that makes this file worth
keeping at all: years from now a lesson can still be traced to the records it
came from, and discarded if they no longer say what it claims.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.FailureLessonKind import FailureLessonKind
from research.ResearchFailureLesson import ResearchFailureLesson

MAX_FAILURE_STORE_BYTES = 4 * 1024 * 1024
MAX_FAILURE_STORE_LESSONS = 1000

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "lessons"})
_LESSON_FIELDS = frozenset(
    {
        "lesson_id",
        "kind",
        "run_id",
        "subject_id",
        "statement",
        "provenance",
        "context",
        "recorded_at",
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
        if self._byte_count + encoded_size > MAX_FAILURE_STORE_BYTES:
            raise OverflowError("Failure lesson store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Failure lesson store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileFailureLessonStore:
    """Load and atomically replace a strict versioned lesson document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchFailureLesson]:
        """Return validated lessons, or an empty list when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_FAILURE_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the failure lesson store.") from error
        if len(encoded_document) > MAX_FAILURE_STORE_BYTES:
            raise ResearchError("The failure lesson store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the failure lesson store.") from error
        return self._parse_document(document)

    def save(self, lessons: list[ResearchFailureLesson]) -> None:
        """Atomically replace the complete lesson document."""
        self._validate_lessons(lessons)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "lessons": [self._serialize(lesson) for lesson in lessons],
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
            raise ResearchError("The failure lesson store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the failure lesson store.") from error
        finally:
            self._remove_temporary_file(temporary_path)

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _serialize(lesson: ResearchFailureLesson) -> dict[str, Any]:
        return {
            "lesson_id": lesson.lesson_id,
            "kind": lesson.kind.value,
            "run_id": lesson.run_id,
            "subject_id": lesson.subject_id,
            "statement": lesson.statement,
            "provenance": list(lesson.provenance),
            "context": lesson.context,
            "recorded_at": lesson.recorded_at.isoformat(),
        }

    def _parse_document(self, document: object) -> list[ResearchFailureLesson]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The failure lesson document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError(
                "The failure lesson store schema version is not supported."
            )
        lessons_value = document["lessons"]
        if not isinstance(lessons_value, list):
            raise ResearchError("Failure lesson store lessons must be a list.")
        if len(lessons_value) > MAX_FAILURE_STORE_LESSONS:
            raise ResearchError("The failure lesson store has too many lessons.")
        lessons = [self._parse_lesson(value) for value in lessons_value]
        self._validate_lessons(lessons)
        return lessons

    @staticmethod
    def _parse_lesson(document: object) -> ResearchFailureLesson:
        if not isinstance(document, dict) or set(document) != _LESSON_FIELDS:
            raise ResearchError("A failure lesson document is invalid.")
        store = JsonFileFailureLessonStore
        provenance = document["provenance"]
        if not isinstance(provenance, list) or not all(
            isinstance(value, str) for value in provenance
        ):
            raise ResearchError("A failure lesson provenance list is invalid.")
        kind = document["kind"]
        if not isinstance(kind, str):
            raise ResearchError("A failure lesson kind is invalid.")
        try:
            parsed_kind = FailureLessonKind(kind)
        except ValueError as error:
            raise ResearchError("A failure lesson kind is invalid.") from error
        return ResearchFailureLesson(
            lesson_id=store._text(document["lesson_id"]),
            kind=parsed_kind,
            run_id=store._text(document["run_id"]),
            subject_id=store._optional_text(document["subject_id"]),
            statement=store._optional_text(document["statement"]),
            provenance=tuple(provenance),
            context=store._optional_text(document["context"]),
            recorded_at=store._timestamp(document["recorded_at"]),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A failure lesson identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A failure lesson text field is invalid.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A failure lesson timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("A failure lesson timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("A failure lesson timestamp must be timezone-aware.")
        return parsed

    def _validate_lessons(self, lessons: list[ResearchFailureLesson]) -> None:
        if not isinstance(lessons, list):
            raise ResearchError("The failure lesson store accepts a list.")
        if len(lessons) > MAX_FAILURE_STORE_LESSONS:
            raise ResearchError("The failure lesson store has too many lessons.")
        if not all(isinstance(lesson, ResearchFailureLesson) for lesson in lessons):
            raise ResearchError("The failure lesson store accepts only lessons.")
        lesson_ids = [lesson.lesson_id for lesson in lessons]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise ResearchError("The failure lesson store has duplicate lesson IDs.")
