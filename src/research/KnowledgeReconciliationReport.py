"""What is indexed, what research uses, and what is neither — counted honestly.

The report separates documents from resources throughout, because they are
different questions and only one of them is about independent evidence. Two
records of the same page are two documents and one resource, and a reconciliation
that reported only documents would make a duplicate look like extra coverage —
the same confusion the corroboration counting already had to fix.

Nothing here is a cleanup list. Knowledge-only resources are reported because
knowing what is on the machine is useful, not because anything should be removed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.KnowledgeAttachment import KnowledgeAttachment
from research.KnowledgeResourceRecord import KnowledgeResourceRecord


@dataclass(frozen=True, slots=True)
class KnowledgeReconciliationReport:
    """Report how local knowledge and research-run membership line up."""

    records: tuple[KnowledgeResourceRecord, ...]

    def __post_init__(self) -> None:
        if not all(
            isinstance(record, KnowledgeResourceRecord) for record in self.records
        ):
            raise ResearchError("A reconciliation report accepts only records.")

    def of_attachment(
        self,
        attachment: KnowledgeAttachment,
    ) -> tuple[KnowledgeResourceRecord, ...]:
        """Return every record with one bounded classification."""
        return tuple(
            record for record in self.records if record.attachment is attachment
        )

    @property
    def attached(self) -> tuple[KnowledgeResourceRecord, ...]:
        """Return the resources a research run has accepted."""
        return self.of_attachment(KnowledgeAttachment.ATTACHED)

    @property
    def knowledge_only(self) -> tuple[KnowledgeResourceRecord, ...]:
        """Return indexed resources no research run references."""
        return self.of_attachment(KnowledgeAttachment.KNOWLEDGE_ONLY)

    @property
    def broken_references(self) -> tuple[KnowledgeResourceRecord, ...]:
        """Return runs pointing at documents the index does not hold."""
        return self.of_attachment(KnowledgeAttachment.BROKEN_REFERENCE)

    @property
    def indexed_document_count(self) -> int:
        """Return how many local documents exist, duplicates included."""
        return sum(
            record.document_count
            for record in self.records
            if record.attachment.indexed_locally
        )

    @property
    def indexed_resource_count(self) -> int:
        """Return how many distinct resources are indexed locally."""
        return sum(1 for record in self.records if record.attachment.indexed_locally)

    @property
    def healthy(self) -> bool:
        """Return whether nothing is structurally broken.

        Knowledge-only resources do not make a machine unhealthy. Only a run
        referencing a document the index cannot produce does.
        """
        return not self.broken_references

    def lines(self) -> tuple[str, ...]:
        """Render the counts as bounded, separately labelled lines."""
        return (
            f"Indexed resources: {self.indexed_resource_count}",
            f"Indexed documents: {self.indexed_document_count}",
            f"Attached to research: {len(self.attached)}",
            f"Knowledge-only: {len(self.knowledge_only)}",
            f"Broken references: {len(self.broken_references)}",
        )

    def counts(self) -> dict[str, int]:
        """Return bounded counts suitable for an event payload."""
        return {
            "indexed_resources": self.indexed_resource_count,
            "indexed_documents": self.indexed_document_count,
            "attached": len(self.attached),
            "knowledge_only": len(self.knowledge_only),
            "broken_references": len(self.broken_references),
        }
