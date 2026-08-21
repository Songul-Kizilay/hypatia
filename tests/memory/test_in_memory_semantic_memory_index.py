from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

        with patch(
            "memory.InMemorySemanticMemoryIndex.MAX_EMBEDDING_DIMENSION",
            2,
        ):
            with self.assertRaisesRegex(ValueError, "supported positive integer"):
                InMemorySemanticMemoryIndex(3)

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

    def test_identifier_entry_and_aggregate_bounds_preserve_state(self) -> None:
        index = InMemorySemanticMemoryIndex()
        with (
            patch(
                "memory.InMemorySemanticMemoryIndex."
                "MAX_SEMANTIC_MEMORY_INDEX_MEMORY_ID_CHARACTERS",
                5,
            ),
            patch(
                "memory.InMemorySemanticMemoryIndex."
                "MAX_SEMANTIC_MEMORY_INDEX_ENTRIES",
                2,
            ),
            patch(
                "memory.InMemorySemanticMemoryIndex."
                "MAX_SEMANTIC_MEMORY_INDEX_VALUES",
                4,
            ),
        ):
            index.upsert("id001", Embedding((1, 0)))
            index.upsert("id002", Embedding((0, 1)))
            index.upsert("id001", Embedding((0, 1)))

            with self.assertRaisesRegex(ValueError, "memory ID.*too long"):
                index.upsert("id0003", Embedding((1, 0)))
            with self.assertRaisesRegex(ValueError, "too many entries"):
                index.upsert("id003", Embedding((1, 0)))

            self.assertEqual(index.count(), 2)
            self.assertEqual(index.dimension, 2)
            self.assertEqual(
                index.search(Embedding((0, 1))),
                (
                    SemanticMemoryMatch(memory_id="id001", score=1.0),
                    SemanticMemoryMatch(memory_id="id002", score=1.0),
                ),
            )

        empty_index = InMemorySemanticMemoryIndex()
        with patch(
            "memory.InMemorySemanticMemoryIndex." "MAX_SEMANTIC_MEMORY_INDEX_VALUES",
            1,
        ):
            with self.assertRaisesRegex(ValueError, "too many embedding values"):
                empty_index.upsert("memory-1", Embedding((1, 0)))
        self.assertEqual(empty_index.count(), 0)
        self.assertIsNone(empty_index.dimension)

    def test_cosine_search_remains_finite_for_large_numeric_values(self) -> None:
        index = InMemorySemanticMemoryIndex(dimension=4)
        index.upsert("same", Embedding((1e308, 1e308, 1e308, 1e308)))
        index.upsert("opposite", Embedding((-1e308, -1e308, -1e308, -1e308)))

        matches = index.search(Embedding((1e308, 1e308, 1e308, 1e308)))

        self.assertEqual(
            tuple(match.memory_id for match in matches), ("same", "opposite")
        )
        self.assertAlmostEqual(matches[0].score, 1.0)
        self.assertAlmostEqual(matches[1].score, -1.0)


if __name__ == "__main__":
    unittest.main()
