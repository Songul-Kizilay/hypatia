from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory


class LearnedMemoryTests(unittest.TestCase):
    def test_preference_preserves_exact_content(self) -> None:
        memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="  Python  ",
        )

        self.assertEqual(memory.kind, "preference")
        self.assertEqual(memory.key, "preferred_language")
        self.assertEqual(memory.value, "  Python  ")

    def test_user_fact_preserves_exact_content(self) -> None:
        memory = LearnedMemory(
            kind="user_fact",
            key=" name ",
            value="  Songül  ",
        )

        self.assertEqual(memory.kind, "user_fact")
        self.assertEqual(memory.key, " name ")
        self.assertEqual(memory.value, "  Songül  ")

    def test_memory_is_immutable(self) -> None:
        memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )

        with self.assertRaises(FrozenInstanceError):
            memory.value = "Rust"  # type: ignore[misc]
