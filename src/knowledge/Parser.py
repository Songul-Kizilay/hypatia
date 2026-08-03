"""Paragraph parser for the Knowledge Foundation."""

from __future__ import annotations

import re

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk, ChunkType
from knowledge.Document import Document


class Parser:
    """Splits source documents into ordered paragraph chunks."""

    def parse(self, document: Document) -> list[Chunk]:
        """Create one paragraph chunk for each non-empty document paragraph."""
        if not isinstance(document, Document):
            raise KnowledgeError("Parser expects a Document instance.")
        if document.is_empty():
            raise KnowledgeError("Document content cannot be empty.")

        paragraphs = (
            paragraph.strip() for paragraph in re.split(r"\n\s*\n", document.content)
        )
        chunks = [
            Chunk(
                document_id=document.document_id,
                index=index,
                content=paragraph,
                chunk_type=ChunkType.PARAGRAPH,
            )
            for index, paragraph in enumerate(paragraphs)
            if paragraph
        ]

        if not chunks:
            raise KnowledgeError("Document did not produce any chunks.")

        return chunks
