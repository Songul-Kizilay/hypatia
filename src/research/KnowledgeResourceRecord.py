"""One resource on this machine, and how research relates to it.

A record is keyed by resource identity rather than document ID, so two stored
records of the same page are one entry holding two document identifiers. That is
the honest shape: the machine holds one page, and it holds it twice.

The record carries the run identifiers that reference the resource. An empty
tuple with a present document means knowledge-only; a present tuple with no
document means the reference is broken.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.KnowledgeAttachment import KnowledgeAttachment

MAX_RECORD_TITLE_LENGTH = 200


@dataclass(frozen=True, slots=True)
class KnowledgeResourceRecord:
    """Describe one resource, its stored documents, and its research runs."""

    resource_identity: str
    attachment: KnowledgeAttachment
    document_ids: tuple[str, ...] = ()
    run_ids: tuple[str, ...] = ()
    title: str = ""

    def __post_init__(self) -> None:
        if not self.resource_identity.strip():
            raise ResearchError("A knowledge resource needs an identity.")
        if not isinstance(self.attachment, KnowledgeAttachment):
            raise ResearchError("A knowledge attachment must be a bounded value.")
        if len(self.title) > MAX_RECORD_TITLE_LENGTH:
            raise ResearchError("A knowledge resource title is too long.")
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ResearchError("A knowledge resource repeats a document.")
        if len(set(self.run_ids)) != len(self.run_ids):
            raise ResearchError("A knowledge resource repeats a run.")
        self._validate_consistency()

    def _validate_consistency(self) -> None:
        """Refuse a classification the identifiers do not support."""
        if self.attachment.indexed_locally and not self.document_ids:
            raise ResearchError(
                "An indexed resource must name at least one local document."
            )
        if self.attachment is KnowledgeAttachment.BROKEN_REFERENCE:
            if self.document_ids:
                raise ResearchError(
                    "A broken reference names no local document by definition."
                )
            if not self.run_ids:
                raise ResearchError("A broken reference must name the run using it.")
        if self.attachment is KnowledgeAttachment.ATTACHED and not self.run_ids:
            raise ResearchError("An attached resource must name its research runs.")
        if self.attachment is KnowledgeAttachment.KNOWLEDGE_ONLY and self.run_ids:
            raise ResearchError("A knowledge-only resource names no research run.")

    @property
    def document_count(self) -> int:
        """Return how many stored documents hold this one resource."""
        return len(self.document_ids)

    @property
    def duplicated(self) -> bool:
        """Return whether this resource is stored more than once."""
        return self.document_count > 1

    def line(self) -> str:
        """Render one bounded line naming the resource and its documents."""
        label = self.title or self.resource_identity
        return (
            f"{label} [{self.attachment.value}] "
            f"documents={self.document_count} runs={len(self.run_ids)}"
        )
