from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.Embedding import Embedding
from memory.MemoryManager import MemoryManager
from memory.SemanticMemoryIndexBuilder import SemanticMemoryIndexBuilder
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class StubEmbeddingProvider:
    def __init__(self, embeddings_by_text: dict[str, Embedding]) -> None:
        self._embeddings_by_text = embeddings_by_text
        self.requests: list[str] = []

    def embed(self, source_text: str) -> Embedding:
        self.requests.append(source_text)
        return self._embeddings_by_text[source_text]


class SemanticMemoryIndexBuilderTests(unittest.TestCase):
    def test_build_uses_exact_active_memory_content_in_creation_order(self) -> None:
        memory_manager = MemoryManager()
        first = memory_manager.add("First fact")
        second = memory_manager.add("Second fact")
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((0, 1)),
            }
        )

        index = SemanticMemoryIndexBuilder(provider).build(memory_manager)

        self.assertEqual(index.dimension, 2)
        self.assertEqual(index.count(), 2)
        self.assertEqual(
            index.search(Embedding((1, 0))),
            (
                SemanticMemoryMatch(memory_id=first.memory_id, score=1.0),
                SemanticMemoryMatch(memory_id=second.memory_id, score=0.0),
            ),
        )
        self.assertEqual(provider.requests, ["First fact", "Second fact"])

    def test_build_returns_empty_index_when_memory_is_empty(self) -> None:
        provider = StubEmbeddingProvider({})

        index = SemanticMemoryIndexBuilder(provider).build(MemoryManager())

        self.assertIsNone(index.dimension)
        self.assertEqual(index.count(), 0)

    def test_rebuild_creates_a_replacement_index_without_stale_entries(self) -> None:
        memory_manager = MemoryManager()
        original = memory_manager.add("Original fact")
        provider = StubEmbeddingProvider(
            {
                "Original fact": Embedding((1, 0)),
                "Replacement fact": Embedding((0, 1)),
            }
        )
        builder = SemanticMemoryIndexBuilder(provider)

        first_index = builder.build(memory_manager)
        self.assertTrue(memory_manager.delete(original.memory_id))
        replacement = memory_manager.add("Replacement fact")

        rebuilt_index = builder.build(memory_manager)

        self.assertEqual(first_index.count(), 1)
        self.assertEqual(rebuilt_index.count(), 1)
        self.assertEqual(
            rebuilt_index.search(Embedding((0, 1))),
            (SemanticMemoryMatch(memory_id=replacement.memory_id, score=1.0),),
        )

    def test_build_rejects_a_provider_embedding_with_wrong_dimension(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        memory_manager.add("Second fact")
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((1, 0, 0)),
            }
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            SemanticMemoryIndexBuilder(provider).build(memory_manager)


if __name__ == "__main__":
    unittest.main()
