from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCodec import encode_learned_memory


class LearnedMemoryCodecTests(unittest.TestCase):
    def test_preference_is_encoded_exactly_and_source_is_unchanged(self) -> None:
        memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="  Python  ",
        )

        encoded = encode_learned_memory(memory)

        self.assertEqual(
            encoded,
            (
                "  Python  ",
                frozenset({"learned", "preference"}),
                {
                    "kind": "preference",
                    "key": "preferred_language",
                    "value": "  Python  ",
                },
            ),
        )
        self.assertIsInstance(encoded[1], frozenset)
        self.assertEqual(memory.kind, "preference")
        self.assertEqual(memory.key, "preferred_language")
        self.assertEqual(memory.value, "  Python  ")

    def test_user_fact_is_encoded_exactly(self) -> None:
        memory = LearnedMemory(
            kind="user_fact",
            key=" name ",
            value=" Songül ",
        )

        self.assertEqual(
            encode_learned_memory(memory),
            (
                " Songül ",
                frozenset({"learned", "user_fact"}),
                {
                    "kind": "user_fact",
                    "key": " name ",
                    "value": " Songül ",
                },
            ),
        )
