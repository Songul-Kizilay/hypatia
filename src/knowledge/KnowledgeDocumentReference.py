"""Stable read model for a locally loaded knowledge source."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.Document import DocumentType


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentReference:
    """Identifies one loaded local document for explicit user selection."""

    document_id: str
    title: str
    source: str
    document_type: DocumentType
    chunk_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise KnowledgeError("Knowledge document ID cannot be empty.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise KnowledgeError("Knowledge document title cannot be empty.")
        if not isinstance(self.source, str):
            raise KnowledgeError("Knowledge document source must be text.")
        if not isinstance(self.document_type, DocumentType):
            raise KnowledgeError("Knowledge document type is invalid.")
        if isinstance(self.chunk_count, bool) or self.chunk_count < 0:
            raise KnowledgeError("Knowledge document chunk count cannot be negative.")
        object.__setattr__(self, "document_id", self.document_id.strip())
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "source", self.source.strip())
