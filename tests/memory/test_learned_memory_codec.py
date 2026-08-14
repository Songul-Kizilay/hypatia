from __future__ import annotations

import sys
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCodec import decode_learned_memory, encode_learned_memory
from memory.MemoryRecord import MemoryRecord


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

    def test_valid_record_round_trips_from_exact_metadata(self) -> None:
        original = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="  Python  ",
        )
        content, tags, metadata = encode_learned_memory(original)
        record = MemoryRecord(
            memory_id="memory-1",
            content=content,
            tags=tags,
            metadata=metadata,
        )

        decoded = decode_learned_memory(record)

        self.assertEqual(decoded, original)
        self.assertEqual(record.metadata, metadata)
        self.assertEqual(record.tags, tags)

    def test_invalid_records_decode_to_none(self) -> None:
        cases = {
            "missing learned tag": {
                "tags": frozenset({"preference"}),
                "metadata": {
                    "kind": "preference",
                    "key": "preferred_language",
                    "value": "Python",
                },
            },
            "missing kind": {
                "tags": frozenset({"learned"}),
                "metadata": {"key": "preferred_language", "value": "Python"},
            },
            "missing key": {
                "tags": frozenset({"learned"}),
                "metadata": {"kind": "preference", "value": "Python"},
            },
            "missing value": {
                "tags": frozenset({"learned"}),
                "metadata": {"kind": "preference", "key": "preferred_language"},
            },
            "unknown kind": {
                "tags": frozenset({"learned"}),
                "metadata": {
                    "kind": "unknown",
                    "key": "preferred_language",
                    "value": "Python",
                },
            },
            "non-string kind": {
                "tags": frozenset({"learned"}),
                "metadata": {
                    "kind": ["preference"],
                    "key": "preferred_language",
                    "value": "Python",
                },
            },
            "non-string key": {
                "tags": frozenset({"learned"}),
                "metadata": {"kind": "preference", "key": 1, "value": "Python"},
            },
            "non-string value": {
                "tags": frozenset({"learned"}),
                "metadata": {
                    "kind": "preference",
                    "key": "preferred_language",
                    "value": 1,
                },
            },
        }

        for name, case in cases.items():
            with self.subTest(name=name):
                record = MemoryRecord(
                    memory_id=name,
                    content="ignored",
                    tags=cast(frozenset[str], case["tags"]),
                    metadata=cast(Mapping[str, Any], case["metadata"]),
                )

                self.assertIsNone(decode_learned_memory(record))

    def test_record_content_is_not_the_decode_source(self) -> None:
        record = MemoryRecord(
            memory_id="memory-2",
            content="different content",
            tags=frozenset({"learned", "goal"}),
            metadata={
                "kind": "goal",
                "key": "current_goal",
                "value": "  Ship Hypatia  ",
            },
        )

        self.assertEqual(
            decode_learned_memory(record),
            LearnedMemory(
                kind="goal",
                key="current_goal",
                value="  Ship Hypatia  ",
            ),
        )
