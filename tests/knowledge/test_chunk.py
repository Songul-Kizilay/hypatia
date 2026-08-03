"""Unit tests for the Chunk model."""

from __future__ import annotations

import unittest

from knowledge.Chunk import Chunk, ChunkType


class ChunkTests(unittest.TestCase):
    def test_initializes_common_chunk_fields(self) -> None:
        chunk = Chunk(
            document_id=" document-1 ",
            index=2,
            content=" Hypatia content ",
            chunk_type=ChunkType.PARAGRAPH,
            metadata={"section": 1},
        )

        self.assertEqual(chunk.document_id, "document-1")
        self.assertEqual(chunk.index, 2)
        self.assertEqual(chunk.content, "Hypatia content")
        self.assertEqual(chunk.chunk_type, ChunkType.PARAGRAPH)
        self.assertEqual(chunk.metadata, {"section": 1})
        self.assertEqual(chunk.size(), len("Hypatia content"))
        self.assertFalse(chunk.is_empty())

    def test_rejects_blank_document_id(self) -> None:
        with self.assertRaises(ValueError):
            Chunk(document_id=" ", index=0, content="Content")

    def test_rejects_blank_content(self) -> None:
        with self.assertRaises(ValueError):
            Chunk(document_id="document", index=0, content=" ")

    def test_update_content_refreshes_timestamp(self) -> None:
        chunk = Chunk(document_id="document", index=0, content="Old content")
        created_at = chunk.updated_at

        chunk.update_content(" New content ")

        self.assertEqual(chunk.content, "New content")
        self.assertGreaterEqual(chunk.updated_at, created_at)
