"""Fail-closed startup restoration for persisted accepted research content."""

from __future__ import annotations

import re
from datetime import datetime

from core.Exceptions import KnowledgeError, ResearchError
from knowledge.Document import Document
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchRun import ResearchRun
from research.ResearchSource import ResearchSource
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)
from research.ResearchSourceContentStore import ResearchSourceContentStore
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchSourceContentRestorer:
    """Restore only content that exactly matches accepted run provenance."""

    _MAXIMUM_RESTORED_PARAGRAPHS = 20_000

    def __init__(
        self,
        store: ResearchSourceContentStore,
        knowledge_engine: KnowledgeEngine,
    ) -> None:
        self._store = store
        self._knowledge_engine = knowledge_engine

    def restore(
        self,
        runs: list[ResearchRun],
    ) -> ResearchSourceContentRestorationStatus:
        """Validate the complete snapshot before rebuilding the empty index."""
        if not isinstance(runs, list) or not all(
            isinstance(run, ResearchRun) for run in runs
        ):
            raise ResearchError("Research source restoration requires research runs.")
        records = self._store.load()
        if not records:
            return ResearchSourceContentRestorationStatus(True, 0, 0)
        if self._knowledge_engine.documents():
            raise ResearchError(
                "Research source restoration requires an empty knowledge index."
            )
        provenance_by_document_id = self._provenance_by_document_id(runs)
        documents = [
            self._validated_document(record, provenance_by_document_id)
            for record in records
        ]
        restored_paragraph_count = sum(
            self._paragraph_count(document.content) for document in documents
        )
        if restored_paragraph_count > self._MAXIMUM_RESTORED_PARAGRAPHS:
            raise ResearchError(
                "Persisted research source content has too many paragraphs."
            )
        try:
            for document in documents:
                self._knowledge_engine.add_document(document)
        except KnowledgeError as error:
            self._knowledge_engine.clear()
            raise ResearchError(
                "Unable to restore accepted research source content."
            ) from error
        return ResearchSourceContentRestorationStatus(
            available=True,
            restored_document_count=len(documents),
            restored_paragraph_count=restored_paragraph_count,
        )

    @classmethod
    def _provenance_by_document_id(
        cls,
        runs: list[ResearchRun],
    ) -> dict[str, ResearchSourceRecord]:
        provenance: dict[str, ResearchSourceRecord] = {}
        for run in runs:
            for source in run.sources:
                existing = provenance.get(source.document_id)
                if existing is not None and cls._provenance_identity(
                    existing
                ) != cls._provenance_identity(source):
                    raise ResearchError(
                        "Research runs contain conflicting source provenance."
                    )
                provenance.setdefault(source.document_id, source)
        return provenance

    @classmethod
    def _validated_document(
        cls,
        record: ResearchSourceContentRecord,
        provenance_by_document_id: dict[str, ResearchSourceRecord],
    ) -> Document:
        provenance = provenance_by_document_id.get(record.document_id)
        if provenance is None:
            raise ResearchError(
                "Persisted research source content has no accepted provenance."
            )
        if cls._content_identity(record) != cls._provenance_identity(provenance):
            raise ResearchError(
                "Persisted research source content does not match its provenance."
            )
        source = ResearchSource(
            url=record.url,
            title=record.title,
            content=record.content,
            content_type=record.content_type,
            fetched_at=record.fetched_at,
        )
        if source.content != record.content:
            raise ResearchError("Persisted research source content is not canonical.")
        document = source.to_document()
        if document.document_id != record.document_id:
            raise ResearchError(
                "Persisted research source content has an invalid document ID."
            )
        return document

    @staticmethod
    def _paragraph_count(content: str) -> int:
        return sum(
            1 for paragraph in re.split(r"\n\s*\n", content) if paragraph.strip()
        )

    @staticmethod
    def _content_identity(
        record: ResearchSourceContentRecord,
    ) -> tuple[str, str, str, str, datetime]:
        return (
            record.document_id,
            record.url,
            record.title,
            record.content_type,
            record.fetched_at,
        )

    @staticmethod
    def _provenance_identity(
        record: ResearchSourceRecord,
    ) -> tuple[str, str, str, str, datetime]:
        return (
            record.document_id,
            record.url,
            record.title,
            record.content_type,
            record.fetched_at,
        )
