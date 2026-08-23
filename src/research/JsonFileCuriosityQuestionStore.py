"""Atomic versioned persistence for proposed curiosity questions.

A fourth separate store, following the background-task store pattern exactly.
`ResearchRun`, the execution store, and the task store are untouched, so no
migration runs and deleting this file simply means no proposed questions.

Question text is stored, because a question a human must read is useless as an
opaque identifier. That text is template-generated from wording the run store
already holds, so this file exposes nothing new. It stores no source body, no
evidence excerpt, and no exception message, and the curiosity events built from
these records carry identifiers and counts only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind

MAX_CURIOSITY_STORE_BYTES = 4 * 1024 * 1024
MAX_CURIOSITY_STORE_QUESTIONS = 500

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "questions"})
_QUESTION_FIELDS = frozenset(
    {
        "question_id",
        "gap_id",
        "run_id",
        "kind",
        "subject_id",
        "text",
        "rank_score",
        "status",
        "generated_at",
        "decided_at",
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
        if self._byte_count + encoded_size > MAX_CURIOSITY_STORE_BYTES:
            raise OverflowError("Curiosity question store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Curiosity question store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileCuriosityQuestionStore:
    """Load and atomically replace a strict versioned question document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchCuriosityQuestion]:
        """Return validated questions, or an empty list when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_CURIOSITY_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                "Unable to read the curiosity question store."
            ) from error
        if len(encoded_document) > MAX_CURIOSITY_STORE_BYTES:
            raise ResearchError("The curiosity question store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read the curiosity question store."
            ) from error
        return self._parse_document(document)

    def save(self, questions: list[ResearchCuriosityQuestion]) -> None:
        """Atomically replace the complete question document."""
        self._validate_questions(questions)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "questions": [self._serialize(question) for question in questions],
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
            raise ResearchError("The curiosity question store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the curiosity question store."
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _serialize(question: ResearchCuriosityQuestion) -> dict[str, Any]:
        return {
            "question_id": question.question_id,
            "gap_id": question.gap_id,
            "run_id": question.run_id,
            "kind": question.kind.value,
            "subject_id": question.subject_id,
            "text": question.text,
            "rank_score": question.rank_score,
            "status": question.status.value,
            "generated_at": question.generated_at.isoformat(),
            "decided_at": (
                None if question.decided_at is None else question.decided_at.isoformat()
            ),
        }

    def _parse_document(self, document: object) -> list[ResearchCuriosityQuestion]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The curiosity question document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError(
                "The curiosity question store schema version is not supported."
            )
        questions_value = document["questions"]
        if not isinstance(questions_value, list):
            raise ResearchError("Curiosity question store questions must be a list.")
        if len(questions_value) > MAX_CURIOSITY_STORE_QUESTIONS:
            raise ResearchError("The curiosity question store has too many questions.")
        questions = [self._parse_question(value) for value in questions_value]
        self._validate_questions(questions)
        return questions

    @staticmethod
    def _parse_question(document: object) -> ResearchCuriosityQuestion:
        if not isinstance(document, dict) or set(document) != _QUESTION_FIELDS:
            raise ResearchError("A curiosity question document is invalid.")
        store = JsonFileCuriosityQuestionStore
        decided_at = document["decided_at"]
        return ResearchCuriosityQuestion(
            question_id=store._text(document["question_id"]),
            gap_id=store._text(document["gap_id"]),
            run_id=store._text(document["run_id"]),
            kind=store._kind(document["kind"]),
            subject_id=store._optional_text(document["subject_id"]),
            text=store._optional_text(document["text"]),
            rank_score=document["rank_score"],
            status=store._status(document["status"]),
            generated_at=store._timestamp(document["generated_at"]),
            decided_at=(None if decided_at is None else store._timestamp(decided_at)),
        )

    @staticmethod
    def _kind(value: object) -> ResearchKnowledgeGapKind:
        if not isinstance(value, str):
            raise ResearchError("A curiosity question kind is invalid.")
        try:
            return ResearchKnowledgeGapKind(value)
        except ValueError as error:
            raise ResearchError("A curiosity question kind is invalid.") from error

    @staticmethod
    def _status(value: object) -> CuriosityQuestionStatus:
        if not isinstance(value, str):
            raise ResearchError("A curiosity question status is invalid.")
        try:
            return CuriosityQuestionStatus(value)
        except ValueError as error:
            raise ResearchError("A curiosity question status is invalid.") from error

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A curiosity question identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A curiosity question text field is invalid.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A curiosity question timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("A curiosity question timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError(
                "A curiosity question timestamp must be timezone-aware."
            )
        return parsed

    def _validate_questions(
        self,
        questions: list[ResearchCuriosityQuestion],
    ) -> None:
        if not isinstance(questions, list):
            raise ResearchError("The curiosity question store accepts a list.")
        if len(questions) > MAX_CURIOSITY_STORE_QUESTIONS:
            raise ResearchError("The curiosity question store has too many questions.")
        if not all(
            isinstance(question, ResearchCuriosityQuestion) for question in questions
        ):
            raise ResearchError("The curiosity question store accepts only questions.")
        question_ids = [question.question_id for question in questions]
        if len(question_ids) != len(set(question_ids)):
            raise ResearchError(
                "The curiosity question store has duplicate question IDs."
            )
