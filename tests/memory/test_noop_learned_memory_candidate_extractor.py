from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemoryCandidateExtractor import LearnedMemoryCandidateExtractor
from memory.NoOpLearnedMemoryCandidateExtractor import (
    NoOpLearnedMemoryCandidateExtractor,
)


class NoOpLearnedMemoryCandidateExtractorTests(unittest.TestCase):
    def test_conforms_to_protocol_and_preserves_exact_source_text(self) -> None:
        extractor: LearnedMemoryCandidateExtractor = (
            NoOpLearnedMemoryCandidateExtractor()
        )
        source_text = "  Ben Python seviyorum.  "

        batch = extractor.extract(source_text)

        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(batch.candidates, ())

    def test_each_call_returns_an_exact_empty_batch_without_state(self) -> None:
        extractor: LearnedMemoryCandidateExtractor = (
            NoOpLearnedMemoryCandidateExtractor()
        )

        first_batch = extractor.extract("first source")
        second_batch = extractor.extract("  second source  ")

        self.assertEqual(first_batch.source_text, "first source")
        self.assertEqual(first_batch.candidates, ())
        self.assertEqual(second_batch.source_text, "  second source  ")
        self.assertEqual(second_batch.candidates, ())


if __name__ == "__main__":
    unittest.main()
