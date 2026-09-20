"""Atomic versioned persistence for research reflection reports.

A fifth separate store, following the curiosity store pattern exactly. Runs,
executions, background tasks, and curiosity questions are untouched, so no
migration runs and deleting this file simply means no reflection history.

Reports keep only process observations: bounded finding kinds, the identifier of
whatever the finding is about, the templated detail text, and canonical counts.
No source body, no evidence excerpt, and no exception message is written here.

Nothing in this file can produce a reflection about a reflection. It stores
reports; it does not expose them as anything a generator would accept.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.ReflectionFindingKind import ReflectionFindingKind
from research.ResearchReflectionFinding import ResearchReflectionFinding
from research.ResearchReflectionReport import ResearchReflectionReport

MAX_REFLECTION_STORE_BYTES = 4 * 1024 * 1024
MAX_REFLECTION_STORE_REPORTS = 200

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "reports"})
_REPORT_FIELDS = frozenset(
    {
        "report_id",
        "run_id",
        "question",
        "findings",
        "summary",
        "reflected_at",
    }
)
_FINDING_FIELDS = frozenset({"kind", "subject_id", "detail"})
_SUMMARY_FIELDS = frozenset(
    {
        "run_count",
        "discovery_count",
        "source_count",
        "evidence_count",
        "assessment_count",
        "claim_count",
        "contradiction_count",
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
        if self._byte_count + encoded_size > MAX_REFLECTION_STORE_BYTES:
            raise OverflowError("Reflection report store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Reflection report store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileReflectionReportStore:
    """Load and atomically replace a strict versioned reflection document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchReflectionReport]:
        """Return validated reports, or an empty list when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_REFLECTION_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the reflection store.") from error
        if len(encoded_document) > MAX_REFLECTION_STORE_BYTES:
            raise ResearchError("The reflection store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the reflection store.") from error
        return self._parse_document(document)

    def save(self, reports: list[ResearchReflectionReport]) -> None:
        """Atomically replace the complete reflection document."""
        self._validate_reports(reports)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "reports": [self._serialize(report) for report in reports],
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
            raise ResearchError("The reflection store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the reflection store.") from error
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
    def _serialize(report: ResearchReflectionReport) -> dict[str, Any]:
        return {
            "report_id": report.report_id,
            "run_id": report.run_id,
            "question": report.question,
            "findings": [
                {
                    "kind": finding.kind.value,
                    "subject_id": finding.subject_id,
                    "detail": finding.detail,
                }
                for finding in report.findings
            ],
            "summary": {
                "run_count": report.summary.run_count,
                "discovery_count": report.summary.discovery_count,
                "source_count": report.summary.source_count,
                "evidence_count": report.summary.evidence_count,
                "assessment_count": report.summary.assessment_count,
                "claim_count": report.summary.claim_count,
                "contradiction_count": report.summary.contradiction_count,
            },
            "reflected_at": report.reflected_at.isoformat(),
        }

    def _parse_document(self, document: object) -> list[ResearchReflectionReport]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The reflection document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError("The reflection store schema version is not supported.")
        reports_value = document["reports"]
        if not isinstance(reports_value, list):
            raise ResearchError("Reflection store reports must be a list.")
        if len(reports_value) > MAX_REFLECTION_STORE_REPORTS:
            raise ResearchError("The reflection store has too many reports.")
        reports = [self._parse_report(value) for value in reports_value]
        self._validate_reports(reports)
        return reports

    @staticmethod
    def _parse_report(document: object) -> ResearchReflectionReport:
        if not isinstance(document, dict) or set(document) != _REPORT_FIELDS:
            raise ResearchError("A reflection report document is invalid.")
        store = JsonFileReflectionReportStore
        findings_value = document["findings"]
        if not isinstance(findings_value, list):
            raise ResearchError("Reflection report findings must be a list.")
        summary_value = document["summary"]
        if not isinstance(summary_value, dict) or set(summary_value) != _SUMMARY_FIELDS:
            raise ResearchError("A reflection summary document is invalid.")
        return ResearchReflectionReport(
            report_id=store._text(document["report_id"]),
            run_id=store._text(document["run_id"]),
            question=store._text(document["question"]),
            findings=tuple(store._parse_finding(value) for value in findings_value),
            summary=CanonicalResearchSummary(**summary_value),
            reflected_at=store._timestamp(document["reflected_at"]),
        )

    @staticmethod
    def _parse_finding(document: object) -> ResearchReflectionFinding:
        if not isinstance(document, dict) or set(document) != _FINDING_FIELDS:
            raise ResearchError("A reflection finding document is invalid.")
        kind = document["kind"]
        if not isinstance(kind, str):
            raise ResearchError("A reflection finding kind is invalid.")
        try:
            parsed_kind = ReflectionFindingKind(kind)
        except ValueError as error:
            raise ResearchError("A reflection finding kind is invalid.") from error
        store = JsonFileReflectionReportStore
        return ResearchReflectionFinding(
            kind=parsed_kind,
            subject_id=store._optional_text(document["subject_id"]),
            detail=store._optional_text(document["detail"]),
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("A reflection identifier cannot be empty.")
        return value

    @staticmethod
    def _optional_text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("A reflection text field is invalid.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A reflection timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("A reflection timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("A reflection timestamp must be timezone-aware.")
        return parsed

    def _validate_reports(self, reports: list[ResearchReflectionReport]) -> None:
        if not isinstance(reports, list):
            raise ResearchError("The reflection store accepts a list.")
        if len(reports) > MAX_REFLECTION_STORE_REPORTS:
            raise ResearchError("The reflection store has too many reports.")
        if not all(isinstance(report, ResearchReflectionReport) for report in reports):
            raise ResearchError("The reflection store accepts only reports.")
        report_ids = [report.report_id for report in reports]
        if len(report_ids) != len(set(report_ids)):
            raise ResearchError("The reflection store has duplicate report IDs.")
