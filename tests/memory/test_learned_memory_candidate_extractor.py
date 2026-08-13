from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch
from memory.LearnedMemoryCandidateExtractor import LearnedMemoryCandidateExtractor


class RecordingCandidateExtractor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def extract(
        self,
        source_text: str,
    ) -> LearnedMemoryCandidateBatch:
        self.calls.append(source_text)
        return LearnedMemoryCandidateBatch(
            source_text=source_text,
            candidates=(),
        )


class LearnedMemoryCandidateExtractorTests(unittest.TestCase):
    def test_conforming_extractor_preserves_exact_source_text(self) -> None:
        recording_extractor = RecordingCandidateExtractor()
        extractor: LearnedMemoryCandidateExtractor = recording_extractor
        source_text = "  Ben Python seviyorum.  "

        batch = extractor.extract(source_text)

        self.assertEqual(recording_extractor.calls, [source_text])
        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(batch.candidates, ())


if __name__ == "__main__":
    unittest.main()
