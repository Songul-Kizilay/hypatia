"""Transactional owner of persisted research-run audit state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from core.Exceptions import ResearchError
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
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
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
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
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

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
