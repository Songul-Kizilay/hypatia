from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.Embedding import Embedding


class EmbeddingTests(unittest.TestCase):
    def test_normalizes_finite_numeric_values_to_immutable_float_tuple(self) -> None:
        embedding = Embedding((1, -2.5, 0))

        self.assertEqual(embedding.values, (1.0, -2.5, 0.0))
        self.assertEqual(embedding.dimension, 3)

    def test_rejects_empty_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            Embedding(())

    def test_rejects_non_finite_and_non_numeric_values(self) -> None:
        for value in (math.inf, -math.inf, math.nan, "1", True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite numbers"):
                    Embedding((value,))  # type: ignore[arg-type]

    def test_dimension_bound_accepts_exact_limit_and_rejects_overflow(self) -> None:
        with patch("memory.Embedding.MAX_EMBEDDING_DIMENSION", 2):
            self.assertEqual(Embedding((1, 0)).dimension, 2)
            with self.assertRaisesRegex(ValueError, "cannot exceed 2"):
                Embedding((1, 0, 0))


if __name__ == "__main__":
    unittest.main()
