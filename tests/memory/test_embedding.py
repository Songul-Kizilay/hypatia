from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
