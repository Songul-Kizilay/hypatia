"""Read model for one active explicit local document relationship."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import KnowledgeGraphRelation


@dataclass(frozen=True, slots=True)
class KnowledgeRelationReference:
    """Presents one active relation with its loaded endpoint identities."""

    source: KnowledgeDocumentReference
    relation: KnowledgeGraphRelation
    target: KnowledgeDocumentReference
    persisted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source, KnowledgeDocumentReference):
            raise KnowledgeError("Knowledge relation source reference is invalid.")
        if not isinstance(self.target, KnowledgeDocumentReference):
            raise KnowledgeError("Knowledge relation target reference is invalid.")
        if self.source.document_id == self.target.document_id:
            raise KnowledgeError("Knowledge relation source and target must differ.")
        if self.relation is not KnowledgeGraphRelation.RELATED_TO:
            raise KnowledgeError("Knowledge relation type is not user-selectable.")
        if not isinstance(self.persisted, bool):
            raise KnowledgeError("Knowledge relation persistence flag is invalid.")
