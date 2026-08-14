"""Build explicit, source-visible local knowledge prompts for an LLM."""

from __future__ import annotations

from collections.abc import Sequence

from knowledge.Chunk import Chunk
from knowledge.KnowledgeCitation import KnowledgeCitation


def build_knowledge_context_prompt(
    user_message: str,
    results: Sequence[Chunk],
    citations: Sequence[KnowledgeCitation],
) -> str:
    """Build a bounded prompt that names every local source used as context."""
    if len(results) != len(citations):
        raise ValueError("Knowledge results and citations must have equal length.")
    context_items = "\n\n".join(
        (
            f"[{index}] {citation.document_title} | "
            f"{citation.source or 'local source unavailable'} | "
            f"paragraph {citation.chunk_index + 1}\n{result.content}"
        )
        for index, (result, citation) in enumerate(
            zip(results, citations, strict=True),
            start=1,
        )
    )
    return (
        "Answer the user using only the local context below. "
        "If the context is insufficient, say so clearly.\n\n"
        f"Local context:\n{context_items}\n\n"
        f"User question: {user_message}"
    )
