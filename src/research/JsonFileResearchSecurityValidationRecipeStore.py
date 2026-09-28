"""Strict atomic persistence for append-only security validation recipes.

Schema version 1 (a new store, no legacy version to carry). Modeled directly
on `JsonFileResearchSessionContextStore`'s shape: one document holding one
flat list of immutable, operator-authored records, strict field-set
validation, a bounded record-count/byte ceiling, globally-unique ID
rejection, atomic temp-file-then-`os.replace` write, append-only `save`
(only ever accepts a document whose records are a superset-by-prefix of what
is already persisted). This store never mutates a previously saved record in
place and never re-orders persisted records.
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
from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)

MAX_SECURITY_VALIDATION_RECIPE_STORE_BYTES = 2 * 1024 * 1024
MAX_SECURITY_VALIDATION_RECIPES = 5_000

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "recipes"})
_RECIPE_FIELDS = frozenset(
    {
        "recipe_id",
        "program_id",
        "subject_kind",
        "subject_id",
        "steps",
        "notes",
        "created_at",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchSecurityValidationRecipeDocument:
    recipes: tuple[ResearchSecurityValidationRecipeRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.recipes, tuple) or any(
            not isinstance(value, ResearchSecurityValidationRecipeRecord)
            for value in self.recipes
        ):
            raise ResearchError("Security validation recipes are invalid.")
        if len(self.recipes) > MAX_SECURITY_VALIDATION_RECIPES:
            raise ResearchError(
                "The security validation recipe store has too many records."
            )
        identities = [value.recipe_id for value in self.recipes]
        if len(identities) != len(set(identities)):
            raise ResearchError(
                "The security validation recipe store has duplicate recipe IDs."
            )


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        if self._byte_count + len(encoded) > MAX_SECURITY_VALIDATION_RECIPE_STORE_BYTES:
            raise OverflowError("Security validation recipe store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != len(encoded):
            raise OSError("Security validation recipe temporary write was incomplete.")
        self._byte_count += len(encoded)
        return len(value)


class JsonFileResearchSecurityValidationRecipeStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchSecurityValidationRecipeDocument:
        if not self._path.exists():
            return ResearchSecurityValidationRecipeDocument()
        try:
            with self._path.open("rb") as file:
                encoded = file.read(MAX_SECURITY_VALIDATION_RECIPE_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                "Unable to read the security validation recipe store."
            ) from error
        if len(encoded) > MAX_SECURITY_VALIDATION_RECIPE_STORE_BYTES:
            raise ResearchError("The security validation recipe store is too large.")
        try:
            document = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read the security validation recipe store."
            ) from error
        return self._parse_document(document)

    def save(self, document: ResearchSecurityValidationRecipeDocument) -> None:
        if not isinstance(document, ResearchSecurityValidationRecipeDocument):
            raise ResearchError(
                "The security validation recipe store accepts only a document."
            )
        existing = self.load()
        if document.recipes[: len(existing.recipes)] != existing.recipes:
            raise ResearchError(
                "Security validation recipes are append-only and cannot be" " replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "recipes": [self._serialize_recipe(recipe) for recipe in document.recipes],
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
                "The security validation recipe store is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the security validation recipe store."
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _serialize_recipe(
        recipe: ResearchSecurityValidationRecipeRecord,
    ) -> dict[str, Any]:
        return {
            "recipe_id": recipe.recipe_id,
            "program_id": recipe.program_id,
            "subject_kind": recipe.subject_kind.value,
            "subject_id": recipe.subject_id,
            "steps": list(recipe.steps),
            "notes": recipe.notes,
            "created_at": recipe.created_at.isoformat(),
        }

    @staticmethod
    def _parse_document(document: object) -> ResearchSecurityValidationRecipeDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The security validation recipe document is invalid.")
        version = document["schema_version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != _SCHEMA_VERSION
        ):
            raise ResearchError(
                "The security validation recipe store schema version is not"
                " supported."
            )
        recipes = document["recipes"]
        if (
            not isinstance(recipes, list)
            or len(recipes) > MAX_SECURITY_VALIDATION_RECIPES
        ):
            raise ResearchError("Security validation recipes must be a bounded list.")
        return ResearchSecurityValidationRecipeDocument(
            recipes=tuple(
                JsonFileResearchSecurityValidationRecipeStore._parse_recipe(v)
                for v in recipes
            )
        )

    @staticmethod
    def _parse_recipe(document: object) -> ResearchSecurityValidationRecipeRecord:
        if not isinstance(document, dict) or set(document) != _RECIPE_FIELDS:
            raise ResearchError("A security validation recipe document is invalid.")
        subject_kind = document["subject_kind"]
        if not isinstance(subject_kind, str):
            raise ResearchError("Security validation recipe subject kind is invalid.")
        try:
            parsed_subject_kind = ResearchSecurityValidationRecipeSubjectKind(
                subject_kind
            )
        except ValueError as error:
            raise ResearchError(
                "Security validation recipe subject kind is invalid."
            ) from error
        steps = document["steps"]
        if not isinstance(steps, list) or any(
            not isinstance(value, str) for value in steps
        ):
            raise ResearchError("Security validation recipe steps are invalid.")
        created_at = document["created_at"]
        if not isinstance(created_at, str):
            raise ResearchError(
                "Security validation recipe creation timestamp is invalid."
            )
        try:
            timestamp = datetime.fromisoformat(created_at)
        except ValueError as error:
            raise ResearchError(
                "Security validation recipe creation timestamp is invalid."
            ) from error
        notes = document["notes"]
        if not isinstance(notes, str):
            raise ResearchError("Security validation recipe notes are invalid.")
        return ResearchSecurityValidationRecipeRecord(
            recipe_id=JsonFileResearchSecurityValidationRecipeStore._text(
                document["recipe_id"]
            ),
            program_id=JsonFileResearchSecurityValidationRecipeStore._text(
                document["program_id"]
            ),
            subject_kind=parsed_subject_kind,
            subject_id=JsonFileResearchSecurityValidationRecipeStore._text(
                document["subject_id"]
            ),
            steps=tuple(steps),
            notes=notes,
            created_at=timestamp,
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(
                "A security validation recipe identifier cannot be empty."
            )
        return value
