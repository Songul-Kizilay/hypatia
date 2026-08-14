"""Applied, explicit local document relationship."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeGraph import KnowledgeGraph, KnowledgeGraphEdge
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview


@dataclass(frozen=True, slots=True)
class KnowledgeRelationApplication:
    """Records the result of one confirmed, in-memory graph mutation."""

    preview: KnowledgeRelationPreview
    edge: KnowledgeGraphEdge
    persisted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.preview, KnowledgeRelationPreview):
            raise KnowledgeError("Knowledge relation application preview is invalid.")
        if not isinstance(self.edge, KnowledgeGraphEdge):
            raise KnowledgeError("Knowledge relation application edge is invalid.")
        if not isinstance(self.persisted, bool):
            raise KnowledgeError("Knowledge relation persistence flag is invalid.")
        if (
            self.edge.source_node_id
            != KnowledgeGraph.document_node_id(self.preview.source.document_id)
            or self.edge.target_node_id
            != KnowledgeGraph.document_node_id(self.preview.target.document_id)
            or self.edge.relation is not self.preview.relation
        ):
            raise KnowledgeError(
                "Knowledge relation application does not match preview."
            )
