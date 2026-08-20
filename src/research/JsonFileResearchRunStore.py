"""Atomic JSON persistence for auditable research runs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from core.Exceptions import ResearchError
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class JsonFileResearchRunStore:
    """Load and atomically replace a strict versioned research-run document."""

    _SCHEMA_VERSION = 3
    _SUPPORTED_SCHEMA_VERSIONS = {1, 2, 3}
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
    _SOURCE_FIELDS = {
        "document_id",
        "url",
        "title",
        "content_type",
        "fetched_at",
        "added_at",
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

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchRun]:
        """Return a fully validated snapshot, or an empty one when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open(encoding="utf-8") as file:
                document = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
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
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(document, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
        except (OSError, OverflowError, TypeError, ValueError) as error:
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
        runs = [self._parse_run(value, schema_version) for value in runs_data]
        self._validate_runs(runs)
        return runs

    def _parse_run(self, value: Any, schema_version: int) -> ResearchRun:
        expected_fields = {
            1: self._RUN_FIELDS_V1,
            2: self._RUN_FIELDS_V2,
            3: self._RUN_FIELDS_V3,
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
        if (
            not isinstance(sources_data, list)
            or not isinstance(failures_data, list)
            or not isinstance(evidence_data, list)
            or not isinstance(discoveries_data, list)
        ):
            raise ResearchError("Research run store contains invalid run collections.")
        return ResearchRun(
            run_id=value["run_id"],
            question=value["question"],
            status=status,
            sources=tuple(self._parse_source(item) for item in sources_data),
            failures=tuple(self._parse_failure(item) for item in failures_data),
            created_at=self._parse_datetime(value["created_at"], "created_at"),
            updated_at=self._parse_datetime(value["updated_at"], "updated_at"),
            evidence=tuple(self._parse_evidence(item) for item in evidence_data),
            discoveries=tuple(self._parse_discovery(item) for item in discoveries_data),
        )

    def _parse_source(self, value: Any) -> ResearchSourceRecord:
        if not isinstance(value, dict) or set(value) != self._SOURCE_FIELDS:
            raise ResearchError("Research run store contains an invalid source record.")
        return ResearchSourceRecord(
            document_id=value["document_id"],
            url=value["url"],
            title=value["title"],
            content_type=value["content_type"],
            fetched_at=self._parse_datetime(value["fetched_at"], "fetched_at"),
            added_at=self._parse_datetime(value["added_at"], "added_at"),
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

    def _parse_discovery(self, value: Any) -> ResearchSourceDiscoveryRecord:
        if not isinstance(value, dict) or set(value) != self._DISCOVERY_FIELDS:
            raise ResearchError(
                "Research run store contains an invalid discovery record."
            )
        candidates = value["candidates"]
        if not isinstance(candidates, list):
            raise ResearchError(
                "Research run store discovery candidates must be a list."
            )
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
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        }

    @staticmethod
    def _validate_runs(runs: list[ResearchRun]) -> None:
        if not all(isinstance(run, ResearchRun) for run in runs):
            raise ResearchError("Research run store accepts only ResearchRun records.")
        run_ids = [run.run_id for run in runs]
        if len(run_ids) != len(set(run_ids)):
            raise ResearchError("Research run store contains duplicate run IDs.")

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
