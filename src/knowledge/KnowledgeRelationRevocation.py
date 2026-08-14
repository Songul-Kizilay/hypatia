"""Result of removing one explicit local document relationship."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeGraph import KnowledgeGraph, KnowledgeGraphEdge
from knowledge.KnowledgeRelationRevocationPreview import (
    KnowledgeRelationRevocationPreview,
)


@dataclass(frozen=True, slots=True)
class KnowledgeRelationRevocation:
    """Records one confirmed graph and optional persistence removal."""

    preview: KnowledgeRelationRevocationPreview
    edge: KnowledgeGraphEdge

    def __post_init__(self) -> None:
        if not isinstance(self.preview, KnowledgeRelationRevocationPreview):
            raise KnowledgeError(
                "Knowledge relation removal result preview is invalid."
            )
        if not isinstance(self.edge, KnowledgeGraphEdge):
            raise KnowledgeError("Knowledge relation removal result edge is invalid.")
        relation = self.preview.relation
        if (
            self.edge.source_node_id
            != KnowledgeGraph.document_node_id(relation.source.document_id)
            or self.edge.target_node_id
            != KnowledgeGraph.document_node_id(relation.target.document_id)
            or self.edge.relation is not relation.relation
        ):
            raise KnowledgeError(
                "Knowledge relation removal result does not match preview."
            )
