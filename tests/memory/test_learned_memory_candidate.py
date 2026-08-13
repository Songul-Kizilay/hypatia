from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)


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

    def test_batch_preserves_exact_source_tuple_order_and_identity(self) -> None:
        candidate_a = LearnedMemoryCandidate(
            memory=LearnedMemory(
                kind="user_fact",
                key="name",
                value="Songül",
            ),
            source_text="candidate source a",
        )
        candidate_b = LearnedMemoryCandidate(
            memory=LearnedMemory(
                kind="preference",
                key="preferred_programming_language",
                value="Python",
            ),
            source_text="candidate source b",
        )
        candidates = (candidate_a, candidate_b)

        batch = LearnedMemoryCandidateBatch(
            source_text="  exact source  ",
            candidates=candidates,
        )

        self.assertEqual(batch.source_text, "  exact source  ")
        self.assertIs(batch.candidates, candidates)
        self.assertIs(batch.candidates[0], candidate_a)
        self.assertIs(batch.candidates[1], candidate_b)

    def test_batch_accepts_exact_empty_tuple(self) -> None:
        candidates: tuple[LearnedMemoryCandidate, ...] = ()

        batch = LearnedMemoryCandidateBatch(
            source_text="Merhaba",
            candidates=candidates,
        )

        self.assertIs(batch.candidates, candidates)
        self.assertEqual(batch.candidates, ())

    def test_batch_is_immutable(self) -> None:
        batch = LearnedMemoryCandidateBatch(
            source_text="source",
            candidates=(),
        )

        with self.assertRaises(FrozenInstanceError):
            batch.source_text = "changed"  # type: ignore[misc]
