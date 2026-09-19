"""Atomic JSON persistence for auditable research runs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision,
    ResearchComparisonReviewRecord,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceRecord import (
    EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY,
    EXTERNAL_SOURCE_TAINT_LABEL,
    ResearchSourceRecord,
)
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome
from research.ResearchSourceRevalidationRecord import ResearchSourceRevalidationRecord
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.ResearchVulnerabilityMetric import ResearchVulnerabilityMetric
from research.ResearchVulnerabilityRecord import ResearchVulnerabilityRecord
from research.ResearchVulnerabilityReference import ResearchVulnerabilityReference

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

    _SCHEMA_VERSION = 19
    _SUPPORTED_SCHEMA_VERSIONS = set(range(1, _SCHEMA_VERSION + 1))
    _DOCUMENT_FIELDS_V1_V18 = {"schema_version", "runs"}
    _DOCUMENT_FIELDS_V19 = _DOCUMENT_FIELDS_V1_V18 | {"source_revalidations"}
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
    _RUN_FIELDS_V8 = _RUN_FIELDS_V7 | {"claims"}
    _RUN_FIELDS_V9 = _RUN_FIELDS_V8 | {"claim_contradictions"}
    #: Version 14 adds explicit operator comparison reviews. A run written
    #: before it decodes with none, which is what it holds: no review was
    #: recorded, so no retained comparison is treated as supported.
    _RUN_FIELDS_V14 = _RUN_FIELDS_V9 | {"comparison_reviews"}
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
    #: Version 15 records the content version each run observed.  Sources
    #: written before it decode with none: their content version is unrecorded,
    #: never inferred from the URL or from content stored by another run.
    _SOURCE_FIELDS_V15 = _SOURCE_FIELDS_V7 | {"content_sha256"}
    #: Version 16 records the URL each run requested, beside the final URL.
    #: Earlier sources decode with none: unrecorded, never copied from ``url``.
    _SOURCE_FIELDS_V16 = _SOURCE_FIELDS_V15 | {"requested_url"}
    #: Version 17 records discovery-candidate identity: candidate IDs on each
    #: discovery and the selected candidate on each source.  Earlier records
    #: decode with none; nothing is backfilled from URLs or ordering.
    _SOURCE_FIELDS_V17 = _SOURCE_FIELDS_V16 | {"discovery_candidate_id"}
    #: Version 18 records the immutable identity of each source acceptance.
    #: Earlier records retain ``None`` because historical observation identity
    #: was never captured and must not be fabricated during loading.
    _SOURCE_FIELDS_V18 = _SOURCE_FIELDS_V17 | {"observation_id"}
    _FAILURE_FIELDS_V1_V12 = {"stage", "reason", "occurred_at"}
    _FAILURE_FIELDS_V13 = _FAILURE_FIELDS_V1_V12 | {"provider"}
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
    _CANDIDATE_FIELDS_V1 = {"url", "title", "snippet"}
    #: Version 10 keeps the venue and year the provider already received. A
    #: version 9 record decodes without them, which is what it truthfully has:
    #: they were discarded before it was written, and inventing a year for an
    #: old record is exactly the failure this field exists to prevent.
    _CANDIDATE_FIELDS_V10 = _CANDIDATE_FIELDS_V1 | {"container", "published_year"}
    #: Version 12 carries the structured vulnerability record a security
    #: provider returns. A scholarly candidate stores `null` there and a record
    #: written before version 12 decodes with none, which is what it has: no
    #: provider had ever returned one.
    _CANDIDATE_FIELDS_V12 = _CANDIDATE_FIELDS_V10 | {"vulnerability"}
    _VULNERABILITY_FIELDS = {
        "cve_id",
        "status",
        "source_identifier",
        "last_modified",
        "weaknesses",
        "metrics",
        "references",
        "reference_total",
        "known_exploited_at",
        "known_exploited_name",
    }
    _VULNERABILITY_METRIC_FIELDS = {"version", "source", "score", "severity"}
    _VULNERABILITY_REFERENCE_FIELDS = {"url", "source", "tags"}
    _ASSESSMENT_FIELDS_V4 = {
        "assessment_id",
        "source_document_id",
        "evidence_ids",
        "text",
        "recorded_at",
    }
    _ASSESSMENT_FIELDS_V5 = _ASSESSMENT_FIELDS_V4 | {"supersedes_assessment_id"}
    _ASSESSMENT_FIELDS_V7 = _ASSESSMENT_FIELDS_V5 | {"information_trust"}
    #: Version 11 records what the operator concluded about the source itself.
    #: Anything written before it decodes as `unknown` on all four, which is
    #: what those records truthfully hold: nobody was ever asked.
    _ASSESSMENT_FIELDS_V11 = _ASSESSMENT_FIELDS_V7 | {
        "usefulness",
        "applicability",
        "independence",
        "publication_status",
    }
    _CLAIM_FIELDS = {
        "claim_id",
        "text",
        "epistemic_state",
        "confidence",
        "source_document_ids",
        "evidence_ids",
        "recorded_at",
        "supersedes_claim_id",
    }
    _CLAIM_CONTRADICTION_FIELDS = {
        "contradiction_id",
        "claim_ids",
        "evidence_ids",
        "note",
        "recorded_at",
    }
    _COMPARISON_REVIEW_FIELDS = {
        "review_id",
        "note_id",
        "evidence_ids",
        "decision",
        "note",
        "recorded_at",
        "supersedes_review_id",
    }
    _COMPARISON_NOTE_FIELDS = {
        "note_id",
        "source_document_ids",
        "evidence_ids",
        "assessment_ids",
        "text",
        "recorded_at",
    }
    _SOURCE_REVALIDATION_FIELDS = {
        "revalidation_id",
        "earlier_run_id",
        "earlier_observation_id",
        "later_run_id",
        "later_observation_id",
        "outcome",
        "recorded_at",
    }

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchRun]:
        """Return a fully validated snapshot, or an empty one when absent."""
        return self._load_snapshot()[0]

    def load_source_revalidations(self) -> list[ResearchSourceRevalidationRecord]:
        """Return recorded cross-run observation relations without mutation."""
        return self._load_snapshot()[1]

    def save(self, runs: list[ResearchRun]) -> None:
        """Atomically replace the complete research-run snapshot."""
        self.save_with_source_revalidations(runs, [])

    def save_with_source_revalidations(
        self,
        runs: list[ResearchRun],
        source_revalidations: list[ResearchSourceRevalidationRecord],
    ) -> None:
        """Atomically replace run and cross-run temporal provenance together."""
        self._validate_runs(runs)
        self._validate_source_revalidations(source_revalidations)
        self._validate_source_revalidation_bindings(source_revalidations, runs)
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "runs": [self._serialize_run(run) for run in runs],
            "source_revalidations": [
                self._serialize_source_revalidation(record)
                for record in source_revalidations
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

    def _load_snapshot(
        self,
    ) -> tuple[list[ResearchRun], list[ResearchSourceRevalidationRecord]]:
        if not self._path.exists():
            return [], []
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
        return self._parse_snapshot(document)

    def _parse_snapshot(
        self, document: Any
    ) -> tuple[list[ResearchRun], list[ResearchSourceRevalidationRecord]]:
        if not isinstance(document, dict) or not isinstance(
            document.get("schema_version"), int
        ):
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
        expected_fields = (
            self._DOCUMENT_FIELDS_V19
            if schema_version >= 19
            else self._DOCUMENT_FIELDS_V1_V18
        )
        if set(document) != expected_fields:
            raise ResearchError(
                f"Research run store '{self._path}' has invalid fields."
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
        revalidations_data = document.get("source_revalidations", [])
        if not isinstance(revalidations_data, list):
            raise ResearchError(
                f"Research run store '{self._path}' source revalidations "
                "must be a list."
            )
        budget.consume(revalidations_data)
        revalidations = [
            self._parse_source_revalidation(value) for value in revalidations_data
        ]
        self._validate_source_revalidations(revalidations)
        self._validate_source_revalidation_bindings(revalidations, runs)
        return runs, revalidations

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
            8: self._RUN_FIELDS_V8,
            9: self._RUN_FIELDS_V9,
            # Version 10 changed the shape of a candidate, not the shape of a
            # run, so a version 10 run record is a version 9 run record. Version
            # 11 changed the shape of an assessment, for the same reason.
            10: self._RUN_FIELDS_V9,
            11: self._RUN_FIELDS_V9,
            # Version 12 changed the shape of a candidate again, not the run.
            12: self._RUN_FIELDS_V9,
            # Version 13 added optional provider provenance to failures.
            13: self._RUN_FIELDS_V9,
            14: self._RUN_FIELDS_V14,
            # Version 15 changed the shape of a source, not the run.
            15: self._RUN_FIELDS_V14,
            # Version 16 changed the shape of a source, not the run.
            16: self._RUN_FIELDS_V14,
            # Version 17 changed discoveries and sources, not the run.
            17: self._RUN_FIELDS_V14,
            # Version 18 changed the shape of a source, not the run.
            18: self._RUN_FIELDS_V14,
            # Version 19 adds document-level source revalidations, not run fields.
            19: self._RUN_FIELDS_V14,
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
        claims_data = [] if schema_version < 8 else value["claims"]
        claim_contradictions_data = (
            [] if schema_version < 9 else value["claim_contradictions"]
        )
        comparison_reviews_data = (
            [] if schema_version < 14 else value["comparison_reviews"]
        )
        if (
            not isinstance(sources_data, list)
            or not isinstance(failures_data, list)
            or not isinstance(evidence_data, list)
            or not isinstance(discoveries_data, list)
            or not isinstance(assessments_data, list)
            or not isinstance(comparison_notes_data, list)
            or not isinstance(claims_data, list)
            or not isinstance(claim_contradictions_data, list)
            or not isinstance(comparison_reviews_data, list)
        ):
            raise ResearchError("Research run store contains invalid run collections.")
        for values in (
            sources_data,
            failures_data,
            evidence_data,
            discoveries_data,
            assessments_data,
            comparison_notes_data,
            claims_data,
            claim_contradictions_data,
            comparison_reviews_data,
        ):
            budget.consume(values)
        return ResearchRun(
            run_id=value["run_id"],
            question=value["question"],
            status=status,
            sources=tuple(
                self._parse_source(item, schema_version) for item in sources_data
            ),
            failures=tuple(
                self._parse_failure(item, schema_version) for item in failures_data
            ),
            created_at=self._parse_datetime(value["created_at"], "created_at"),
            updated_at=self._parse_datetime(value["updated_at"], "updated_at"),
            evidence=tuple(self._parse_evidence(item) for item in evidence_data),
            discoveries=tuple(
                self._parse_discovery(item, budget, schema_version)
                for item in discoveries_data
            ),
            assessments=tuple(
                self._parse_assessment(item, schema_version, budget)
                for item in assessments_data
            ),
            comparison_notes=tuple(
                self._parse_comparison_note(item, budget)
                for item in comparison_notes_data
            ),
            claims=tuple(self._parse_claim(item, budget) for item in claims_data),
            claim_contradictions=tuple(
                self._parse_claim_contradiction(item, budget)
                for item in claim_contradictions_data
            ),
            comparison_reviews=tuple(
                self._parse_comparison_review(item, budget)
                for item in comparison_reviews_data
            ),
        )

    def _parse_source(
        self,
        value: Any,
        schema_version: int,
    ) -> ResearchSourceRecord:
        expected_fields = (
            self._SOURCE_FIELDS_V18
            if schema_version >= 18
            else (
                self._SOURCE_FIELDS_V17
                if schema_version >= 17
                else (
                    self._SOURCE_FIELDS_V16
                    if schema_version >= 16
                    else (
                        self._SOURCE_FIELDS_V15
                        if schema_version >= 15
                        else (
                            self._SOURCE_FIELDS_V7
                            if schema_version >= 7
                            else self._SOURCE_FIELDS_V1_V6
                        )
                    )
                )
            )
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
            content_sha256=value["content_sha256"] if schema_version >= 15 else None,
            requested_url=value["requested_url"] if schema_version >= 16 else None,
            discovery_candidate_id=(
                value["discovery_candidate_id"] if schema_version >= 17 else None
            ),
            observation_id=value["observation_id"] if schema_version >= 18 else None,
        )

    def _parse_failure(self, value: Any, schema_version: int) -> ResearchFailureRecord:
        expected_fields = (
            self._FAILURE_FIELDS_V13
            if schema_version >= 13
            else self._FAILURE_FIELDS_V1_V12
        )
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ResearchError(
                "Research run store contains an invalid failure record."
            )
        return ResearchFailureRecord(
            stage=value["stage"],
            reason=value["reason"],
            occurred_at=self._parse_datetime(value["occurred_at"], "occurred_at"),
            provider=value["provider"] if schema_version >= 13 else None,
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
        schema_version: int,
    ) -> ResearchSourceDiscoveryRecord:
        expected_fields = (
            self._DISCOVERY_FIELDS | {"candidate_ids"}
            if schema_version >= 17
            else self._DISCOVERY_FIELDS
        )
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ResearchError(
                "Research run store contains an invalid discovery record."
            )
        candidates = value["candidates"]
        if not isinstance(candidates, list):
            raise ResearchError(
                "Research run store discovery candidates must be a list."
            )
        budget.consume(candidates)
        candidate_ids = value.get("candidate_ids", [])
        if not isinstance(candidate_ids, list):
            raise ResearchError(
                "Research run store discovery candidate IDs must be a list."
            )
        return ResearchSourceDiscoveryRecord(
            candidate_ids=tuple(candidate_ids),
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
        if not isinstance(value, dict) or set(value) not in (
            JsonFileResearchRunStore._CANDIDATE_FIELDS_V1,
            JsonFileResearchRunStore._CANDIDATE_FIELDS_V10,
            JsonFileResearchRunStore._CANDIDATE_FIELDS_V12,
        ):
            raise ResearchError(
                "Research run store contains an invalid source candidate."
            )
        year = value.get("published_year")
        if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
            raise ResearchError(
                "Research run store contains an invalid source candidate."
            )
        container = value.get("container", "")
        if not isinstance(container, str):
            raise ResearchError(
                "Research run store contains an invalid source candidate."
            )
        return ResearchSourceCandidate(
            url=value["url"],
            title=value["title"],
            snippet=value["snippet"],
            container=container,
            published_year=year,
            vulnerability=_parse_vulnerability(value.get("vulnerability")),
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
        elif schema_version < 11:
            expected_fields = self._ASSESSMENT_FIELDS_V7
        else:
            expected_fields = self._ASSESSMENT_FIELDS_V11
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
            usefulness=self._parse_judgement(
                value, schema_version, "usefulness", ResearchSourceUsefulness
            ),
            applicability=self._parse_judgement(
                value, schema_version, "applicability", ResearchSourceApplicability
            ),
            independence=self._parse_judgement(
                value, schema_version, "independence", ResearchSourceIndependence
            ),
            publication_status=self._parse_judgement(
                value,
                schema_version,
                "publication_status",
                ResearchSourcePublicationStatus,
            ),
        )

    @staticmethod
    def _parse_judgement(
        value: dict[str, Any],
        schema_version: int,
        field: str,
        vocabulary: type[Any],
    ) -> Any:
        """Return one structured judgement, or `unknown` for a record without one.

        An unrecognised stored value fails the load rather than degrading to
        `unknown`. A judgement this build cannot read is a judgement somebody
        made, and quietly showing it as never made would be worse than refusing
        to open the file.
        """
        if schema_version < 11:
            return vocabulary("unknown")
        try:
            return vocabulary(value[field])
        except (KeyError, TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains an invalid source judgement."
            ) from error

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

    def _parse_claim(
        self,
        value: Any,
        budget: _CollectionBudget,
    ) -> ResearchClaimRecord:
        if not isinstance(value, dict) or set(value) != self._CLAIM_FIELDS:
            raise ResearchError("Research run store contains an invalid claim record.")
        source_document_ids = value["source_document_ids"]
        evidence_ids = value["evidence_ids"]
        if not isinstance(source_document_ids, list) or not isinstance(
            evidence_ids,
            list,
        ):
            raise ResearchError("Research run store claim references must be lists.")
        budget.consume(source_document_ids)
        budget.consume(evidence_ids)
        return ResearchClaimRecord(
            claim_id=value["claim_id"],
            text=value["text"],
            epistemic_state=self._parse_epistemic_state(value["epistemic_state"]),
            confidence=self._parse_claim_confidence(value["confidence"]),
            source_document_ids=tuple(source_document_ids),
            evidence_ids=tuple(evidence_ids),
            recorded_at=self._parse_datetime(value["recorded_at"], "recorded_at"),
            supersedes_claim_id=value["supersedes_claim_id"],
        )

    def _parse_claim_contradiction(
        self,
        value: Any,
        budget: _CollectionBudget,
    ) -> ResearchClaimContradictionRecord:
        if (
            not isinstance(value, dict)
            or set(value) != self._CLAIM_CONTRADICTION_FIELDS
        ):
            raise ResearchError(
                "Research run store contains an invalid claim contradiction record."
            )
        claim_ids = value["claim_ids"]
        evidence_ids = value["evidence_ids"]
        if not isinstance(claim_ids, list) or not isinstance(evidence_ids, list):
            raise ResearchError(
                "Research run store claim contradiction references must be lists."
            )
        budget.consume(claim_ids)
        budget.consume(evidence_ids)
        return ResearchClaimContradictionRecord(
            contradiction_id=value["contradiction_id"],
            claim_ids=tuple(claim_ids),
            evidence_ids=tuple(evidence_ids),
            note=value["note"],
            recorded_at=self._parse_datetime(value["recorded_at"], "recorded_at"),
        )

    def _parse_comparison_review(
        self,
        value: Any,
        budget: _CollectionBudget,
    ) -> ResearchComparisonReviewRecord:
        if not isinstance(value, dict) or set(value) != self._COMPARISON_REVIEW_FIELDS:
            raise ResearchError(
                "Research run store contains an invalid comparison review record."
            )
        evidence_ids = value["evidence_ids"]
        if not isinstance(evidence_ids, list):
            raise ResearchError(
                "Research run store comparison review evidence must be a list."
            )
        budget.consume(evidence_ids)
        try:
            decision = ResearchComparisonReviewDecision(value["decision"])
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains an invalid comparison review decision."
            ) from error
        return ResearchComparisonReviewRecord(
            review_id=value["review_id"],
            note_id=value["note_id"],
            evidence_ids=tuple(evidence_ids),
            decision=decision,
            note=value["note"],
            recorded_at=self._parse_datetime(value["recorded_at"], "recorded_at"),
            supersedes_review_id=value["supersedes_review_id"],
        )

    @staticmethod
    def _parse_epistemic_state(value: Any) -> ResearchEpistemicState:
        try:
            return ResearchEpistemicState(value)
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains an invalid epistemic state."
            ) from error

    @staticmethod
    def _parse_claim_confidence(value: Any) -> ResearchClaimConfidence:
        try:
            return ResearchClaimConfidence(value)
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains invalid claim confidence."
            ) from error

    def _parse_source_revalidation(
        self, value: Any
    ) -> ResearchSourceRevalidationRecord:
        if (
            not isinstance(value, dict)
            or set(value) != self._SOURCE_REVALIDATION_FIELDS
        ):
            raise ResearchError(
                "Research run store contains an invalid source revalidation record."
            )
        try:
            outcome = ResearchSourceRevalidationOutcome(value["outcome"])
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research run store contains an invalid source revalidation outcome."
            ) from error
        return ResearchSourceRevalidationRecord(
            revalidation_id=value["revalidation_id"],
            earlier_run_id=value["earlier_run_id"],
            earlier_observation_id=value["earlier_observation_id"],
            later_run_id=value["later_run_id"],
            later_observation_id=value["later_observation_id"],
            outcome=outcome,
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

    @classmethod
    def encode_run(cls, run: ResearchRun) -> tuple[int, dict[str, object]]:
        """Return the store schema version and one run's canonical document form.

        Read-only; used by exports that must carry exactly the persisted shape.
        """
        return cls._SCHEMA_VERSION, cls._serialize_run(run)

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
                    "content_sha256": source.content_sha256,
                    "requested_url": source.requested_url,
                    "discovery_candidate_id": source.discovery_candidate_id,
                    "observation_id": source.observation_id,
                }
                for source in run.sources
            ],
            "failures": [
                {
                    "stage": failure.stage,
                    "reason": failure.reason,
                    "occurred_at": failure.occurred_at.isoformat(),
                    "provider": failure.provider,
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
                            "container": candidate.container,
                            "published_year": candidate.published_year,
                            "vulnerability": _encoded_vulnerability(
                                candidate.vulnerability
                            ),
                        }
                        for candidate in discovery.candidates
                    ],
                    "discovered_at": discovery.discovered_at.isoformat(),
                    "candidate_ids": list(discovery.candidate_ids),
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
                    "usefulness": assessment.usefulness.value,
                    "applicability": assessment.applicability.value,
                    "independence": assessment.independence.value,
                    "publication_status": assessment.publication_status.value,
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
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "text": claim.text,
                    "epistemic_state": claim.epistemic_state.value,
                    "confidence": claim.confidence.value,
                    "source_document_ids": list(claim.source_document_ids),
                    "evidence_ids": list(claim.evidence_ids),
                    "recorded_at": claim.recorded_at.isoformat(),
                    "supersedes_claim_id": claim.supersedes_claim_id,
                }
                for claim in run.claims
            ],
            "claim_contradictions": [
                {
                    "contradiction_id": contradiction.contradiction_id,
                    "claim_ids": list(contradiction.claim_ids),
                    "evidence_ids": list(contradiction.evidence_ids),
                    "note": contradiction.note,
                    "recorded_at": contradiction.recorded_at.isoformat(),
                }
                for contradiction in run.claim_contradictions
            ],
            "comparison_reviews": [
                {
                    "review_id": review.review_id,
                    "note_id": review.note_id,
                    "evidence_ids": list(review.evidence_ids),
                    "decision": review.decision.value,
                    "note": review.note,
                    "recorded_at": review.recorded_at.isoformat(),
                    "supersedes_review_id": review.supersedes_review_id,
                }
                for review in run.comparison_reviews
            ],
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        }

    @staticmethod
    def _serialize_source_revalidation(
        record: ResearchSourceRevalidationRecord,
    ) -> dict[str, object]:
        return {
            "revalidation_id": record.revalidation_id,
            "earlier_run_id": record.earlier_run_id,
            "earlier_observation_id": record.earlier_observation_id,
            "later_run_id": record.later_run_id,
            "later_observation_id": record.later_observation_id,
            "outcome": record.outcome.value,
            "recorded_at": record.recorded_at.isoformat(),
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
                run.claims,
                run.claim_contradictions,
                run.comparison_reviews,
            ):
                budget.consume_count(len(values))
            for review in run.comparison_reviews:
                budget.consume_count(len(review.evidence_ids))
            for discovery in run.discoveries:
                budget.consume_count(len(discovery.candidates))
            for assessment in run.assessments:
                budget.consume_count(len(assessment.evidence_ids))
            for note in run.comparison_notes:
                budget.consume_count(len(note.source_document_ids))
                budget.consume_count(len(note.evidence_ids))
                budget.consume_count(len(note.assessment_ids))
            for claim in run.claims:
                budget.consume_count(len(claim.source_document_ids))
                budget.consume_count(len(claim.evidence_ids))
            for contradiction in run.claim_contradictions:
                budget.consume_count(len(contradiction.claim_ids))
                budget.consume_count(len(contradiction.evidence_ids))
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
        claim_ids = [claim.claim_id for run in runs for claim in run.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ResearchError("Research run store contains duplicate claim IDs.")
        contradiction_ids = [
            contradiction.contradiction_id
            for run in runs
            for contradiction in run.claim_contradictions
        ]
        if len(contradiction_ids) != len(set(contradiction_ids)):
            raise ResearchError(
                "Research run store contains duplicate claim contradiction IDs."
            )
        review_ids = [
            review.review_id for run in runs for review in run.comparison_reviews
        ]
        if len(review_ids) != len(set(review_ids)):
            raise ResearchError(
                "Research run store contains duplicate comparison review IDs."
            )

    @staticmethod
    def _validate_source_revalidations(
        records: list[ResearchSourceRevalidationRecord],
    ) -> None:
        if not isinstance(records, list) or not all(
            isinstance(record, ResearchSourceRevalidationRecord) for record in records
        ):
            raise ResearchError(
                "Research run store accepts only source revalidation records."
            )
        identifiers = [record.revalidation_id for record in records]
        if len(identifiers) != len(set(identifiers)):
            raise ResearchError(
                "Research run store contains duplicate source revalidation IDs."
            )
        pairs = [
            (
                record.earlier_run_id,
                record.earlier_observation_id,
                record.later_run_id,
                record.later_observation_id,
            )
            for record in records
        ]
        if len(pairs) != len(set(pairs)):
            raise ResearchError(
                "Research run store contains duplicate source revalidation pairs."
            )

    @staticmethod
    def _validate_source_revalidation_bindings(
        records: list[ResearchSourceRevalidationRecord],
        runs: list[ResearchRun],
    ) -> None:
        from research.SourceIdentity import same_resource

        by_run = {run.run_id: run for run in runs}
        for record in records:
            earlier_run = by_run.get(record.earlier_run_id)
            later_run = by_run.get(record.later_run_id)
            if earlier_run is None or later_run is None:
                raise ResearchError(
                    "Research source revalidation references an unknown run."
                )
            earlier = next(
                (
                    source
                    for source in earlier_run.sources
                    if source.observation_id == record.earlier_observation_id
                ),
                None,
            )
            later = next(
                (
                    source
                    for source in later_run.sources
                    if source.observation_id == record.later_observation_id
                ),
                None,
            )
            if earlier is None or later is None:
                raise ResearchError(
                    "Research source revalidation references an unknown observation."
                )
            if (
                earlier.requested_url is None
                or later.requested_url is None
                or not same_resource(earlier.requested_url, later.requested_url)
            ):
                raise ResearchError(
                    "Research source revalidation resource lineage is invalid."
                )
            if earlier.content_sha256 is None or later.content_sha256 is None:
                raise ResearchError(
                    "Research source revalidation requires recorded content versions."
                )
            if earlier.fetched_at >= later.fetched_at:
                raise ResearchError(
                    "Research source revalidation observation order is invalid."
                )
            expected = (
                ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED
                if earlier.content_sha256 == later.content_sha256
                else ResearchSourceRevalidationOutcome.CONTENT_CHANGED
            )
            if record.outcome is not expected:
                raise ResearchError(
                    "Research source revalidation outcome differs from "
                    "recorded content."
                )

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _encoded_vulnerability(
    record: ResearchVulnerabilityRecord | None,
) -> dict[str, Any] | None:
    """Render one vulnerability record as bounded fields, never as raw JSON.

    Only the values the domain already validated are written. Keeping the
    provider's original document instead would mean storing an unbounded blob
    whose shape nothing in this system controls, and re-reading structure out of
    it later would be trusting a response we never checked.
    """
    if record is None:
        return None
    return {
        "cve_id": record.cve_id,
        "status": record.status,
        "source_identifier": record.source_identifier,
        "last_modified": (
            None if record.last_modified is None else record.last_modified.isoformat()
        ),
        "weaknesses": list(record.weaknesses),
        "metrics": [
            {
                "version": metric.version,
                "source": metric.source,
                "score": metric.score,
                "severity": metric.severity,
            }
            for metric in record.metrics
        ],
        "references": [
            {
                "url": reference.url,
                "source": reference.source,
                "tags": list(reference.tags),
            }
            for reference in record.references
        ],
        "reference_total": record.reference_total,
        "known_exploited_at": record.known_exploited_at,
        "known_exploited_name": record.known_exploited_name,
    }


def _parse_vulnerability(value: Any) -> ResearchVulnerabilityRecord | None:
    """Decode one stored vulnerability record, or refuse the document.

    Absent means absent — a Crossref candidate never had one. A present but
    unreadable one fails the load rather than degrading to `None`, because a
    record this build cannot decode is one somebody discovered, and showing it
    as never found would be worse than refusing to open the file.
    """
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != JsonFileResearchRunStore._VULNERABILITY_FIELDS
    ):
        raise ResearchError(
            "Research run store contains an invalid vulnerability record."
        )
    try:
        return ResearchVulnerabilityRecord(
            cve_id=value["cve_id"],
            status=value["status"],
            source_identifier=value["source_identifier"],
            last_modified=_parse_vulnerability_time(value["last_modified"]),
            weaknesses=tuple(value["weaknesses"]),
            metrics=tuple(
                _parse_vulnerability_metric(item) for item in value["metrics"]
            ),
            references=tuple(
                _parse_vulnerability_reference(item) for item in value["references"]
            ),
            reference_total=value["reference_total"],
            known_exploited_at=value["known_exploited_at"],
            known_exploited_name=value["known_exploited_name"],
        )
    except (TypeError, KeyError) as error:
        raise ResearchError(
            "Research run store contains an invalid vulnerability record."
        ) from error


def _parse_vulnerability_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ResearchError(
            "Research run store vulnerability time must be ISO-8601 text."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ResearchError(
            "Research run store vulnerability time is invalid."
        ) from error
    if parsed.tzinfo is None:
        raise ResearchError(
            "Research run store vulnerability time must carry an offset."
        )
    return parsed


def _parse_vulnerability_metric(value: Any) -> ResearchVulnerabilityMetric:
    if (
        not isinstance(value, dict)
        or set(value) != JsonFileResearchRunStore._VULNERABILITY_METRIC_FIELDS
    ):
        raise ResearchError(
            "Research run store contains an invalid vulnerability metric."
        )
    return ResearchVulnerabilityMetric(
        version=value["version"],
        source=value["source"],
        score=value["score"],
        severity=value["severity"],
    )


def _parse_vulnerability_reference(value: Any) -> ResearchVulnerabilityReference:
    if (
        not isinstance(value, dict)
        or set(value) != JsonFileResearchRunStore._VULNERABILITY_REFERENCE_FIELDS
    ):
        raise ResearchError(
            "Research run store contains an invalid vulnerability reference."
        )
    tags = value["tags"]
    if not isinstance(tags, list):
        raise ResearchError(
            "Research run store contains an invalid vulnerability reference."
        )
    return ResearchVulnerabilityReference(
        url=value["url"], source=value["source"], tags=tuple(tags)
    )
