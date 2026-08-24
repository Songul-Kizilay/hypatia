"""How a locally indexed resource relates to the research runs.

The vocabulary is chosen carefully, because the obvious word is wrong. A
document that no research run references is not an orphan — it is very often a
book, a note, or a page someone loaded on purpose to search locally, and calling
it an orphan invites deleting it. It is knowledge-only: real, wanted, and simply
not part of a research run's evidence chain.

The word orphan is reserved for the one case that genuinely is structural
breakage: a run naming a document that is not in the local index at all. There
the reference points at nothing, and something really has gone wrong.

Nothing here deletes, merges, or repairs. Classifying is reading.
"""

from __future__ import annotations

from enum import StrEnum


class KnowledgeAttachment(StrEnum):
    """Name one bounded relationship between a resource and the research runs."""

    ATTACHED = "attached"
    KNOWLEDGE_ONLY = "knowledge_only"
    BROKEN_REFERENCE = "broken_reference"

    @property
    def in_research(self) -> bool:
        """Return whether a research run has accepted this resource."""
        return self is KnowledgeAttachment.ATTACHED

    @property
    def indexed_locally(self) -> bool:
        """Return whether the local index actually holds this document.

        A broken reference is the case where it does not: a run points at a
        document the index cannot produce.
        """
        return self is not KnowledgeAttachment.BROKEN_REFERENCE

    @property
    def is_structural_breakage(self) -> bool:
        """Return whether this classification means something is actually wrong.

        Knowledge-only is not breakage. It is the normal state of anything
        loaded for local search rather than for a research run.
        """
        return self is KnowledgeAttachment.BROKEN_REFERENCE
