"""Strict atomic persistence for append-only reproduction records.

Schema version 1 (a new store, no legacy version to carry). Modeled
directly on `JsonFileResearchSecurityValidationRecipeStore`'s shape: one
document holding one flat list of immutable, operator-authored records,
strict field-set validation, a bounded record-count/byte ceiling,
globally-unique ID rejection, atomic temp-file-then-`os.replace` write,
append-only `save` (only ever accepts a document whose records are a
superset-by-prefix of what is already persisted). This store never mutates
a previously saved record in place and never re-orders persisted records.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

MAX_REPRODUCTION_STORE_BYTES = 2 * 1024 * 1024
MAX_REPRODUCTIONS = 5_000

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "reproductions"})
_REPRODUCTION_FIELDS = frozenset(
    {
        "reproduction_id",
        "program_id",
        "recipe_id",
        "subject_kind",
        "subject_id",
        "outcome",
        "notes",
        "evidence_ids",
        "recorded_at",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchReproductionDocument:
    reproductions: tuple[ResearchReproductionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reproductions, tuple) or any(
            not isinstance(value, ResearchReproductionRecord)
            for value in self.reproductions
        ):
            raise ResearchError("Reproduction records are invalid.")
        if len(self.reproductions) > MAX_REPRODUCTIONS:
            raise ResearchError("The reproduction store has too many records.")
        identities = [value.reproduction_id for value in self.reproductions]
        if len(identities) != len(set(identities)):
            raise ResearchError(
                "The reproduction store has duplicate reproduction IDs."
            )


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        if self._byte_count + len(encoded) > MAX_REPRODUCTION_STORE_BYTES:
            raise OverflowError("Reproduction store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != len(encoded):
            raise OSError("Reproduction temporary write was incomplete.")
        self._byte_count += len(encoded)
        return len(value)


class JsonFileResearchReproductionStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchReproductionDocument:
        if not self._path.exists():
            return ResearchReproductionDocument()
        try:
            with self._path.open("rb") as file:
                encoded = file.read(MAX_REPRODUCTION_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the reproduction store.") from error
        if len(encoded) > MAX_REPRODUCTION_STORE_BYTES:
            raise ResearchError("The reproduction store is too large.")
        try:
            document = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the reproduction store.") from error
        return self._parse_document(document)

    def save(self, document: ResearchReproductionDocument) -> None:
        if not isinstance(document, ResearchReproductionDocument):
            raise ResearchError("The reproduction store accepts only a document.")
        existing = self.load()
        if (
            document.reproductions[: len(existing.reproductions)]
            != existing.reproductions
        ):
            raise ResearchError(
                "Reproduction records are append-only and cannot be replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "reproductions": [
                self._serialize(reproduction) for reproduction in document.reproductions
            ],
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
            raise ResearchError("The reproduction store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the reproduction store.") from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _serialize(reproduction: ResearchReproductionRecord) -> dict[str, Any]:
        return {
            "reproduction_id": reproduction.reproduction_id,
            "program_id": reproduction.program_id,
            "recipe_id": reproduction.recipe_id,
            "subject_kind": reproduction.subject_kind.value,
            "subject_id": reproduction.subject_id,
            "outcome": reproduction.outcome.value,
            "notes": reproduction.notes,
            "evidence_ids": list(reproduction.evidence_ids),
            "recorded_at": reproduction.recorded_at.isoformat(),
        }

    @staticmethod
    def _parse_document(document: object) -> ResearchReproductionDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The reproduction document is invalid.")
        version = document["schema_version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != _SCHEMA_VERSION
        ):
            raise ResearchError(
                "The reproduction store schema version is not supported."
            )
        reproductions = document["reproductions"]
        if (
            not isinstance(reproductions, list)
            or len(reproductions) > MAX_REPRODUCTIONS
        ):
            raise ResearchError("Reproduction records must be a bounded list.")
        return ResearchReproductionDocument(
            reproductions=tuple(
                JsonFileResearchReproductionStore._parse_reproduction(v)
                for v in reproductions
            )
        )

    @staticmethod
    def _parse_reproduction(document: object) -> ResearchReproductionRecord:
        if not isinstance(document, dict) or set(document) != _REPRODUCTION_FIELDS:
            raise ResearchError("A reproduction document is invalid.")
        subject_kind = document["subject_kind"]
        if not isinstance(subject_kind, str):
            raise ResearchError("Reproduction subject kind is invalid.")
        try:
            parsed_subject_kind = ResearchSecurityValidationRecipeSubjectKind(
                subject_kind
            )
        except ValueError as error:
            raise ResearchError("Reproduction subject kind is invalid.") from error
        outcome = document["outcome"]
        if not isinstance(outcome, str):
            raise ResearchError("Reproduction outcome is invalid.")
        try:
            parsed_outcome = ResearchReproductionOutcome(outcome)
        except ValueError as error:
            raise ResearchError("Reproduction outcome is invalid.") from error
        evidence_ids = document["evidence_ids"]
        if not isinstance(evidence_ids, list) or any(
            not isinstance(value, str) for value in evidence_ids
        ):
            raise ResearchError("Reproduction evidence IDs are invalid.")
        notes = document["notes"]
        if not isinstance(notes, str):
            raise ResearchError("Reproduction notes are invalid.")
        recorded_at = document["recorded_at"]
        if not isinstance(recorded_at, str):
            raise ResearchError("Reproduction recording timestamp is invalid.")
        try:
            timestamp = datetime.fromisoformat(recorded_at)
        except ValueError as error:
            raise ResearchError(
                "Reproduction recording timestamp is invalid."
            ) from error
        return ResearchReproductionRecord(
            reproduction_id=JsonFileResearchReproductionStore._text(
                document["reproduction_id"]
            ),
            program_id=JsonFileResearchReproductionStore._text(document["program_id"]),
            recipe_id=JsonFileResearchReproductionStore._text(document["recipe_id"]),
            subject_kind=parsed_subject_kind,
            subject_id=JsonFileResearchReproductionStore._text(document["subject_id"]),
            outcome=parsed_outcome,
            notes=notes,
            evidence_ids=tuple(evidence_ids),
            recorded_at=timestamp,
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A reproduction identifier cannot be empty.")
        return value
