"""Atomic file persistence for the append-only security hypothesis log.

Schema version 1 (a new store, no legacy version to carry). Modeled directly
on `JsonFileResearchAssetInventoryStore`'s shape: one document holding three
flat lists (hypotheses, evidence links, status transitions), strict
field-set validation, bounded record-count/size ceilings, globally-unique ID
rejection independently for each of the three ID spaces, atomic
temp-file-then-`os.replace` write. This store never mutates a previously
saved record in place; `save` only ever replaces the whole document with one
that is a superset of what was already persisted (append-only by
construction).

An evidence link or status transition must reference a hypothesis already
present in the same document — the same "no dangling relation" discipline
`ResearchAssetInventoryDocument` enforces for `RESOLVES_TO` relations — as
defence in depth against a hand-edited or partially-written file, on top of
the application service's own referential checks.
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
from research.ResearchSecurityHypothesisEvidenceKind import (
    ResearchSecurityHypothesisEvidenceKind,
)
from research.ResearchSecurityHypothesisEvidenceLinkRecord import (
    ResearchSecurityHypothesisEvidenceLinkRecord,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSecurityHypothesisRecord import ResearchSecurityHypothesisRecord
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from research.ResearchSecurityHypothesisStatusTransitionRecord import (
    ResearchSecurityHypothesisStatusTransitionRecord,
)

#: Whole-file ceilings, mirroring `JsonFileResearchAssetInventoryStore`'s own
#: global-rather-than-per-program bounds: one document holds every program's
#: records, so this is an availability bound on an operator-authored log, not
#: a content-isolation boundary (program isolation is enforced per record).
MAX_SECURITY_HYPOTHESIS_STORE_BYTES = 4 * 1024 * 1024
MAX_SECURITY_HYPOTHESES = 5_000
MAX_SECURITY_HYPOTHESIS_EVIDENCE_LINKS = 5_000
MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITIONS = 5_000

_SCHEMA_VERSION = 1
_SUPPORTED_SCHEMA_VERSIONS = frozenset({_SCHEMA_VERSION})
_DOCUMENT_FIELDS = frozenset(
    {"schema_version", "hypotheses", "evidence_links", "status_transitions"}
)
_HYPOTHESIS_FIELDS = frozenset(
    {
        "hypothesis_id",
        "program_id",
        "hypothesis_kind",
        "subject_kind",
        "subject_canonical_value",
        "statement",
        "rationale",
        "required_validation",
        "origin",
        "created_at",
    }
)
_EVIDENCE_LINK_FIELDS = frozenset(
    {
        "link_id",
        "hypothesis_id",
        "program_id",
        "evidence_kind",
        "evidence_id",
        "relation",
        "recorded_at",
    }
)
_STATUS_TRANSITION_FIELDS = frozenset(
    {
        "transition_id",
        "hypothesis_id",
        "program_id",
        "status",
        "reason",
        "recorded_at",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchSecurityHypothesisDocument:
    """The complete, flat, append-only security hypothesis log for every program."""

    hypotheses: tuple[ResearchSecurityHypothesisRecord, ...] = ()
    evidence_links: tuple[ResearchSecurityHypothesisEvidenceLinkRecord, ...] = ()
    status_transitions: tuple[
        ResearchSecurityHypothesisStatusTransitionRecord, ...
    ] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.hypotheses, tuple) or any(
            not isinstance(value, ResearchSecurityHypothesisRecord)
            for value in self.hypotheses
        ):
            raise ResearchError("Security hypotheses are invalid.")
        if not isinstance(self.evidence_links, tuple) or any(
            not isinstance(value, ResearchSecurityHypothesisEvidenceLinkRecord)
            for value in self.evidence_links
        ):
            raise ResearchError("Security hypothesis evidence links are invalid.")
        if not isinstance(self.status_transitions, tuple) or any(
            not isinstance(value, ResearchSecurityHypothesisStatusTransitionRecord)
            for value in self.status_transitions
        ):
            raise ResearchError("Security hypothesis status transitions are invalid.")
        if len(self.hypotheses) > MAX_SECURITY_HYPOTHESES:
            raise ResearchError("The security hypothesis store has too many records.")
        if len(self.evidence_links) > MAX_SECURITY_HYPOTHESIS_EVIDENCE_LINKS:
            raise ResearchError(
                "The security hypothesis store has too many evidence links."
            )
        if len(self.status_transitions) > MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITIONS:
            raise ResearchError(
                "The security hypothesis store has too many status transitions."
            )
        hypothesis_ids = [value.hypothesis_id for value in self.hypotheses]
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ResearchError(
                "The security hypothesis store has duplicate hypothesis IDs."
            )
        link_ids = [value.link_id for value in self.evidence_links]
        if len(link_ids) != len(set(link_ids)):
            raise ResearchError(
                "The security hypothesis store has duplicate evidence link IDs."
            )
        transition_ids = [value.transition_id for value in self.status_transitions]
        if len(transition_ids) != len(set(transition_ids)):
            raise ResearchError(
                "The security hypothesis store has duplicate status transition IDs."
            )
        known_hypotheses = {
            (value.hypothesis_id, value.program_id) for value in self.hypotheses
        }
        for link in self.evidence_links:
            if (link.hypothesis_id, link.program_id) not in known_hypotheses:
                raise ResearchError(
                    "A security hypothesis evidence link must reference a"
                    " recorded hypothesis in its program."
                )
        for transition in self.status_transitions:
            if (
                transition.hypothesis_id,
                transition.program_id,
            ) not in known_hypotheses:
                raise ResearchError(
                    "A security hypothesis status transition must reference a"
                    " recorded hypothesis in its program."
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
        if self._byte_count + encoded_size > MAX_SECURITY_HYPOTHESIS_STORE_BYTES:
            raise OverflowError("Security hypothesis store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Security hypothesis store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchSecurityHypothesisStore:
    """Load and atomically replace the complete security hypothesis document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchSecurityHypothesisDocument:
        """Return the validated document, or an empty one when absent."""
        if not self._path.exists():
            return ResearchSecurityHypothesisDocument()
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_SECURITY_HYPOTHESIS_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                "Unable to read the security hypothesis store."
            ) from error
        if len(encoded_document) > MAX_SECURITY_HYPOTHESIS_STORE_BYTES:
            raise ResearchError("The security hypothesis store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read the security hypothesis store."
            ) from error
        return self._parse_document(document)

    def save(self, document: ResearchSecurityHypothesisDocument) -> None:
        """Atomically append validated records without rewriting history."""
        if not isinstance(document, ResearchSecurityHypothesisDocument):
            raise ResearchError(
                "The security hypothesis store accepts only a document."
            )
        existing = self.load()
        if (
            document.hypotheses[: len(existing.hypotheses)] != existing.hypotheses
            or document.evidence_links[: len(existing.evidence_links)]
            != existing.evidence_links
            or document.status_transitions[: len(existing.status_transitions)]
            != existing.status_transitions
        ):
            raise ResearchError(
                "Security hypothesis records are append-only and cannot be" " replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "hypotheses": [
                self._serialize_hypothesis(value) for value in document.hypotheses
            ],
            "evidence_links": [
                self._serialize_evidence_link(value)
                for value in document.evidence_links
            ],
            "status_transitions": [
                self._serialize_status_transition(value)
                for value in document.status_transitions
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
            raise ResearchError(
                "The security hypothesis store is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the security hypothesis store."
            ) from error
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
    def _serialize_hypothesis(
        value: ResearchSecurityHypothesisRecord,
    ) -> dict[str, Any]:
        return {
            "hypothesis_id": value.hypothesis_id,
            "program_id": value.program_id,
            "hypothesis_kind": value.hypothesis_kind.value,
            "subject_kind": value.subject_kind.value,
            "subject_canonical_value": value.subject_canonical_value,
            "statement": value.statement,
            "rationale": value.rationale,
            "required_validation": value.required_validation,
            "origin": value.origin.value,
            "created_at": value.created_at.isoformat(),
        }

    @staticmethod
    def _serialize_evidence_link(
        value: ResearchSecurityHypothesisEvidenceLinkRecord,
    ) -> dict[str, Any]:
        return {
            "link_id": value.link_id,
            "hypothesis_id": value.hypothesis_id,
            "program_id": value.program_id,
            "evidence_kind": value.evidence_kind.value,
            "evidence_id": value.evidence_id,
            "relation": value.relation.value,
            "recorded_at": value.recorded_at.isoformat(),
        }

    @staticmethod
    def _serialize_status_transition(
        value: ResearchSecurityHypothesisStatusTransitionRecord,
    ) -> dict[str, Any]:
        return {
            "transition_id": value.transition_id,
            "hypothesis_id": value.hypothesis_id,
            "program_id": value.program_id,
            "status": value.status.value,
            "reason": value.reason,
            "recorded_at": value.recorded_at.isoformat(),
        }

    def _parse_document(self, document: object) -> ResearchSecurityHypothesisDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The security hypothesis document is invalid.")
        schema_version = document["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version not in _SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ResearchError(
                "The security hypothesis store schema version is not supported."
            )
        hypotheses_value = document["hypotheses"]
        if not isinstance(hypotheses_value, list):
            raise ResearchError("Security hypotheses must be a list.")
        if len(hypotheses_value) > MAX_SECURITY_HYPOTHESES:
            raise ResearchError("The security hypothesis store has too many records.")
        evidence_links_value = document["evidence_links"]
        if not isinstance(evidence_links_value, list):
            raise ResearchError("Security hypothesis evidence links must be a list.")
        if len(evidence_links_value) > MAX_SECURITY_HYPOTHESIS_EVIDENCE_LINKS:
            raise ResearchError(
                "The security hypothesis store has too many evidence links."
            )
        status_transitions_value = document["status_transitions"]
        if not isinstance(status_transitions_value, list):
            raise ResearchError(
                "Security hypothesis status transitions must be a list."
            )
        if len(status_transitions_value) > MAX_SECURITY_HYPOTHESIS_STATUS_TRANSITIONS:
            raise ResearchError(
                "The security hypothesis store has too many status transitions."
            )
        hypotheses = tuple(self._parse_hypothesis(value) for value in hypotheses_value)
        evidence_links = tuple(
            self._parse_evidence_link(value) for value in evidence_links_value
        )
        status_transitions = tuple(
            self._parse_status_transition(value) for value in status_transitions_value
        )
        return ResearchSecurityHypothesisDocument(
            hypotheses=hypotheses,
            evidence_links=evidence_links,
            status_transitions=status_transitions,
        )

    @staticmethod
    def _parse_hypothesis(document: object) -> ResearchSecurityHypothesisRecord:
        if not isinstance(document, dict) or set(document) != _HYPOTHESIS_FIELDS:
            raise ResearchError("A security hypothesis document is invalid.")
        store = JsonFileResearchSecurityHypothesisStore
        return ResearchSecurityHypothesisRecord(
            hypothesis_id=store._text(document["hypothesis_id"]),
            program_id=store._text(document["program_id"]),
            hypothesis_kind=store._hypothesis_kind(document["hypothesis_kind"]),
            subject_kind=store._asset_kind(document["subject_kind"]),
            subject_canonical_value=store._text(document["subject_canonical_value"]),
            statement=store._text(document["statement"]),
            rationale=store._text(document["rationale"]),
            required_validation=store._text(document["required_validation"]),
            origin=store._origin(document["origin"]),
            created_at=store._timestamp(document["created_at"]),
        )

    @staticmethod
    def _parse_evidence_link(
        document: object,
    ) -> ResearchSecurityHypothesisEvidenceLinkRecord:
        if not isinstance(document, dict) or set(document) != _EVIDENCE_LINK_FIELDS:
            raise ResearchError("A security hypothesis evidence link is invalid.")
        store = JsonFileResearchSecurityHypothesisStore
        return ResearchSecurityHypothesisEvidenceLinkRecord(
            link_id=store._text(document["link_id"]),
            hypothesis_id=store._text(document["hypothesis_id"]),
            program_id=store._text(document["program_id"]),
            evidence_kind=store._evidence_kind(document["evidence_kind"]),
            evidence_id=store._text(document["evidence_id"]),
            relation=store._relation(document["relation"]),
            recorded_at=store._timestamp(document["recorded_at"]),
        )

    @staticmethod
    def _parse_status_transition(
        document: object,
    ) -> ResearchSecurityHypothesisStatusTransitionRecord:
        if not isinstance(document, dict) or set(document) != _STATUS_TRANSITION_FIELDS:
            raise ResearchError(
                "A security hypothesis status transition document is invalid."
            )
        store = JsonFileResearchSecurityHypothesisStore
        return ResearchSecurityHypothesisStatusTransitionRecord(
            transition_id=store._text(document["transition_id"]),
            hypothesis_id=store._text(document["hypothesis_id"]),
            program_id=store._text(document["program_id"]),
            status=store._status(document["status"]),
            reason=store._optional_text(document["reason"]),
            recorded_at=store._timestamp(document["recorded_at"]),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A security hypothesis identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis text field is invalid.")
        return value

    @staticmethod
    def _asset_kind(value: object) -> ResearchAssetKind:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis subject kind is invalid.")
        try:
            return ResearchAssetKind(value)
        except ValueError as error:
            raise ResearchError(
                "A security hypothesis subject kind is invalid."
            ) from error

    @staticmethod
    def _hypothesis_kind(value: object) -> ResearchSecurityHypothesisKind:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis kind is invalid.")
        try:
            return ResearchSecurityHypothesisKind(value)
        except ValueError as error:
            raise ResearchError("A security hypothesis kind is invalid.") from error

    @staticmethod
    def _origin(value: object) -> ResearchSecurityHypothesisOrigin:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis origin is invalid.")
        try:
            return ResearchSecurityHypothesisOrigin(value)
        except ValueError as error:
            raise ResearchError("A security hypothesis origin is invalid.") from error

    @staticmethod
    def _evidence_kind(value: object) -> ResearchSecurityHypothesisEvidenceKind:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis evidence kind is invalid.")
        try:
            return ResearchSecurityHypothesisEvidenceKind(value)
        except ValueError as error:
            raise ResearchError(
                "A security hypothesis evidence kind is invalid."
            ) from error

    @staticmethod
    def _relation(value: object) -> ResearchSecurityHypothesisEvidenceRelation:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis evidence relation is invalid.")
        try:
            return ResearchSecurityHypothesisEvidenceRelation(value)
        except ValueError as error:
            raise ResearchError(
                "A security hypothesis evidence relation is invalid."
            ) from error

    @staticmethod
    def _status(value: object) -> ResearchSecurityHypothesisStatus:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis status is invalid.")
        try:
            return ResearchSecurityHypothesisStatus(value)
        except ValueError as error:
            raise ResearchError("A security hypothesis status is invalid.") from error

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A security hypothesis timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError(
                "A security hypothesis timestamp is invalid."
            ) from error
        if parsed.utcoffset() is None:
            raise ResearchError(
                "A security hypothesis timestamp must be timezone-aware."
            )
        return parsed
