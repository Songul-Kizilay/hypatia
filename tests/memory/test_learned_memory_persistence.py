from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryPersistence import persist_learned_memory


class LearnedMemoryPersistenceTests(unittest.TestCase):
    @patch("memory.LearnedMemoryPersistence.encode_learned_memory")
    def test_persists_encoded_fields_once_and_returns_exact_record(
        self,
        encode_learned_memory: Mock,
    ) -> None:
        memory = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="  Python  ",
        )
        sentinel_content = "  Python  "
        sentinel_tags = frozenset({"learned", "preference"})
        sentinel_metadata = {
            "kind": "preference",
            "key": "preferred_language",
            "value": "  Python  ",
        }
        sentinel_record = object()
        memory_manager = Mock()
        encode_learned_memory.return_value = (
            sentinel_content,
            sentinel_tags,
            sentinel_metadata,
        )
        memory_manager.add.return_value = sentinel_record

        result = persist_learned_memory(memory_manager, memory)

        encode_learned_memory.assert_called_once_with(memory)
        memory_manager.add.assert_called_once_with(
            content=sentinel_content,
            tags=sentinel_tags,
            metadata=sentinel_metadata,
        )
        self.assertIs(result, sentinel_record)
        self.assertEqual(memory.kind, "preference")
        self.assertEqual(memory.key, "preferred_language")
        self.assertEqual(memory.value, "  Python  ")
