"""Structured observability for how far a source ingestion actually got.

The stage vocabulary is not redefined here. `SourceLoadStage` already names every
point the transaction can reach, and a second vocabulary would drift from it —
so these events carry that enum's values and nothing parallel to them.

Two rules shape the contract. An event is emitted only after the transition it
names has actually happened, with the deliberate exception of the `*_started`
events, which say a step is beginning and claim nothing about its outcome.
Inventing progress would make the event stream a worse record than the run
store, which is the one thing it must never be.

And the payload is machine-readable throughout: identifiers, a stage value, a
status, and booleans. No user-facing prose, no exception messages, no
translation. A subscriber deciding what to do reads fields; a person reading
about what happened reads the composed response, which is a different artefact
with different rules.

The invariant the whole pipeline exists to protect survives here too. A local
document existing and a research run accepting a source are separate facts, so
`document_id` and `attached_to_run` are separate fields and no combination of
events collapses them.
"""

from __future__ import annotations

from enum import StrEnum

from eventbus.EventBus import EventBus
from research.SourceLoadStage import SourceLoadStage

VALIDATION_STARTED = "source_ingestion.validation_started"
VALIDATION_COMPLETED = "source_ingestion.validation_completed"
FETCH_STARTED = "source_ingestion.fetch_started"
FETCH_COMPLETED = "source_ingestion.fetch_completed"
INDEX_STARTED = "source_ingestion.index_started"
INDEX_COMPLETED = "source_ingestion.index_completed"
ATTACH_STARTED = "source_ingestion.attach_started"
ATTACH_COMPLETED = "source_ingestion.attach_completed"
INGESTION_CANCELLED = "source_ingestion.cancelled"
INGESTION_FAILED = "source_ingestion.failed"

EVENT_SOURCE = "research.source_ingestion"

MAX_FAILURE_KIND_LENGTH = 60


class IngestionStatus(StrEnum):
    """Whether the named step is beginning, or how it turned out."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def asserts_an_outcome(self) -> bool:
        """Return whether this status claims the step actually finished."""
        return self is not IngestionStatus.STARTED


class IngestionFailureKind(StrEnum):
    """Bounded reason an ingestion stopped, carrying no exception text."""

    VALIDATION_REFUSED = "validation_refused"
    FETCH_REFUSED = "fetch_refused"
    INDEX_FAILED = "index_failed"
    CONTENT_PERSIST_FAILED = "content_persist_failed"
    ATTACH_REFUSED = "attach_refused"
    RUN_UNAVAILABLE = "run_unavailable"
    CANCELLED = "cancelled"


class SourceIngestionEvents:
    """Publish bounded ingestion events, or nothing when no bus is present."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        attempt_id: str = "",
    ) -> None:
        self._event_bus = event_bus
        self._attempt_id = attempt_id

    def for_attempt(self, attempt_id: str) -> SourceIngestionEvents:
        """Return a view bound to one ingestion attempt, sharing the bus."""
        return SourceIngestionEvents(self._event_bus, attempt_id)

    def validation_started(self, run_id: str = "") -> None:
        self._emit(
            VALIDATION_STARTED,
            SourceLoadStage.NOT_ATTEMPTED,
            IngestionStatus.STARTED,
            run_id=run_id,
        )

    def validation_completed(self, resource_identity: str, run_id: str = "") -> None:
        self._emit(
            VALIDATION_COMPLETED,
            SourceLoadStage.NOT_ATTEMPTED,
            IngestionStatus.COMPLETED,
            resource_identity=resource_identity,
            run_id=run_id,
        )

    def fetch_started(self, resource_identity: str, run_id: str = "") -> None:
        self._emit(
            FETCH_STARTED,
            SourceLoadStage.NOT_ATTEMPTED,
            IngestionStatus.STARTED,
            resource_identity=resource_identity,
            run_id=run_id,
        )

    def fetch_completed(self, resource_identity: str, run_id: str = "") -> None:
        self._emit(
            FETCH_COMPLETED,
            SourceLoadStage.NOT_ATTEMPTED,
            IngestionStatus.COMPLETED,
            resource_identity=resource_identity,
            run_id=run_id,
        )

    def index_started(self, resource_identity: str, run_id: str = "") -> None:
        self._emit(
            INDEX_STARTED,
            SourceLoadStage.NOT_ATTEMPTED,
            IngestionStatus.STARTED,
            resource_identity=resource_identity,
            run_id=run_id,
        )

    def index_completed(
        self,
        resource_identity: str,
        document_id: str,
        run_id: str = "",
    ) -> None:
        """Report that a local document now exists, and nothing more.

        The stage is INDEXED_WITHOUT_RUN even when a run is bound and
        attachment is about to be attempted, because at this instant that is
        exactly what is true.
        """
        self._emit(
            INDEX_COMPLETED,
            SourceLoadStage.INDEXED_WITHOUT_RUN,
            IngestionStatus.COMPLETED,
            resource_identity=resource_identity,
            document_id=document_id,
            run_id=run_id,
        )

    def attach_started(
        self,
        resource_identity: str,
        document_id: str,
        run_id: str,
    ) -> None:
        self._emit(
            ATTACH_STARTED,
            SourceLoadStage.INDEXED_WITHOUT_RUN,
            IngestionStatus.STARTED,
            resource_identity=resource_identity,
            document_id=document_id,
            run_id=run_id,
        )

    def attach_completed(
        self,
        resource_identity: str,
        document_id: str,
        run_id: str,
        accepted_source_count: int,
    ) -> None:
        """Report the one transition that means the run accepted the source."""
        self._emit(
            ATTACH_COMPLETED,
            SourceLoadStage.ACCEPTED_INTO_RUN,
            IngestionStatus.COMPLETED,
            resource_identity=resource_identity,
            document_id=document_id,
            run_id=run_id,
            accepted_source_count=accepted_source_count,
        )

    def cancelled(
        self,
        resource_identity: str = "",
        document_id: str = "",
        run_id: str = "",
    ) -> None:
        self._emit(
            INGESTION_CANCELLED,
            SourceLoadStage.CANCELLED,
            IngestionStatus.CANCELLED,
            resource_identity=resource_identity,
            document_id=document_id,
            run_id=run_id,
            failure_kind=IngestionFailureKind.CANCELLED,
        )

    def failed(
        self,
        stage: SourceLoadStage,
        failure_kind: IngestionFailureKind,
        *,
        resource_identity: str = "",
        document_id: str = "",
        run_id: str = "",
        safe_failure_recorded: bool = False,
    ) -> None:
        """Report a stop, naming the stage reached and a bounded reason."""
        self._emit(
            INGESTION_FAILED,
            stage,
            IngestionStatus.FAILED,
            resource_identity=resource_identity,
            document_id=document_id,
            run_id=run_id,
            failure_kind=failure_kind,
            safe_failure_recorded=safe_failure_recorded,
        )

    def _emit(
        self,
        name: str,
        stage: SourceLoadStage,
        status: IngestionStatus,
        *,
        resource_identity: str = "",
        document_id: str = "",
        run_id: str = "",
        accepted_source_count: int | None = None,
        failure_kind: IngestionFailureKind | None = None,
        safe_failure_recorded: bool = False,
    ) -> None:
        if self._event_bus is None:
            return
        payload: dict[str, object] = {
            "attempt_id": self._attempt_id,
            "stage": stage.value,
            "status": status.value,
            "resource_identity": resource_identity,
            "document_id": document_id,
            "run_id": run_id,
            "attached_to_run": stage.attached_to_run,
            "created_local_document": stage.created_local_document,
            "safe_failure_recorded": safe_failure_recorded,
        }
        if accepted_source_count is not None:
            payload["accepted_source_count"] = accepted_source_count
        if failure_kind is not None:
            payload["failure_kind"] = failure_kind.value[:MAX_FAILURE_KIND_LENGTH]
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
