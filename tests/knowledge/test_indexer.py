"""Unit tests for the in-memory Indexer."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk
from knowledge.Indexer import Indexer


class IndexerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.indexer = Indexer()
        self.first = Chunk(document_id="document", index=0, content="First")
        self.second = Chunk(document_id="document", index=1, content="Second")

    def test_add_increases_count(self) -> None:
        self.indexer.add(self.first)

        self.assertEqual(self.indexer.count(), 1)

    def test_contains_registered_chunk_id(self) -> None:
        self.indexer.add(self.first)

        self.assertTrue(self.indexer.contains(self.first.chunk_id))
        self.assertFalse(self.indexer.contains("missing"))

    def test_get_returns_registered_chunk(self) -> None:
        self.indexer.add(self.first)

        self.assertIs(self.indexer.get(self.first.chunk_id), self.first)

    def test_rejects_duplicate_chunk_id(self) -> None:
        self.indexer.add(self.first)

        with self.assertRaises(KnowledgeError):
            self.indexer.add(self.first)

    def test_rejects_missing_chunk_id(self) -> None:
        with self.assertRaises(KnowledgeError):
            self.indexer.get("missing")

    def test_remove_returns_chunk_and_reduces_count(self) -> None:
        self.indexer.add(self.first)

        removed = self.indexer.remove(self.first.chunk_id)

        self.assertIs(removed, self.first)
        self.assertEqual(self.indexer.count(), 0)

    def test_index_replaces_existing_chunks_and_returns_mapping(self) -> None:
        self.indexer.add(self.first)

        indexed = self.indexer.index([self.second])

        self.assertEqual(indexed, {self.second.chunk_id: self.second})
        self.assertEqual(self.indexer.all(), indexed)
