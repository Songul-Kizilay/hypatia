"""The one canonical source-acceptance transaction.

Extracted from the research source-load route so exactly one implementation
exists. Both the explicit source-load route and the Research Plan
`SOURCE_ACCEPT` capability call this service; neither reimplements the flow.

The transaction is unchanged:

    fetched source
    -> knowledge indexing
    -> source-content persistence
    -> ResearchRunManager.add_source
    -> layered rollback on failure

Accepted means accepted into the run's canonical source set and nothing more.
No evidence, assessment, claim, trust, or conclusion is produced here.

There are two successful outcomes and they are not the same. With a run bound,
the source is attached to it and the stage is ACCEPTED_INTO_RUN. With no run
bound, the document is indexed into local knowledge and the stage is
INDEXED_WITHOUT_RUN — a real result, but not an accepted research source, and
nothing may record evidence from it. Both used to return the same flag, which
let a knowledge-only index be reported to a person as a loaded research source.
"""

from __future__ import annotations

from datetime import UTC, datetime

from cognition.SourceIngestionEvents import (
    IngestionFailureKind,
    SourceIngestionEvents,
)
from core.Exceptions import KnowledgeError, ResearchError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceAcceptanceResult import ResearchSourceAcceptanceResult
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceContentStore import ResearchSourceContentStore
from research.SourceIdentity import identity_of
from research.SourceLoadStage import SourceLoadStage


class ResearchSourceAcceptanceService:
    """Index, persist, and record one fetched source atomically."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        research_run_manager: ResearchRunManager | None = None,
        research_source_content_store: ResearchSourceContentStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._research_run_manager = research_run_manager
        self._research_source_content_store = research_source_content_store
        self._events = SourceIngestionEvents(event_bus)

    def accept(
        self,
        source: ResearchSource,
        run_id: str = "",
        attempt_id: str = "",
    ) -> ResearchSourceAcceptanceResult:
        """Run the canonical acceptance transaction for one fetched source.

        Indexing failures raise `KnowledgeError` so the caller can distinguish
        them from acquisition failures, exactly as before the extraction.
        """
        events = self._events.for_attempt(attempt_id)
        resource = identity_of(source.url)
        source_document = source.to_document()
        events.index_started(resource, run_id=run_id)
        try:
            document = self._knowledge_engine.add_document(
                source_document,
                stable_chunk_ids=bool(run_id),
            )
        except KnowledgeError:
            events.failed(
                SourceLoadStage.INDEX_FAILED,
                IngestionFailureKind.INDEX_FAILED,
                resource_identity=resource,
                run_id=run_id,
            )
            raise
        events.index_completed(resource, document.document_id, run_id=run_id)

        if not run_id or self._research_run_manager is None:
            return ResearchSourceAcceptanceResult(
                accepted=True,
                transaction_attempted=True,
                document_id=document.document_id,
                run=None,
                stage=SourceLoadStage.INDEXED_WITHOUT_RUN,
            )

        content_snapshot: list[ResearchSourceContentRecord] | None = None
        if self._research_source_content_store is not None:
            try:
                content_snapshot = self._research_source_content_store.load()
                content_record = ResearchSourceContentRecord.from_source(
                    source,
                    document.document_id,
                    datetime.now(UTC),
                )
                self._research_source_content_store.save(
                    [*content_snapshot, content_record]
                )
            except ResearchError:
                try:
                    self._knowledge_engine.remove_document(document.document_id)
                except KnowledgeError:
                    return self._failed(
                        events,
                        "Research source content failed and knowledge "
                        "rollback failed.",
                        SourceLoadStage.CONTENT_PERSIST_FAILED,
                        IngestionFailureKind.CONTENT_PERSIST_FAILED,
                        resource,
                        run_id,
                    )
                return self._failed(
                    events,
                    "Research source content could not be saved; "
                    "knowledge was rolled back.",
                    SourceLoadStage.CONTENT_PERSIST_FAILED,
                    IngestionFailureKind.CONTENT_PERSIST_FAILED,
                    resource,
                    run_id,
                )

        events.attach_started(resource, document.document_id, run_id)
        try:
            run = self._research_run_manager.add_source(
                run_id,
                source,
                document.document_id,
            )
        except ResearchError:
            return self._failed(
                events,
                self._rollback(document.document_id, content_snapshot),
                SourceLoadStage.RUN_ATTACH_FAILED,
                IngestionFailureKind.ATTACH_REFUSED,
                resource,
                run_id,
            )
        events.attach_completed(
            resource,
            document.document_id,
            run_id,
            len(run.sources),
        )
        return ResearchSourceAcceptanceResult(
            accepted=True,
            transaction_attempted=True,
            document_id=document.document_id,
            run=run,
            stage=SourceLoadStage.ACCEPTED_INTO_RUN,
        )

    def _rollback(
        self,
        document_id: str,
        content_snapshot: list[ResearchSourceContentRecord] | None,
    ) -> str:
        """Undo partial acceptance and describe exactly what was recovered."""
        content_rollback_failed = False
        if (
            content_snapshot is not None
            and self._research_source_content_store is not None
        ):
            try:
                self._research_source_content_store.save(content_snapshot)
            except ResearchError:
                content_rollback_failed = True
        knowledge_rollback_failed = False
        try:
            self._knowledge_engine.remove_document(document_id)
        except KnowledgeError:
            knowledge_rollback_failed = True

        if content_rollback_failed and knowledge_rollback_failed:
            return (
                "Research source audit, content rollback, and knowledge "
                "rollback failed."
            )
        if content_rollback_failed:
            return (
                "Research source audit failed and content rollback failed; "
                "knowledge was rolled back."
            )
        if knowledge_rollback_failed:
            return (
                "Research source audit failed and knowledge rollback failed; "
                "content was rolled back."
            )
        if content_snapshot is not None:
            return (
                "Research source audit could not be saved; content and "
                "knowledge were rolled back."
            )
        return "Research source audit could not be saved; knowledge was rolled back."

    @staticmethod
    def _failed(
        events: SourceIngestionEvents,
        reason: str,
        stage: SourceLoadStage,
        failure_kind: IngestionFailureKind,
        resource_identity: str,
        run_id: str,
    ) -> ResearchSourceAcceptanceResult:
        """Announce the stop once, then return the matching result."""
        events.failed(
            stage,
            failure_kind,
            resource_identity=resource_identity,
            run_id=run_id,
        )
        return ResearchSourceAcceptanceResult(
            accepted=False,
            transaction_attempted=True,
            failure_reason=reason,
            stage=stage,
        )
