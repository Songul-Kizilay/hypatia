"""Transactional owner of persisted research-run audit state."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchRunStatusTransitionPreview import (
    ResearchRunStatusTransitionPreview,
)
from research.ResearchRunStore import ResearchRunStore
from research.ResearchSource import ResearchSource
from research.ResearchSourceAssessmentPreview import ResearchSourceAssessmentPreview
from research.ResearchSourceAssessmentRecord import (
    MAX_SOURCE_ASSESSMENT_CHARACTERS,
    ResearchSourceAssessmentRecord,
)
from research.ResearchSourceAssessmentWritePreview import (
    ResearchSourceAssessmentWritePreview,
)
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)
from research.ResearchSourceComparisonItem import (
    MAX_COMPARISON_ASSESSMENTS_PER_SOURCE,
    MAX_COMPARISON_EVIDENCE_PER_SOURCE,
    ResearchSourceComparisonItem,
)
from research.ResearchSourceComparisonPreview import (
    MAX_COMPARISON_SOURCES,
    MIN_COMPARISON_SOURCES,
    ResearchSourceComparisonPreview,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchRunManager:
    """Create and update research runs only after snapshot persistence succeeds."""

    def __init__(
        self,
        store: ResearchRunStore | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        evidence_id_factory: Callable[[], str] | None = None,
        discovery_id_factory: Callable[[], str] | None = None,
        assessment_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._evidence_id_factory = evidence_id_factory or (lambda: str(uuid4()))
        self._discovery_id_factory = discovery_id_factory or (lambda: str(uuid4()))
        self._assessment_id_factory = assessment_id_factory or (lambda: str(uuid4()))
        self._runs: tuple[ResearchRun, ...] = ()
        self._lock = RLock()

    def load(self) -> None:
        """Load and atomically replace the current in-memory snapshot."""
        if self._store is None:
            return
        runs = self._store.load()
        with self._lock:
            self._runs = tuple(runs)

    def create(self, question: str) -> ResearchRun:
        """Create a collecting run for one explicit research question."""
        normalized_question = self._normalize_question(question)
        with self._lock:
            now = self._now()
            run = ResearchRun(
                run_id=self._new_run_id(),
                question=normalized_question,
                status=ResearchRunStatus.COLLECTING,
                sources=(),
                failures=(),
                created_at=now,
                updated_at=now,
                discoveries=(),
                assessments=(),
            )
            candidate = (*self._runs, run)
            self._persist(candidate)
            self._runs = candidate
        return run

    def list(self) -> list[ResearchRun]:
        """Return runs in deterministic creation order."""
        with self._lock:
            return list(self._runs)

    def get(self, run_id: str) -> ResearchRun:
        """Return one run or raise a controlled unknown-run error."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            run = next(
                (item for item in self._runs if item.run_id == normalized_id), None
            )
        if run is None:
            raise ResearchError(f"Research run was not found: {normalized_id}")
        return run

    def has_source(self, run_id: str, document_id: str) -> bool:
        """Return whether the run already records a source document."""
        run = self.get(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        return any(
            source.document_id == normalized_document_id for source in run.sources
        )

    def add_source(
        self,
        run_id: str,
        source: ResearchSource,
        document_id: str,
    ) -> ResearchRun:
        """Persist source provenance after successful local knowledge indexing."""
        normalized_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            if any(
                record.document_id == normalized_document_id for record in run.sources
            ):
                raise ResearchError("Research source is already attached to this run.")
            now = self._now()
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=(
                    *run.sources,
                    ResearchSourceRecord.from_source(
                        source,
                        normalized_document_id,
                        now,
                    ),
                ),
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def record_failure(self, run_id: str, stage: str, reason: str) -> ResearchRun:
        """Persist a safe bounded failure without retaining rejected URL input."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            now = self._now()
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=(
                    *run.failures,
                    ResearchFailureRecord(stage, reason, now),
                ),
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def add_evidence(self, run_id: str, chunk: Chunk, note: str) -> ResearchRun:
        """Persist one explicit evidence record from an accepted source chunk."""
        normalized_id = self._normalize_run_id(run_id)
        if not isinstance(chunk, Chunk):
            raise ResearchError("Research evidence expects a knowledge chunk.")
        normalized_note = self._normalize_evidence_note(note)
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            if not any(
                source.document_id == chunk.document_id for source in run.sources
            ):
                raise ResearchError(
                    "Research evidence must come from a source attached to this run."
                )
            now = self._now()
            evidence = ResearchEvidenceRecord.from_chunk(
                self._new_evidence_id(),
                chunk,
                normalized_note,
                now,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=(*run.evidence, evidence),
                discoveries=run.discoveries,
                assessments=run.assessments,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def add_discovery(
        self,
        run_id: str,
        query: str,
        provider: str,
        candidates: Sequence[ResearchSourceCandidate],
    ) -> ResearchRun:
        """Atomically persist one ordered, unaccepted discovery result."""
        normalized_id = self._normalize_run_id(run_id)
        normalized_query = self._normalize_question(query)
        normalized_provider = self._normalize_provider(provider)
        if not isinstance(candidates, list):
            raise ResearchError("Research source discovery candidates must be a list.")
        candidate_tuple: tuple[ResearchSourceCandidate, ...] = tuple(candidates)
        if len(candidate_tuple) > 10:
            raise ResearchError(
                "Research source discovery cannot contain more than 10 candidates."
            )
        if not all(
            isinstance(candidate, ResearchSourceCandidate)
            for candidate in candidate_tuple
        ):
            raise ResearchError(
                "Research source discovery contains an invalid candidate."
            )
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            now = self._now()
            discovery = ResearchSourceDiscoveryRecord(
                discovery_id=self._new_discovery_id(),
                query=normalized_query,
                provider=normalized_provider,
                candidates=candidate_tuple,
                discovered_at=now,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=(*run.discoveries, discovery),
                assessments=run.assessments,
            )
            candidate_runs = list(self._runs)
            candidate_runs[index] = updated
            candidate_snapshot = tuple(candidate_runs)
            self._persist(candidate_snapshot)
            self._runs = candidate_snapshot
        return updated

    def preview_status_transition(
        self,
        run_id: str,
        target_status: ResearchRunStatus,
    ) -> ResearchRunStatusTransitionPreview:
        """Return a no-side-effect decision for one terminal transition."""
        normalized_id = self._normalize_run_id(run_id)
        if not isinstance(target_status, ResearchRunStatus):
            raise ResearchError("Research run target status is invalid.")
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            return self._status_transition_preview(run, target_status)

    def preview_candidate_acceptance(
        self,
        run_id: str,
        discovery_id: str,
        candidate_url: str,
    ) -> ResearchSourceCandidateAcceptancePreview:
        """Revalidate one persisted candidate without network or mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_discovery_id = self._normalize_discovery_id(discovery_id)
        normalized_url = self._normalize_candidate_url(candidate_url)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            discovery = next(
                (
                    item
                    for item in run.discoveries
                    if item.discovery_id == normalized_discovery_id
                ),
                None,
            )
            if discovery is None:
                raise ResearchError("Research source discovery was not found.")
            candidate = next(
                (item for item in discovery.candidates if item.url == normalized_url),
                None,
            )
            if candidate is None:
                raise ResearchError(
                    "Research source candidate was not found in this discovery."
                )
            if run.status.terminal:
                return ResearchSourceCandidateAcceptancePreview(
                    run.run_id,
                    discovery.discovery_id,
                    candidate,
                    False,
                    "A closed research run cannot accept new sources.",
                )
            return ResearchSourceCandidateAcceptancePreview(
                run.run_id,
                discovery.discovery_id,
                candidate,
                True,
                "Research source candidate can be loaded and attached to this run.",
            )

    def preview_source_assessment(
        self,
        run_id: str,
        document_id: str,
    ) -> ResearchSourceAssessmentPreview:
        """Return accepted provenance and explicit evidence without mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            source = next(
                (
                    record
                    for record in run.sources
                    if record.document_id == normalized_document_id
                ),
                None,
            )
            if source is None:
                raise ResearchError(
                    "Research source was not found among this run's accepted sources."
                )
            evidence = tuple(
                record
                for record in run.evidence
                if record.source_document_id == source.document_id
            )
            evidence_count = len(evidence)
            reason = (
                f"Source has {evidence_count} user-selected evidence record"
                f"{'s' if evidence_count != 1 else ''} for manual assessment."
                if evidence
                else (
                    "Source has no user-selected evidence records; no quality or "
                    "support conclusion can be drawn."
                )
            )
            return ResearchSourceAssessmentPreview(
                run_id=run.run_id,
                run_status=run.status,
                source=source,
                evidence=evidence,
                has_recorded_evidence=bool(evidence),
                reason=reason,
                assessments=tuple(
                    record
                    for record in run.assessments
                    if record.source_document_id == source.document_id
                ),
            )

    def preview_source_comparison(
        self,
        run_id: str,
        document_ids: Sequence[str],
    ) -> ResearchSourceComparisonPreview:
        """Return ordered manual evidence columns without live work or mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_ids = self._normalize_comparison_document_ids(document_ids)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            sources_by_id = {source.document_id: source for source in run.sources}
            if any(
                document_id not in sources_by_id
                for document_id in normalized_document_ids
            ):
                raise ResearchError(
                    "A research comparison source was not found among this run's "
                    "accepted sources."
                )
            superseded_assessment_ids = {
                record.supersedes_assessment_id
                for record in run.assessments
                if record.supersedes_assessment_id is not None
            }
            items = tuple(
                self._comparison_item(
                    run,
                    sources_by_id[document_id],
                    superseded_assessment_ids,
                )
                for document_id in normalized_document_ids
            )
            return ResearchSourceComparisonPreview(
                run_id=run.run_id,
                question=run.question,
                run_status=run.status,
                sources=items,
                reason=(
                    f"{len(items)} explicitly selected accepted sources are shown "
                    "side by side for manual review."
                ),
            )

    @staticmethod
    def _comparison_item(
        run: ResearchRun,
        source: ResearchSourceRecord,
        superseded_assessment_ids: set[str],
    ) -> ResearchSourceComparisonItem:
        """Collect bounded display records while retaining honest total counts."""
        evidence: list[ResearchEvidenceRecord] = []
        total_evidence_count = 0
        for evidence_record in run.evidence:
            if evidence_record.source_document_id != source.document_id:
                continue
            total_evidence_count += 1
            if len(evidence) < MAX_COMPARISON_EVIDENCE_PER_SOURCE:
                evidence.append(evidence_record)

        current_assessments: list[ResearchSourceAssessmentRecord] = []
        total_current_assessment_count = 0
        for assessment_record in run.assessments:
            if (
                assessment_record.source_document_id != source.document_id
                or assessment_record.assessment_id in superseded_assessment_ids
            ):
                continue
            total_current_assessment_count += 1
            if len(current_assessments) < MAX_COMPARISON_ASSESSMENTS_PER_SOURCE:
                current_assessments.append(assessment_record)

        return ResearchSourceComparisonItem(
            source=source,
            evidence=tuple(evidence),
            current_assessments=tuple(current_assessments),
            omitted_evidence_count=total_evidence_count - len(evidence),
            omitted_current_assessment_count=(
                total_current_assessment_count - len(current_assessments)
            ),
        )

    def preview_source_assessment_write(
        self,
        run_id: str,
        document_id: str,
        evidence_ids: Sequence[str],
        text: str,
        supersedes_assessment_id: str | None = None,
    ) -> ResearchSourceAssessmentWritePreview:
        """Validate one authored assessment without mutating persisted state."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        normalized_evidence_ids = self._normalize_assessment_evidence_ids(evidence_ids)
        normalized_text = self._normalize_assessment_text(text)
        normalized_superseded_id = self._normalize_optional_assessment_id(
            supersedes_assessment_id
        )
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            source, evidence = self._source_and_evidence_for_assessment(
                run,
                normalized_document_id,
                normalized_evidence_ids,
            )
            superseded_assessment = self._superseded_assessment_for_write(
                run,
                source.document_id,
                normalized_superseded_id,
            )
            allowed = not run.status.terminal
            reason = (
                (
                    "Research source assessment correction can be recorded after "
                    "confirmation."
                    if superseded_assessment is not None
                    else (
                        "Research source assessment can be recorded after "
                        "confirmation."
                    )
                )
                if allowed
                else "A closed research run cannot accept new assessments."
            )
            return ResearchSourceAssessmentWritePreview(
                run_id=run.run_id,
                run_status=run.status,
                source=source,
                evidence=evidence,
                text=normalized_text,
                allowed=allowed,
                reason=reason,
                supersedes_assessment=superseded_assessment,
            )

    def record_source_assessment(
        self,
        run_id: str,
        document_id: str,
        evidence_ids: Sequence[str],
        text: str,
        supersedes_assessment_id: str | None = None,
    ) -> ResearchRun:
        """Revalidate and atomically append one user-authored assessment."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        normalized_evidence_ids = self._normalize_assessment_evidence_ids(evidence_ids)
        normalized_text = self._normalize_assessment_text(text)
        normalized_superseded_id = self._normalize_optional_assessment_id(
            supersedes_assessment_id
        )
        with self._lock:
            index, run = self._find_with_index(normalized_run_id)
            source, evidence = self._source_and_evidence_for_assessment(
                run,
                normalized_document_id,
                normalized_evidence_ids,
            )
            superseded_assessment = self._superseded_assessment_for_write(
                run,
                source.document_id,
                normalized_superseded_id,
            )
            self._require_collecting(run)
            now = self._now()
            assessment = ResearchSourceAssessmentRecord(
                assessment_id=self._new_assessment_id(),
                source_document_id=source.document_id,
                evidence_ids=tuple(record.evidence_id for record in evidence),
                text=normalized_text,
                recorded_at=now,
                supersedes_assessment_id=(
                    None
                    if superseded_assessment is None
                    else superseded_assessment.assessment_id
                ),
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=(*run.assessments, assessment),
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def transition_status(
        self,
        run_id: str,
        target_status: ResearchRunStatus,
    ) -> ResearchRun:
        """Revalidate and atomically persist one terminal status transition."""
        normalized_id = self._normalize_run_id(run_id)
        if not isinstance(target_status, ResearchRunStatus):
            raise ResearchError("Research run target status is invalid.")
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            preview = self._status_transition_preview(run, target_status)
            if not preview.allowed:
                raise ResearchError(preview.reason)
            now = self._now()
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=target_status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    @staticmethod
    def _status_transition_preview(
        run: ResearchRun,
        target_status: ResearchRunStatus,
    ) -> ResearchRunStatusTransitionPreview:
        if target_status is ResearchRunStatus.COLLECTING:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A research run can transition only to a terminal status.",
            )
        if run.status.terminal:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A closed research run cannot change status.",
            )
        if target_status is ResearchRunStatus.COMPLETED and not run.sources:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A completed research run requires at least one accepted source.",
            )
        if target_status is ResearchRunStatus.COMPLETED and not run.evidence:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A completed research run requires at least one evidence record.",
            )
        if target_status is ResearchRunStatus.FAILED and not run.failures:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A failed research run requires at least one failure record.",
            )
        return ResearchRunStatusTransitionPreview(
            run.run_id,
            run.status,
            target_status,
            True,
            f"Research run can be marked {target_status.value}.",
        )

    @staticmethod
    def _require_collecting(run: ResearchRun) -> None:
        if run.status.terminal:
            raise ResearchError("A closed research run cannot be changed.")

    def _find_with_index(self, run_id: str) -> tuple[int, ResearchRun]:
        for index, run in enumerate(self._runs):
            if run.run_id == run_id:
                return index, run
        raise ResearchError(f"Research run was not found: {run_id}")

    def _persist(self, runs: tuple[ResearchRun, ...]) -> None:
        if self._store is not None:
            self._store.save(list(runs))

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ResearchError("Research run clock must return a timezone-aware time.")
        return now

    def _new_run_id(self) -> str:
        run_id = self._normalize_run_id(self._id_factory())
        if any(run.run_id == run_id for run in self._runs):
            raise ResearchError("Research run ID already exists.")
        return run_id

    def _new_evidence_id(self) -> str:
        evidence_id = self._normalize_evidence_id(self._evidence_id_factory())
        if any(
            record.evidence_id == evidence_id
            for run in self._runs
            for record in run.evidence
        ):
            raise ResearchError("Research evidence ID already exists.")
        return evidence_id

    def _new_discovery_id(self) -> str:
        discovery_id = self._normalize_discovery_id(self._discovery_id_factory())
        if any(
            record.discovery_id == discovery_id
            for run in self._runs
            for record in run.discoveries
        ):
            raise ResearchError("Research source discovery ID already exists.")
        return discovery_id

    def _new_assessment_id(self) -> str:
        assessment_id = self._normalize_assessment_id(self._assessment_id_factory())
        if any(
            record.assessment_id == assessment_id
            for run in self._runs
            for record in run.assessments
        ):
            raise ResearchError("Research source assessment ID already exists.")
        return assessment_id

    @staticmethod
    def _source_and_evidence_for_assessment(
        run: ResearchRun,
        document_id: str,
        evidence_ids: tuple[str, ...],
    ) -> tuple[ResearchSourceRecord, tuple[ResearchEvidenceRecord, ...]]:
        source = next(
            (record for record in run.sources if record.document_id == document_id),
            None,
        )
        if source is None:
            raise ResearchError(
                "Research source was not found among this run's accepted sources."
            )
        evidence_by_id = {record.evidence_id: record for record in run.evidence}
        try:
            evidence = tuple(
                evidence_by_id[evidence_id] for evidence_id in evidence_ids
            )
        except KeyError as error:
            raise ResearchError(
                "Research assessment evidence was not found in this run."
            ) from error
        if any(record.source_document_id != source.document_id for record in evidence):
            raise ResearchError(
                "Research assessment evidence must belong to the selected source."
            )
        return source, evidence

    @staticmethod
    def _superseded_assessment_for_write(
        run: ResearchRun,
        document_id: str,
        supersedes_assessment_id: str | None,
    ) -> ResearchSourceAssessmentRecord | None:
        if supersedes_assessment_id is None:
            return None
        assessment = next(
            (
                record
                for record in run.assessments
                if record.assessment_id == supersedes_assessment_id
            ),
            None,
        )
        if assessment is None:
            raise ResearchError(
                "Superseded research assessment was not found in this run."
            )
        if assessment.source_document_id != document_id:
            raise ResearchError(
                "Superseded research assessment must belong to the selected source."
            )
        if any(
            record.supersedes_assessment_id == assessment.assessment_id
            for record in run.assessments
        ):
            raise ResearchError(
                "Research source assessment has already been superseded."
            )
        return assessment

    @staticmethod
    def _normalize_question(question: str) -> str:
        if not isinstance(question, str) or not question.strip():
            raise ResearchError("Research question cannot be empty.")
        normalized = question.strip()
        if len(normalized) > 2_000:
            raise ResearchError("Research question is too long.")
        return normalized

    @staticmethod
    def _normalize_run_id(run_id: str) -> str:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("Research run ID cannot be empty.")
        return run_id.strip()

    @staticmethod
    def _normalize_document_id(document_id: str) -> str:
        if not isinstance(document_id, str) or not document_id.strip():
            raise ResearchError("Research source document ID cannot be empty.")
        return document_id.strip()

    @staticmethod
    def _normalize_comparison_document_ids(
        document_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(document_ids, (str, bytes)) or not isinstance(
            document_ids, Sequence
        ):
            raise ResearchError("Research comparison source IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_document_id(value) for value in document_ids
        )
        if not MIN_COMPARISON_SOURCES <= len(normalized) <= MAX_COMPARISON_SOURCES:
            raise ResearchError("Research source comparison requires 2 to 5 sources.")
        if len(normalized) != len(set(normalized)):
            raise ResearchError(
                "Research source comparison contains duplicate sources."
            )
        return normalized

    @staticmethod
    def _normalize_evidence_id(evidence_id: str) -> str:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ResearchError("Research evidence ID cannot be empty.")
        return evidence_id.strip()

    @staticmethod
    def _normalize_evidence_note(note: str) -> str:
        if not isinstance(note, str) or not note.strip():
            raise ResearchError("Research evidence note cannot be empty.")
        normalized = note.strip()
        if len(normalized) > 1_000:
            raise ResearchError("Research evidence note is too long.")
        return normalized

    @staticmethod
    def _normalize_assessment_id(assessment_id: str) -> str:
        if not isinstance(assessment_id, str) or not assessment_id.strip():
            raise ResearchError("Research source assessment ID cannot be empty.")
        normalized = assessment_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research source assessment ID is too long.")
        return normalized

    @staticmethod
    def _normalize_optional_assessment_id(
        assessment_id: str | None,
    ) -> str | None:
        if assessment_id is None:
            return None
        return ResearchRunManager._normalize_assessment_id(assessment_id)

    @staticmethod
    def _normalize_assessment_evidence_ids(
        evidence_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(evidence_ids, (str, bytes)) or not isinstance(
            evidence_ids, Sequence
        ):
            raise ResearchError("Research assessment evidence IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_evidence_id(value) for value in evidence_ids
        )
        if not normalized:
            raise ResearchError(
                "Research source assessment requires explicit evidence IDs."
            )
        if len(normalized) != len(set(normalized)):
            raise ResearchError(
                "Research source assessment contains duplicate evidence IDs."
            )
        if len(normalized) > 20:
            raise ResearchError(
                "Research source assessment cannot cite more than 20 evidence records."
            )
        return normalized

    @staticmethod
    def _normalize_assessment_text(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ResearchError("Research source assessment text cannot be empty.")
        normalized = text.strip()
        if len(normalized) > MAX_SOURCE_ASSESSMENT_CHARACTERS:
            raise ResearchError("Research source assessment text is too long.")
        return normalized

    @staticmethod
    def _normalize_discovery_id(discovery_id: str) -> str:
        if not isinstance(discovery_id, str) or not discovery_id.strip():
            raise ResearchError("Research source discovery ID cannot be empty.")
        normalized = discovery_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research source discovery ID is too long.")
        return normalized

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        if not isinstance(provider, str) or not provider.strip():
            raise ResearchError("Research source discovery provider cannot be empty.")
        normalized = provider.strip()
        if len(normalized) > 200:
            raise ResearchError("Research source discovery provider is too long.")
        if any(character in normalized for character in ("\r", "\n", "\t")):
            raise ResearchError("Research source discovery provider is invalid.")
        return normalized

    @staticmethod
    def _normalize_candidate_url(candidate_url: str) -> str:
        if not isinstance(candidate_url, str) or not candidate_url.strip():
            raise ResearchError("Research source candidate URL cannot be empty.")
        return candidate_url.strip()
