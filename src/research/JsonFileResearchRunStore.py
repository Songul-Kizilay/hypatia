"""Atomic JSON persistence for auditable research runs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import (
    EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY,
    EXTERNAL_SOURCE_TAINT_LABEL,
    ResearchSourceRecord,
)

MAX_RESEARCH_RUN_STORE_BYTES = 64 * 1024 * 1024
MAX_RESEARCH_RUN_STORE_COLLECTION_ITEMS = 20_000


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
        if self._byte_count + encoded_size > MAX_RESEARCH_RUN_STORE_BYTES:
            raise OverflowError("Research run store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Research run store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class _CollectionBudget:
    """Bound aggregate list entries while decoding one validated snapshot."""

    def __init__(self) -> None:
        self._item_count = 0

    def consume(self, values: list[Any]) -> None:
        self.consume_count(len(values))

    def consume_count(self, count: int) -> None:
        if count > MAX_RESEARCH_RUN_STORE_COLLECTION_ITEMS - self._item_count:
            raise ResearchError(
                "Research run store contains too many collection items."
            )
        self._item_count += count


class JsonFileResearchRunStore:
    """Load and atomically replace a strict versioned research-run document."""

    _SCHEMA_VERSION = 7
    _SUPPORTED_SCHEMA_VERSIONS = {1, 2, 3, 4, 5, 6, 7}
    _DOCUMENT_FIELDS = {"schema_version", "runs"}
    _RUN_FIELDS_V1 = {
        "run_id",
        "question",
        "status",
        "sources",
        "failures",
        "created_at",
        "updated_at",
    }
    _RUN_FIELDS_V2 = _RUN_FIELDS_V1 | {"evidence"}
    _RUN_FIELDS_V3 = _RUN_FIELDS_V2 | {"discoveries"}
    _RUN_FIELDS_V4 = _RUN_FIELDS_V3 | {"assessments"}
    _RUN_FIELDS_V5 = _RUN_FIELDS_V4
    _RUN_FIELDS_V6 = _RUN_FIELDS_V5 | {"comparison_notes"}
    _RUN_FIELDS_V7 = _RUN_FIELDS_V6
    _SOURCE_FIELDS_V1_V6 = {
        "document_id",
        "url",
        "title",
        "content_type",
        "fetched_at",
        "added_at",
    }
    _SOURCE_FIELDS_V7 = _SOURCE_FIELDS_V1_V6 | {
        "taint_label",
        "instruction_authority",
    }
    _FAILURE_FIELDS = {"stage", "reason", "occurred_at"}
    _EVIDENCE_FIELDS = {
        "evidence_id",
        "source_document_id",
        "chunk_id",
        "chunk_index",
        "excerpt",
        "excerpt_truncated",
        "chunk_sha256",
        "note",
        "recorded_at",
    }
    _DISCOVERY_FIELDS = {
        "discovery_id",
        "query",
        "provider",
        "candidates",
        "discovered_at",
    }
    _CANDIDATE_FIELDS = {"url", "title", "snippet"}
    _ASSESSMENT_FIELDS_V4 = {
        "assessment_id",
        "source_document_id",
        "evidence_ids",
        "text",
        "recorded_at",
    }
    _ASSESSMENT_FIELDS_V5 = _ASSESSMENT_FIELDS_V4 | {"supersedes_assessment_id"}
    _ASSESSMENT_FIELDS_V7 = _ASSESSMENT_FIELDS_V5 | {"information_trust"}
    _COMPARISON_NOTE_FIELDS = {
        "note_id",
        "source_document_ids",
        "evidence_ids",
        "assessment_ids",
        "text",
        "recorded_at",
    }

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchRun]:
        """Return a fully validated snapshot, or an empty one when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_RESEARCH_RUN_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                f"Unable to read research run store '{self._path}'."
            ) from error
        if len(encoded_document) > MAX_RESEARCH_RUN_STORE_BYTES:
            raise ResearchError(f"Research run store '{self._path}' is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                f"Unable to read research run store '{self._path}'."
            ) from error
        return self._parse_document(document)

    def save(self, runs: list[ResearchRun]) -> None:
        """Atomically replace the complete research-run snapshot."""
        self._validate_runs(runs)
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "runs": [self._serialize_run(run) for run in runs],
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
        except OverflowError as error:
            raise ResearchError(
                f"Research run store '{self._path}' is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                f"Unable to write research run store '{self._path}'."
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _parse_document(self, document: Any) -> list[ResearchRun]:
        if not isinstance(document, dict) or set(document) != self._DOCUMENT_FIELDS:
            raise ResearchError(
                f"Research run store '{self._path}' has invalid fields."
            )
        schema_version = document["schema_version"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version not in self._SUPPORTED_SCHEMA_VERSIONS
        ):
            raise ResearchError(
                f"Research run store '{self._path}' has an unsupported schema version."
            )
        runs_data = document["runs"]
        if not isinstance(runs_data, list):
            raise ResearchError(
                f"Research run store '{self._path}' runs must be a list."
            )
        budget = _CollectionBudget()
        budget.consume(runs_data)
        runs = [self._parse_run(value, schema_version, budget) for value in runs_data]
        self._validate_runs(runs)
        return runs

    def _parse_run(
        self,
        value: Any,
        schema_version: int,
        budget: _CollectionBudget,
    ) -> ResearchRun:
        expected_fields = {
            1: self._RUN_FIELDS_V1,
            2: self._RUN_FIELDS_V2,
            3: self._RUN_FIELDS_V3,
            4: self._RUN_FIELDS_V4,
            5: self._RUN_FIELDS_V5,
            6: self._RUN_FIELDS_V6,
            7: self._RUN_FIELDS_V7,
        }[schema_version]
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ResearchError("Research run store contains an invalid run record.")
        try:
            status = ResearchRunStatus(value["status"])
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains an invalid status."
            ) from error
        sources_data = value["sources"]
        failures_data = value["failures"]
        evidence_data = [] if schema_version == 1 else value["evidence"]
        discoveries_data = [] if schema_version < 3 else value["discoveries"]
        assessments_data = [] if schema_version < 4 else value["assessments"]
        comparison_notes_data = [] if schema_version < 6 else value["comparison_notes"]
        if (
            not isinstance(sources_data, list)
            or not isinstance(failures_data, list)
            or not isinstance(evidence_data, list)
            or not isinstance(discoveries_data, list)
            or not isinstance(assessments_data, list)
            or not isinstance(comparison_notes_data, list)
        ):
            raise ResearchError("Research run store contains invalid run collections.")
        for values in (
            sources_data,
            failures_data,
            evidence_data,
            discoveries_data,
            assessments_data,
            comparison_notes_data,
        ):
            budget.consume(values)
        return ResearchRun(
            run_id=value["run_id"],
            question=value["question"],
            status=status,
            sources=tuple(
                self._parse_source(item, schema_version) for item in sources_data
            ),
            failures=tuple(self._parse_failure(item) for item in failures_data),
            created_at=self._parse_datetime(value["created_at"], "created_at"),
            updated_at=self._parse_datetime(value["updated_at"], "updated_at"),
            evidence=tuple(self._parse_evidence(item) for item in evidence_data),
            discoveries=tuple(
                self._parse_discovery(item, budget) for item in discoveries_data
            ),
            assessments=tuple(
                self._parse_assessment(item, schema_version, budget)
                for item in assessments_data
            ),
            comparison_notes=tuple(
                self._parse_comparison_note(item, budget)
                for item in comparison_notes_data
            ),
        )

    def _parse_source(
        self,
        value: Any,
        schema_version: int,
    ) -> ResearchSourceRecord:
        expected_fields = (
            self._SOURCE_FIELDS_V7 if schema_version >= 7 else self._SOURCE_FIELDS_V1_V6
        )
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ResearchError("Research run store contains an invalid source record.")
        return ResearchSourceRecord(
            document_id=value["document_id"],
            url=value["url"],
            title=value["title"],
            content_type=value["content_type"],
            fetched_at=self._parse_datetime(value["fetched_at"], "fetched_at"),
            added_at=self._parse_datetime(value["added_at"], "added_at"),
            taint_label=(
                value["taint_label"]
                if schema_version >= 7
                else EXTERNAL_SOURCE_TAINT_LABEL
            ),
            instruction_authority=(
                value["instruction_authority"]
                if schema_version >= 7
                else EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY
            ),
        )

    def _parse_failure(self, value: Any) -> ResearchFailureRecord:
        if not isinstance(value, dict) or set(value) != self._FAILURE_FIELDS:
            raise ResearchError(
                "Research run store contains an invalid failure record."
            )
        return ResearchFailureRecord(
            stage=value["stage"],
            reason=value["reason"],
            occurred_at=self._parse_datetime(value["occurred_at"], "occurred_at"),
        )

    def _parse_evidence(self, value: Any) -> ResearchEvidenceRecord:
        if not isinstance(value, dict) or set(value) != self._EVIDENCE_FIELDS:
            raise ResearchError(
                "Research run store contains an invalid evidence record."
            )
        return ResearchEvidenceRecord(
            evidence_id=value["evidence_id"],
            source_document_id=value["source_document_id"],
            chunk_id=value["chunk_id"],
            chunk_index=value["chunk_index"],
            excerpt=value["excerpt"],
            excerpt_truncated=value["excerpt_truncated"],
            chunk_sha256=value["chunk_sha256"],
            note=value["note"],
            recorded_at=self._parse_datetime(value["recorded_at"], "recorded_at"),
        )

    def _parse_discovery(
        self,
        value: Any,
        budget: _CollectionBudget,
    ) -> ResearchSourceDiscoveryRecord:
        if not isinstance(value, dict) or set(value) != self._DISCOVERY_FIELDS:
            raise ResearchError(
                "Research run store contains an invalid discovery record."
            )
        candidates = value["candidates"]
        if not isinstance(candidates, list):
            raise ResearchError(
                "Research run store discovery candidates must be a list."
            )
        budget.consume(candidates)
        return ResearchSourceDiscoveryRecord(
            discovery_id=value["discovery_id"],
            query=value["query"],
            provider=value["provider"],
            candidates=tuple(self._parse_candidate(item) for item in candidates),
            discovered_at=self._parse_datetime(
                value["discovered_at"],
                "discovered_at",
            ),
        )

    @staticmethod
    def _parse_candidate(value: Any) -> ResearchSourceCandidate:
        if (
            not isinstance(value, dict)
            or set(value) != JsonFileResearchRunStore._CANDIDATE_FIELDS
        ):
            raise ResearchError(
                "Research run store contains an invalid source candidate."
            )
        return ResearchSourceCandidate(
            url=value["url"],
            title=value["title"],
            snippet=value["snippet"],
        )

    def _parse_assessment(
        self,
        value: Any,
        schema_version: int,
        budget: _CollectionBudget,
    ) -> ResearchSourceAssessmentRecord:
        if schema_version == 4:
            expected_fields = self._ASSESSMENT_FIELDS_V4
        elif schema_version < 7:
            expected_fields = self._ASSESSMENT_FIELDS_V5
        else:
            expected_fields = self._ASSESSMENT_FIELDS_V7
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ResearchError(
                "Research run store contains an invalid assessment record."
            )
        evidence_ids = value["evidence_ids"]
        if not isinstance(evidence_ids, list):
            raise ResearchError(
                "Research run store assessment evidence IDs must be a list."
            )
        budget.consume(evidence_ids)
        return ResearchSourceAssessmentRecord(
            assessment_id=value["assessment_id"],
            source_document_id=value["source_document_id"],
            evidence_ids=tuple(evidence_ids),
            text=value["text"],
            recorded_at=self._parse_datetime(value["recorded_at"], "recorded_at"),
            supersedes_assessment_id=(
                None if schema_version == 4 else value["supersedes_assessment_id"]
            ),
            information_trust=(
                ResearchInformationTrust.UNASSESSED
                if schema_version < 7
                else self._parse_information_trust(value["information_trust"])
            ),
        )

    @staticmethod
    def _parse_information_trust(value: Any) -> ResearchInformationTrust:
        try:
            return ResearchInformationTrust(value)
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains invalid source information trust."
            ) from error

    def _parse_comparison_note(
        self,
        value: Any,
        budget: _CollectionBudget,
    ) -> ResearchSourceComparisonNoteRecord:
        if not isinstance(value, dict) or set(value) != self._COMPARISON_NOTE_FIELDS:
            raise ResearchError(
                "Research run store contains an invalid comparison note."
            )
        source_document_ids = value["source_document_ids"]
        evidence_ids = value["evidence_ids"]
        assessment_ids = value["assessment_ids"]
        if not all(
            isinstance(values, list)
            for values in (source_document_ids, evidence_ids, assessment_ids)
        ):
            raise ResearchError(
                "Research run store comparison note references must be lists."
            )
        for values in (source_document_ids, evidence_ids, assessment_ids):
            budget.consume(values)
        return ResearchSourceComparisonNoteRecord(
            note_id=value["note_id"],
            source_document_ids=tuple(source_document_ids),
            evidence_ids=tuple(evidence_ids),
            assessment_ids=tuple(assessment_ids),
            text=value["text"],
            recorded_at=self._parse_datetime(value["recorded_at"], "recorded_at"),
        )

    def _parse_datetime(self, value: Any, field_name: str) -> datetime:
        if not isinstance(value, str):
            raise ResearchError(
                f"Research run store {field_name} must be ISO-8601 text."
            )
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError(
                f"Research run store has invalid {field_name}."
            ) from error
        if parsed.utcoffset() is None:
            raise ResearchError(
                f"Research run store {field_name} must be timezone-aware."
            )
        return parsed

    @staticmethod
    def _serialize_run(run: ResearchRun) -> dict[str, object]:
        return {
            "run_id": run.run_id,
            "question": run.question,
            "status": run.status.value,
            "sources": [
                {
                    "document_id": source.document_id,
                    "url": source.url,
                    "title": source.title,
                    "content_type": source.content_type,
                    "fetched_at": source.fetched_at.isoformat(),
                    "added_at": source.added_at.isoformat(),
                    "taint_label": source.taint_label,
                    "instruction_authority": source.instruction_authority,
                }
                for source in run.sources
            ],
            "failures": [
                {
                    "stage": failure.stage,
                    "reason": failure.reason,
                    "occurred_at": failure.occurred_at.isoformat(),
                }
                for failure in run.failures
            ],
            "evidence": [
                {
                    "evidence_id": evidence.evidence_id,
                    "source_document_id": evidence.source_document_id,
                    "chunk_id": evidence.chunk_id,
                    "chunk_index": evidence.chunk_index,
                    "excerpt": evidence.excerpt,
                    "excerpt_truncated": evidence.excerpt_truncated,
                    "chunk_sha256": evidence.chunk_sha256,
                    "note": evidence.note,
                    "recorded_at": evidence.recorded_at.isoformat(),
                }
                for evidence in run.evidence
            ],
            "discoveries": [
                {
                    "discovery_id": discovery.discovery_id,
                    "query": discovery.query,
                    "provider": discovery.provider,
                    "candidates": [
                        {
                            "url": candidate.url,
                            "title": candidate.title,
                            "snippet": candidate.snippet,
                        }
                        for candidate in discovery.candidates
                    ],
                    "discovered_at": discovery.discovered_at.isoformat(),
                }
                for discovery in run.discoveries
            ],
            "assessments": [
                {
                    "assessment_id": assessment.assessment_id,
                    "source_document_id": assessment.source_document_id,
                    "evidence_ids": list(assessment.evidence_ids),
                    "text": assessment.text,
                    "recorded_at": assessment.recorded_at.isoformat(),
                    "supersedes_assessment_id": (assessment.supersedes_assessment_id),
                    "information_trust": assessment.information_trust.value,
                }
                for assessment in run.assessments
            ],
            "comparison_notes": [
                {
                    "note_id": note.note_id,
                    "source_document_ids": list(note.source_document_ids),
                    "evidence_ids": list(note.evidence_ids),
                    "assessment_ids": list(note.assessment_ids),
                    "text": note.text,
                    "recorded_at": note.recorded_at.isoformat(),
                }
                for note in run.comparison_notes
            ],
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        }

    @staticmethod
    def _validate_runs(runs: list[ResearchRun]) -> None:
        if not isinstance(runs, list):
            raise ResearchError("Research run store accepts a list of runs.")
        budget = _CollectionBudget()
        budget.consume_count(len(runs))
        if not all(isinstance(run, ResearchRun) for run in runs):
            raise ResearchError("Research run store accepts only ResearchRun records.")
        for run in runs:
            for values in (
                run.sources,
                run.failures,
                run.evidence,
                run.discoveries,
                run.assessments,
                run.comparison_notes,
            ):
                budget.consume_count(len(values))
            for discovery in run.discoveries:
                budget.consume_count(len(discovery.candidates))
            for assessment in run.assessments:
                budget.consume_count(len(assessment.evidence_ids))
            for note in run.comparison_notes:
                budget.consume_count(len(note.source_document_ids))
                budget.consume_count(len(note.evidence_ids))
                budget.consume_count(len(note.assessment_ids))
        run_ids = [run.run_id for run in runs]
        if len(run_ids) != len(set(run_ids)):
            raise ResearchError("Research run store contains duplicate run IDs.")
        assessment_ids = [
            assessment.assessment_id for run in runs for assessment in run.assessments
        ]
        if len(assessment_ids) != len(set(assessment_ids)):
            raise ResearchError("Research run store contains duplicate assessment IDs.")
        note_ids = [note.note_id for run in runs for note in run.comparison_notes]
        if len(note_ids) != len(set(note_ids)):
            raise ResearchError(
                "Research run store contains duplicate comparison note IDs."
            )

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
