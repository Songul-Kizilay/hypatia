from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import LearnedMemoryCandidate


class LearnedMemoryCandidateTests(unittest.TestCase):
    def test_preserves_exact_memory_identity_and_source_text(self) -> None:
        memory = LearnedMemory(
            kind="preference",
            key="coffee_preference",
            value="  şekersiz  ",
        )

        candidate = LearnedMemoryCandidate(
            memory=memory,
            source_text="  Ben kahveyi şekersiz içerim.  ",
        )

        self.assertIs(candidate.memory, memory)
        self.assertEqual(candidate.memory.value, "  şekersiz  ")
        self.assertEqual(
            candidate.source_text,
            "  Ben kahveyi şekersiz içerim.  ",
        )

    def test_candidate_is_immutable(self) -> None:
        candidate = LearnedMemoryCandidate(
            memory=LearnedMemory(
                kind="preference",
                key="coffee_preference",
                value="şekersiz",
            ),
            source_text="Ben kahveyi şekersiz içerim.",
        )

        with self.assertRaises(FrozenInstanceError):
            candidate.source_text = "changed"  # type: ignore[misc]
