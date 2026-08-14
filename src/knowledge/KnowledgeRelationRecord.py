"""Versionable local record for one explicit document relationship."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeGraph import KnowledgeGraphRelation


@dataclass(frozen=True, slots=True)
class KnowledgeRelationRecord:
    """Stores the user-selectable relation independently of graph node IDs."""

    source_document_id: str
    relation: KnowledgeGraphRelation
    target_document_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_document_id, str)
            or not self.source_document_id.strip()
        ):
            raise KnowledgeError(
                "Knowledge relation source document ID cannot be empty."
            )
        if (
            not isinstance(self.target_document_id, str)
            or not self.target_document_id.strip()
        ):
            raise KnowledgeError(
                "Knowledge relation target document ID cannot be empty."
            )
        if self.source_document_id.strip() == self.target_document_id.strip():
            raise KnowledgeError("Knowledge relation source and target must differ.")
        if self.relation is not KnowledgeGraphRelation.RELATED_TO:
            raise KnowledgeError("Knowledge relation type is not user-selectable.")
        object.__setattr__(self, "source_document_id", self.source_document_id.strip())
        object.__setattr__(self, "target_document_id", self.target_document_id.strip())
