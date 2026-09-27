"""Atomic file persistence for the append-only security finding log.

Schema version 1 (a new store, no legacy version to carry). Modeled directly
on `JsonFileResearchSecurityHypothesisStore`'s shape: one document holding
three flat lists (findings, evidence links, status transitions), strict
field-set validation, bounded record-count/size ceilings, globally-unique ID
rejection independently for each of the three ID spaces, atomic
temp-file-then-`os.replace` write. This store never mutates a previously
saved record in place; `save` only ever replaces the whole document with one
that is a superset of what was already persisted (append-only by
construction).

An evidence link or status transition must reference a finding already
present in the same document — the same "no dangling relation" discipline
`JsonFileResearchSecurityHypothesisStore` enforces — as defence in depth
against a hand-edited or partially-written file, on top of the application
service's own referential checks.
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
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingRecord import ResearchSecurityFindingRecord
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind

#: Whole-file ceilings, mirroring
#: `JsonFileResearchSecurityHypothesisStore`'s own global-rather-than-
#: per-program bounds: one document holds every program's records, so this is
#: an availability bound on an operator-authored log, not a content-isolation
#: boundary (program isolation is enforced per record).
MAX_SECURITY_FINDING_STORE_BYTES = 4 * 1024 * 1024
MAX_SECURITY_FINDINGS = 5_000
MAX_SECURITY_FINDING_EVIDENCE_LINKS = 5_000
MAX_SECURITY_FINDING_STATUS_TRANSITIONS = 5_000

_SCHEMA_VERSION = 1
_SUPPORTED_SCHEMA_VERSIONS = frozenset({_SCHEMA_VERSION})
_DOCUMENT_FIELDS = frozenset(
    {"schema_version", "findings", "evidence_links", "status_transitions"}
)
_FINDING_FIELDS = frozenset(
    {
        "finding_id",
        "program_id",
        "source_hypothesis_id",
        "finding_kind",
        "subject_kind",
        "subject_canonical_value",
        "title",
        "description",
        "required_followup",
        "origin",
        "created_at",
    }
)
_EVIDENCE_LINK_FIELDS = frozenset(
    {
        "link_id",
        "finding_id",
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
        "finding_id",
        "program_id",
        "status",
        "reason",
        "duplicate_of_finding_id",
        "superseded_by_finding_id",
        "recorded_at",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchSecurityFindingDocument:
    """The complete, flat, append-only security finding log for every program."""

    findings: tuple[ResearchSecurityFindingRecord, ...] = ()
    evidence_links: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...] = ()
    status_transitions: tuple[ResearchSecurityFindingStatusTransitionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.findings, tuple) or any(
            not isinstance(value, ResearchSecurityFindingRecord)
            for value in self.findings
        ):
            raise ResearchError("Security findings are invalid.")
        if not isinstance(self.evidence_links, tuple) or any(
            not isinstance(value, ResearchSecurityFindingEvidenceLinkRecord)
            for value in self.evidence_links
        ):
            raise ResearchError("Security finding evidence links are invalid.")
        if not isinstance(self.status_transitions, tuple) or any(
            not isinstance(value, ResearchSecurityFindingStatusTransitionRecord)
            for value in self.status_transitions
        ):
            raise ResearchError("Security finding status transitions are invalid.")
        if len(self.findings) > MAX_SECURITY_FINDINGS:
            raise ResearchError("The security finding store has too many records.")
        if len(self.evidence_links) > MAX_SECURITY_FINDING_EVIDENCE_LINKS:
            raise ResearchError(
                "The security finding store has too many evidence links."
            )
        if len(self.status_transitions) > MAX_SECURITY_FINDING_STATUS_TRANSITIONS:
            raise ResearchError(
                "The security finding store has too many status transitions."
            )
        finding_ids = [value.finding_id for value in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ResearchError("The security finding store has duplicate finding IDs.")
        link_ids = [value.link_id for value in self.evidence_links]
        if len(link_ids) != len(set(link_ids)):
            raise ResearchError(
                "The security finding store has duplicate evidence link IDs."
            )
        transition_ids = [value.transition_id for value in self.status_transitions]
        if len(transition_ids) != len(set(transition_ids)):
            raise ResearchError(
                "The security finding store has duplicate status transition IDs."
            )
        known_findings = {
            (value.finding_id, value.program_id) for value in self.findings
        }
        for link in self.evidence_links:
            if (link.finding_id, link.program_id) not in known_findings:
                raise ResearchError(
                    "A security finding evidence link must reference a recorded"
                    " finding in its program."
                )
        for transition in self.status_transitions:
            if (transition.finding_id, transition.program_id) not in known_findings:
                raise ResearchError(
                    "A security finding status transition must reference a"
                    " recorded finding in its program."
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
        if self._byte_count + encoded_size > MAX_SECURITY_FINDING_STORE_BYTES:
            raise OverflowError("Security finding store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Security finding store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchSecurityFindingStore:
    """Load and atomically replace the complete security finding document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchSecurityFindingDocument:
        """Return the validated document, or an empty one when absent."""
        if not self._path.exists():
            return ResearchSecurityFindingDocument()
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_SECURITY_FINDING_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the security finding store.") from error
        if len(encoded_document) > MAX_SECURITY_FINDING_STORE_BYTES:
            raise ResearchError("The security finding store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the security finding store.") from error
        return self._parse_document(document)

    def save(self, document: ResearchSecurityFindingDocument) -> None:
        """Atomically append validated records without rewriting history."""
        if not isinstance(document, ResearchSecurityFindingDocument):
            raise ResearchError("The security finding store accepts only a document.")
        existing = self.load()
        if (
            document.findings[: len(existing.findings)] != existing.findings
            or document.evidence_links[: len(existing.evidence_links)]
            != existing.evidence_links
            or document.status_transitions[: len(existing.status_transitions)]
            != existing.status_transitions
        ):
            raise ResearchError(
                "Security finding records are append-only and cannot be replaced."
            )
        encoded = {
            "schema_version": _SCHEMA_VERSION,
            "findings": [self._serialize_finding(value) for value in document.findings],
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
            raise ResearchError("The security finding store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the security finding store."
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
    def _serialize_finding(value: ResearchSecurityFindingRecord) -> dict[str, Any]:
        return {
            "finding_id": value.finding_id,
            "program_id": value.program_id,
            "source_hypothesis_id": value.source_hypothesis_id,
            "finding_kind": value.finding_kind.value,
            "subject_kind": value.subject_kind.value,
            "subject_canonical_value": value.subject_canonical_value,
            "title": value.title,
            "description": value.description,
            "required_followup": value.required_followup,
            "origin": value.origin.value,
            "created_at": value.created_at.isoformat(),
        }

    @staticmethod
    def _serialize_evidence_link(
        value: ResearchSecurityFindingEvidenceLinkRecord,
    ) -> dict[str, Any]:
        return {
            "link_id": value.link_id,
            "finding_id": value.finding_id,
            "program_id": value.program_id,
            "evidence_kind": value.evidence_kind.value,
            "evidence_id": value.evidence_id,
            "relation": value.relation.value,
            "recorded_at": value.recorded_at.isoformat(),
        }

    @staticmethod
    def _serialize_status_transition(
        value: ResearchSecurityFindingStatusTransitionRecord,
    ) -> dict[str, Any]:
        return {
            "transition_id": value.transition_id,
            "finding_id": value.finding_id,
            "program_id": value.program_id,
            "status": value.status.value,
            "reason": value.reason,
            "duplicate_of_finding_id": value.duplicate_of_finding_id,
            "superseded_by_finding_id": value.superseded_by_finding_id,
            "recorded_at": value.recorded_at.isoformat(),
        }

    def _parse_document(self, document: object) -> ResearchSecurityFindingDocument:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The security finding document is invalid.")
        schema_version = document["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version not in _SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ResearchError(
                "The security finding store schema version is not supported."
            )
        findings_value = document["findings"]
        if not isinstance(findings_value, list):
            raise ResearchError("Security findings must be a list.")
        if len(findings_value) > MAX_SECURITY_FINDINGS:
            raise ResearchError("The security finding store has too many records.")
        evidence_links_value = document["evidence_links"]
        if not isinstance(evidence_links_value, list):
            raise ResearchError("Security finding evidence links must be a list.")
        if len(evidence_links_value) > MAX_SECURITY_FINDING_EVIDENCE_LINKS:
            raise ResearchError(
                "The security finding store has too many evidence links."
            )
        status_transitions_value = document["status_transitions"]
        if not isinstance(status_transitions_value, list):
            raise ResearchError("Security finding status transitions must be a list.")
        if len(status_transitions_value) > MAX_SECURITY_FINDING_STATUS_TRANSITIONS:
            raise ResearchError(
                "The security finding store has too many status transitions."
            )
        findings = tuple(self._parse_finding(value) for value in findings_value)
        evidence_links = tuple(
            self._parse_evidence_link(value) for value in evidence_links_value
        )
        status_transitions = tuple(
            self._parse_status_transition(value) for value in status_transitions_value
        )
        return ResearchSecurityFindingDocument(
            findings=findings,
            evidence_links=evidence_links,
            status_transitions=status_transitions,
        )

    @staticmethod
    def _parse_finding(document: object) -> ResearchSecurityFindingRecord:
        if not isinstance(document, dict) or set(document) != _FINDING_FIELDS:
            raise ResearchError("A security finding document is invalid.")
        store = JsonFileResearchSecurityFindingStore
        return ResearchSecurityFindingRecord(
            finding_id=store._text(document["finding_id"]),
            program_id=store._text(document["program_id"]),
            source_hypothesis_id=store._text(document["source_hypothesis_id"]),
            finding_kind=store._finding_kind(document["finding_kind"]),
            subject_kind=store._asset_kind(document["subject_kind"]),
            subject_canonical_value=store._text(document["subject_canonical_value"]),
            title=store._text(document["title"]),
            description=store._text(document["description"]),
            required_followup=store._text(document["required_followup"]),
            origin=store._origin(document["origin"]),
            created_at=store._timestamp(document["created_at"]),
        )

    @staticmethod
    def _parse_evidence_link(
        document: object,
    ) -> ResearchSecurityFindingEvidenceLinkRecord:
        if not isinstance(document, dict) or set(document) != _EVIDENCE_LINK_FIELDS:
            raise ResearchError("A security finding evidence link is invalid.")
        store = JsonFileResearchSecurityFindingStore
        return ResearchSecurityFindingEvidenceLinkRecord(
            link_id=store._text(document["link_id"]),
            finding_id=store._text(document["finding_id"]),
            program_id=store._text(document["program_id"]),
            evidence_kind=store._evidence_kind(document["evidence_kind"]),
            evidence_id=store._text(document["evidence_id"]),
            relation=store._relation(document["relation"]),
            recorded_at=store._timestamp(document["recorded_at"]),
        )

    @staticmethod
    def _parse_status_transition(
        document: object,
    ) -> ResearchSecurityFindingStatusTransitionRecord:
        if not isinstance(document, dict) or set(document) != _STATUS_TRANSITION_FIELDS:
            raise ResearchError(
                "A security finding status transition document is invalid."
            )
        store = JsonFileResearchSecurityFindingStore
        return ResearchSecurityFindingStatusTransitionRecord(
            transition_id=store._text(document["transition_id"]),
            finding_id=store._text(document["finding_id"]),
            program_id=store._text(document["program_id"]),
            status=store._status(document["status"]),
            reason=store._optional_text(document["reason"]),
            duplicate_of_finding_id=store._nullable_text(
                document["duplicate_of_finding_id"]
            ),
            superseded_by_finding_id=store._nullable_text(
                document["superseded_by_finding_id"]
            ),
            recorded_at=store._timestamp(document["recorded_at"]),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A security finding identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A security finding text field is invalid.")
        return value

    @staticmethod
    def _nullable_text(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A security finding linkage reference is invalid.")
        return value

    @staticmethod
    def _asset_kind(value: object) -> ResearchAssetKind:
        if not isinstance(value, str):
            raise ResearchError("A security finding subject kind is invalid.")
        try:
            return ResearchAssetKind(value)
        except ValueError as error:
            raise ResearchError(
                "A security finding subject kind is invalid."
            ) from error

    @staticmethod
    def _finding_kind(value: object) -> ResearchSecurityHypothesisKind:
        if not isinstance(value, str):
            raise ResearchError("A security finding kind is invalid.")
        try:
            return ResearchSecurityHypothesisKind(value)
        except ValueError as error:
            raise ResearchError("A security finding kind is invalid.") from error

    @staticmethod
    def _origin(value: object) -> ResearchSecurityFindingOrigin:
        if not isinstance(value, str):
            raise ResearchError("A security finding origin is invalid.")
        try:
            return ResearchSecurityFindingOrigin(value)
        except ValueError as error:
            raise ResearchError("A security finding origin is invalid.") from error

    @staticmethod
    def _evidence_kind(value: object) -> ResearchSecurityFindingEvidenceKind:
        if not isinstance(value, str):
            raise ResearchError("A security finding evidence kind is invalid.")
        try:
            return ResearchSecurityFindingEvidenceKind(value)
        except ValueError as error:
            raise ResearchError(
                "A security finding evidence kind is invalid."
            ) from error

    @staticmethod
    def _relation(value: object) -> ResearchSecurityFindingEvidenceRelation:
        if not isinstance(value, str):
            raise ResearchError("A security finding evidence relation is invalid.")
        try:
            return ResearchSecurityFindingEvidenceRelation(value)
        except ValueError as error:
            raise ResearchError(
                "A security finding evidence relation is invalid."
            ) from error

    @staticmethod
    def _status(value: object) -> ResearchSecurityFindingStatus:
        if not isinstance(value, str):
            raise ResearchError("A security finding status is invalid.")
        try:
            return ResearchSecurityFindingStatus(value)
        except ValueError as error:
            raise ResearchError("A security finding status is invalid.") from error

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A security finding timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("A security finding timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("A security finding timestamp must be timezone-aware.")
        return parsed
