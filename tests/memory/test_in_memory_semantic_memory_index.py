from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.Embedding import Embedding
from memory.InMemorySemanticMemoryIndex import InMemorySemanticMemoryIndex
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class InMemorySemanticMemoryIndexTests(unittest.TestCase):
    def test_rejects_non_positive_or_boolean_dimension(self) -> None:
        for dimension in (0, -1, True):
            with self.subTest(dimension=dimension):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    InMemorySemanticMemoryIndex(dimension)

    def test_empty_index_returns_exact_empty_tuple(self) -> None:
        index = InMemorySemanticMemoryIndex()

        self.assertIsNone(index.dimension)
        self.assertEqual(index.search(Embedding((1, 0))), ())

    def test_upsert_replaces_existing_memory_without_duplicate_entry(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=2)
        index.upsert("memory-1", Embedding((1, 0)))
        index.upsert("memory-1", Embedding((0, 1)))

        self.assertEqual(index.dimension, 2)
        self.assertEqual(index.count(), 1)
        self.assertEqual(
            index.search(Embedding((1, 0))),
            (SemanticMemoryMatch(memory_id="memory-1", score=0.0),),
        )

    def test_remove_reports_existence_and_prevents_stale_result(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=2)
        index.upsert("memory-1", Embedding((1, 0)))

        self.assertTrue(index.remove("memory-1"))
        self.assertFalse(index.remove("memory-1"))
        self.assertEqual(index.count(), 0)
        self.assertEqual(index.search(Embedding((1, 0))), ())

    def test_search_orders_descending_similarity_then_memory_id(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=2)
        index.upsert("memory-c", Embedding((1, 0)))
        index.upsert("memory-a", Embedding((1, 0)))
        index.upsert("memory-b", Embedding((0, 1)))

        self.assertEqual(
            index.search(Embedding((1, 0))),
            (
                SemanticMemoryMatch(memory_id="memory-a", score=1.0),
                SemanticMemoryMatch(memory_id="memory-c", score=1.0),
                SemanticMemoryMatch(memory_id="memory-b", score=0.0),
            ),
        )

    def test_limit_is_applied_after_ranking(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=2)
        index.upsert("weaker", Embedding((1, 1)))
        index.upsert("stronger", Embedding((1, 0)))

        self.assertEqual(
            index.search(Embedding((1, 0)), limit=1),
            (SemanticMemoryMatch(memory_id="stronger", score=1.0),),
        )
        self.assertEqual(index.search(Embedding((1, 0)), limit=0), ())

    def test_zero_query_and_zero_stored_vector_do_not_produce_matches(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=2)
        index.upsert("zero", Embedding((0, 0)))
        index.upsert("non-zero", Embedding((1, 0)))

        self.assertEqual(index.search(Embedding((0, 0))), ())
        self.assertTrue(index.remove("non-zero"))
        self.assertEqual(index.search(Embedding((0, 1))), ())

    def test_rejects_invalid_id_embedding_dimension_and_limit(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=2)

        with self.assertRaisesRegex(ValueError, "non-empty memory ID"):
            index.upsert(" memory-1", Embedding((1, 0)))
        with self.assertRaisesRegex(ValueError, "does not match"):
            index.upsert("memory-1", Embedding((1, 0, 0)))
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            index.search(Embedding((1, 0)), limit=-1)
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            index.search(Embedding((1, 0)), limit=True)


if __name__ == "__main__":
    unittest.main()
