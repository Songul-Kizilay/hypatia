"""Atomic file persistence for the append-only asset observation/relation log.

Schema version 2. Version 1 shipped with exactly one provenance kind
(`OPERATOR_AUTHORED`) and no `source_operation_digest`/relation `provenance`
fields; version 2 adds both, additively, following the same versioned-
field-set, `min_version`-parameterized decode cascade
`JsonFileResearchRunStore` established for `evidence_type`
(`_ASSESSMENT_FIELDS_V11`/`_ASSESSMENT_FIELDS_V21`). A v1-persisted record
decodes honestly as `OPERATOR_AUTHORED`/`None` — the only provenance that
could possibly be true when it was written, not a guess — and a v2 record
missing either new field fails closed. Modeled on
`JsonFileFailureLessonStore`'s simpler flat-list atomic-store shape, not
`JsonFileResearchProgramScopeRevisionStore`'s stricter forced-append-only-
history constraint (specific to that store's revocation semantics, not needed
here since observations/relations are already inherently append-only by
construction — this store never mutates a previously saved record in place,
it only ever replaces the whole list with one that is a superset of what a
caller already validated).
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
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import ResearchAssetObservationRecord
from research.ResearchAssetProvenanceKind import ResearchAssetProvenanceKind
from research.ResearchAssetRelationKind import ResearchAssetRelationKind
from research.ResearchAssetRelationRecord import ResearchAssetRelationRecord

#: Whole-file ceilings, deliberately global rather than per program: one
#: document holds every program's records, so a noisy program can exhaust
#: another's room to append. That is an availability bound on an
#: operator-authored log, never a content-isolation boundary (program
#: isolation is enforced per record), and a per-program cap would be a
#: design decision for whichever milestone first needs multi-program volume.
MAX_ASSET_INVENTORY_STORE_BYTES = 4 * 1024 * 1024
MAX_ASSET_OBSERVATIONS = 5_000
MAX_ASSET_RELATIONS = 5_000

_SCHEMA_VERSION = 2
_SUPPORTED_SCHEMA_VERSIONS = frozenset(range(1, _SCHEMA_VERSION + 1))
_DOCUMENT_FIELDS = frozenset({"schema_version", "observations", "relations"})
_OBSERVATION_FIELDS_V1 = frozenset(
    {
        "observation_id",
        "program_id",
        "kind",
        "canonical_value",
        "provenance",
        "note",
        "recorded_at",
    }
)
_OBSERVATION_FIELDS_V2 = _OBSERVATION_FIELDS_V1 | {"source_operation_digest"}
_RELATION_FIELDS_V1 = frozenset(
    {
        "relation_id",
        "program_id",
        "source_kind",
        "source_value",
        "related_kind",
        "related_value",
        "kind",
        "note",
        "recorded_at",
    }
)
_RELATION_FIELDS_V2 = _RELATION_FIELDS_V1 | {"provenance", "source_operation_digest"}


@dataclass(frozen=True, slots=True)
class ResearchAssetInventoryDocument:
    """The complete, flat, append-only asset inventory log for every program."""

    observations: tuple[ResearchAssetObservationRecord, ...] = ()
    relations: tuple[ResearchAssetRelationRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.observations, tuple) or any(
            not isinstance(value, ResearchAssetObservationRecord)
            for value in self.observations
        ):
            raise ResearchError("Asset inventory observations are invalid.")
        if not isinstance(self.relations, tuple) or any(
            not isinstance(value, ResearchAssetRelationRecord)
            for value in self.relations
        ):
            raise ResearchError("Asset inventory relations are invalid.")
        if len(self.observations) > MAX_ASSET_OBSERVATIONS:
            raise ResearchError("The asset inventory has too many observations.")
        if len(self.relations) > MAX_ASSET_RELATIONS:
            raise ResearchError("The asset inventory has too many relations.")
        observation_ids = [value.observation_id for value in self.observations]
        if len(observation_ids) != len(set(observation_ids)):
            raise ResearchError("The asset inventory has duplicate observation IDs.")
        relation_ids = [value.relation_id for value in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ResearchError("The asset inventory has duplicate relation IDs.")
        observed_assets = {
            (value.program_id, value.kind, value.canonical_value)
            for value in self.observations
        }
        for relation in self.relations:
            if (
                relation.program_id,
                relation.source_kind,
                relation.source_value,
            ) not in observed_assets or (
                relation.program_id,
                relation.related_kind,
                relation.related_value,
            ) not in observed_assets:
                raise ResearchError(
                    "An asset relation must reference observed assets in its program."
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
        if self._byte_count + encoded_size > MAX_ASSET_INVENTORY_STORE_BYTES:
            raise OverflowError("Asset inventory store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Asset inventory store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchAssetInventoryStore:
    """Load and atomically replace the complete asset inventory document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchAssetInventoryDocument:
        """Return the validated document, or an empty one when absent."""
        if not self._path.exists():
            return ResearchAssetInventoryDocument()
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_ASSET_INVENTORY_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the asset inventory store.") from error
        if len(encoded_document) > MAX_ASSET_INVENTORY_STORE_BYTES:
            raise ResearchError("The asset inventory store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the asset inventory store.") from error
        return self._parse_document(document)

    def save(self, document: ResearchAssetInventoryDocument) -> None:
        """Atomically append validated records without rewriting history."""
        if not isinstance(document, ResearchAssetInventoryDocument):
            raise ResearchError("The asset inventory store accepts only a document.")
        existing = self.load()
        if (
            document.observations[: len(existing.observations)] != existing.observations
            or document.relations[: len(existing.relations)] != existing.relations
        ):
            raise ResearchError(
                "Asset inventory records are append-only and cannot be replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "observations": [
                self._serialize_observation(value) for value in document.observations
            ],
            "relations": [
                self._serialize_relation(value) for value in document.relations
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
                bounded_file = _BoundedUtf8Writer(file)
                json.dump(encoded, bounded_file, ensure_ascii=False, indent=2)
                bounded_file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except OverflowError as error:
            raise ResearchError("The asset inventory store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the asset inventory store.") from error
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
    def _serialize_observation(
        observation: ResearchAssetObservationRecord,
    ) -> dict[str, Any]:
        return {
            "observation_id": observation.observation_id,
            "program_id": observation.program_id,
            "kind": observation.kind.value,
            "canonical_value": observation.canonical_value,
            "provenance": observation.provenance.value,
            "note": observation.note,
            "recorded_at": observation.recorded_at.isoformat(),
            "source_operation_digest": observation.source_operation_digest,
        }

    @staticmethod
    def _serialize_relation(relation: ResearchAssetRelationRecord) -> dict[str, Any]:
        return {
            "relation_id": relation.relation_id,
            "program_id": relation.program_id,
            "source_kind": relation.source_kind.value,
            "source_value": relation.source_value,
            "related_kind": relation.related_kind.value,
            "related_value": relation.related_value,
            "kind": relation.kind.value,
            "provenance": relation.provenance.value,
            "note": relation.note,
            "recorded_at": relation.recorded_at.isoformat(),
            "source_operation_digest": relation.source_operation_digest,
        }

    def _parse_document(self, document: object) -> ResearchAssetInventoryDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The asset inventory document is invalid.")
        schema_version = document["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version not in _SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ResearchError(
                "The asset inventory store schema version is not supported."
            )
        observations_value = document["observations"]
        if not isinstance(observations_value, list):
            raise ResearchError("Asset inventory observations must be a list.")
        if len(observations_value) > MAX_ASSET_OBSERVATIONS:
            raise ResearchError("The asset inventory has too many observations.")
        relations_value = document["relations"]
        if not isinstance(relations_value, list):
            raise ResearchError("Asset inventory relations must be a list.")
        if len(relations_value) > MAX_ASSET_RELATIONS:
            raise ResearchError("The asset inventory has too many relations.")
        observations = tuple(
            self._parse_observation(value, schema_version)
            for value in observations_value
        )
        relations = tuple(
            self._parse_relation(value, schema_version) for value in relations_value
        )
        return ResearchAssetInventoryDocument(
            observations=observations, relations=relations
        )

    @staticmethod
    def _parse_observation(
        document: object, schema_version: int
    ) -> ResearchAssetObservationRecord:
        expected_fields = (
            _OBSERVATION_FIELDS_V1 if schema_version < 2 else _OBSERVATION_FIELDS_V2
        )
        if not isinstance(document, dict) or set(document) != expected_fields:
            raise ResearchError("An asset observation document is invalid.")
        store = JsonFileResearchAssetInventoryStore
        return ResearchAssetObservationRecord(
            observation_id=store._text(document["observation_id"]),
            program_id=store._text(document["program_id"]),
            kind=store._kind(document["kind"]),
            canonical_value=store._text(document["canonical_value"]),
            provenance=store._provenance(document["provenance"]),
            note=store._optional_text(document["note"]),
            recorded_at=store._timestamp(document["recorded_at"]),
            source_operation_digest=(
                None
                if schema_version < 2
                else store._optional_digest(document["source_operation_digest"])
            ),
        )

    @staticmethod
    def _parse_relation(
        document: object, schema_version: int
    ) -> ResearchAssetRelationRecord:
        expected_fields = (
            _RELATION_FIELDS_V1 if schema_version < 2 else _RELATION_FIELDS_V2
        )
        if not isinstance(document, dict) or set(document) != expected_fields:
            raise ResearchError("An asset relation document is invalid.")
        store = JsonFileResearchAssetInventoryStore
        return ResearchAssetRelationRecord(
            relation_id=store._text(document["relation_id"]),
            program_id=store._text(document["program_id"]),
            source_kind=store._kind(document["source_kind"]),
            source_value=store._text(document["source_value"]),
            related_kind=store._kind(document["related_kind"]),
            related_value=store._text(document["related_value"]),
            kind=store._relation_kind(document["kind"]),
            provenance=(
                ResearchAssetProvenanceKind.OPERATOR_AUTHORED
                if schema_version < 2
                else store._provenance(document["provenance"])
            ),
            note=store._optional_text(document["note"]),
            recorded_at=store._timestamp(document["recorded_at"]),
            source_operation_digest=(
                None
                if schema_version < 2
                else store._optional_digest(document["source_operation_digest"])
            ),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("An asset inventory identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("An asset inventory text field is invalid.")
        return value

    @staticmethod
    def _optional_digest(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ResearchError("An asset inventory operation digest is invalid.")
        return value

    @staticmethod
    def _kind(value: object) -> ResearchAssetKind:
        if not isinstance(value, str):
            raise ResearchError("An asset kind is invalid.")
        try:
            return ResearchAssetKind(value)
        except ValueError as error:
            raise ResearchError("An asset kind is invalid.") from error

    @staticmethod
    def _provenance(value: object) -> ResearchAssetProvenanceKind:
        if not isinstance(value, str):
            raise ResearchError("An asset provenance is invalid.")
        try:
            return ResearchAssetProvenanceKind(value)
        except ValueError as error:
            raise ResearchError("An asset provenance is invalid.") from error

    @staticmethod
    def _relation_kind(value: object) -> ResearchAssetRelationKind:
        if not isinstance(value, str):
            raise ResearchError("An asset relation kind is invalid.")
        try:
            return ResearchAssetRelationKind(value)
        except ValueError as error:
            raise ResearchError("An asset relation kind is invalid.") from error

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("An asset inventory timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("An asset inventory timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("An asset inventory timestamp must be timezone-aware.")
        return parsed
