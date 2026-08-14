"""Read-only validation result for removing a local document relationship."""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import KnowledgeError
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview


@dataclass(frozen=True, slots=True)
class KnowledgeRelationRevocationPreview:
    """Describes one validated, not-yet-applied relation removal."""

    relation: KnowledgeRelationPreview
    persisted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.relation, KnowledgeRelationPreview):
            raise KnowledgeError("Knowledge relation removal preview is invalid.")
        if not isinstance(self.persisted, bool):
            raise KnowledgeError("Knowledge relation removal persistence is invalid.")
