"""Read-only validation result for a user-controlled document relationship."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraphRelation


@dataclass(frozen=True, slots=True)
class KnowledgeRelationPreview:
    """Describes one validated, not-yet-applied document relationship."""

    source: KnowledgeDocumentReference
    relation: KnowledgeGraphRelation
    target: KnowledgeDocumentReference

    def __post_init__(self) -> None:
        if not isinstance(self.source, KnowledgeDocumentReference):
            raise KnowledgeError("Knowledge relation source is invalid.")
        if not isinstance(self.target, KnowledgeDocumentReference):
            raise KnowledgeError("Knowledge relation target is invalid.")
        if not isinstance(self.relation, KnowledgeGraphRelation):
            raise KnowledgeError("Knowledge relation type is invalid.")
        if self.relation is not KnowledgeGraphRelation.RELATED_TO:
            raise KnowledgeError("Knowledge relation type is not user-selectable.")
        if self.source.document_id == self.target.document_id:
            raise KnowledgeError("Knowledge relation source and target must differ.")
