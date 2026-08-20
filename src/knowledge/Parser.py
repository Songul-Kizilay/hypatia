"""Paragraph parser for the Knowledge Foundation."""

from __future__ import annotations

import hashlib
import re
from uuid import NAMESPACE_URL, uuid5

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk, ChunkType
from knowledge.Document import Document


class Parser:
    """Splits source documents into ordered paragraph chunks."""

    def parse(
        self,
        document: Document,
        *,
        stable_chunk_ids: bool = False,
    ) -> list[Chunk]:
        """Create one paragraph chunk for each non-empty document paragraph."""
        if not isinstance(document, Document):
            raise KnowledgeError("Parser expects a Document instance.")
        if document.is_empty():
            raise KnowledgeError("Document content cannot be empty.")
        if not isinstance(stable_chunk_ids, bool):
            raise KnowledgeError("Stable chunk identity option must be boolean.")

        paragraphs = (
            paragraph.strip() for paragraph in re.split(r"\n\s*\n", document.content)
        )
        chunks = [
            self._paragraph_chunk(
                document,
                index,
                paragraph,
                stable_chunk_ids=stable_chunk_ids,
            )
            for index, paragraph in enumerate(paragraphs)
            if paragraph
        ]

        if not chunks:
            raise KnowledgeError("Document did not produce any chunks.")

        return chunks

    @classmethod
    def _paragraph_chunk(
        cls,
        document: Document,
        index: int,
        content: str,
        *,
        stable_chunk_ids: bool,
    ) -> Chunk:
        metadata = {
            "document_title": document.title,
            "document_source": document.source,
            "document_type": document.document_type.value,
        }
        if stable_chunk_ids:
            return Chunk(
                document_id=document.document_id,
                index=index,
                content=content,
                chunk_type=ChunkType.PARAGRAPH,
                metadata=metadata,
                chunk_id=cls._stable_chunk_id(document.document_id, index, content),
            )
        return Chunk(
            document_id=document.document_id,
            index=index,
            content=content,
            chunk_type=ChunkType.PARAGRAPH,
            metadata=metadata,
        )

    @staticmethod
    def _stable_chunk_id(document_id: str, index: int, content: str) -> str:
        """Bind an opaque v1 identity to document, position, and exact text."""
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        identity = f"hypatia:knowledge-chunk:v1:{document_id}:{index}:{content_sha256}"
        return str(uuid5(NAMESPACE_URL, identity))
