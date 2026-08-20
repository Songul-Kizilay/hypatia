"""Transactional owner of persisted research-run audit state."""

from __future__ import annotations

from collections.abc import Callable
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
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._evidence_id_factory = evidence_id_factory or (lambda: str(uuid4()))
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
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
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
