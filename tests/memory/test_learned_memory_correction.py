from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCorrection import (
    correct_learned_memory_value,
    correct_learned_memory_value_if_changed,
    should_correct_learned_memory,
)
from memory.LearnedMemoryStore import (
    append_learned_memory,
    load_latest_learned_memory,
    load_learned_memories,
)
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


class LearnedMemoryCorrectionTests(unittest.TestCase):
    def test_corrects_only_when_exact_current_value_changed(self) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        current = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        sentinel_record = MemoryRecord(
            memory_id="corrected-record",
            content="Rust",
        )
        cases = (
            ("exact no-op", current, False, None, False),
            ("different value", current, True, sentinel_record, True),
            ("missing current", None, True, sentinel_record, True),
        )

        for name, latest, should_correct, expected, expect_write in cases:
            with (
                self.subTest(name=name),
                patch(
                    "memory.LearnedMemoryCorrection.load_latest_learned_memory",
                    return_value=latest,
                ) as load_latest,
                patch(
                    "memory.LearnedMemoryCorrection.should_correct_learned_memory",
                    return_value=should_correct,
                ) as decide,
                patch(
                    "memory.LearnedMemoryCorrection.correct_learned_memory_value",
                    return_value=sentinel_record,
                ) as correct,
            ):
                result = correct_learned_memory_value_if_changed(
                    memory_manager,
                    kind="preference",
                    key="preferred_language",
                    value="Rust",
                )

                load_latest.assert_called_once_with(
                    memory_manager,
                    kind="preference",
                    key="preferred_language",
                )
                decide.assert_called_once_with(
                    latest,
                    kind="preference",
                    key="preferred_language",
                    value="Rust",
                )
                if expect_write:
                    correct.assert_called_once_with(
                        memory_manager,
                        kind="preference",
                        key="preferred_language",
                        value="Rust",
                    )
                    self.assertIs(result, expected)
                else:
                    correct.assert_not_called()
                    self.assertIsNone(result)

        memory_manager.add.assert_not_called()
        memory_manager.update.assert_not_called()
        memory_manager.delete.assert_not_called()

    def test_should_correct_requires_an_exact_current_match(self) -> None:
        current = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        cases = (
            (
                "missing current",
                None,
                "preference",
                "preferred_language",
                "Python",
                True,
            ),
            (
                "exact match",
                current,
                "preference",
                "preferred_language",
                "Python",
                False,
            ),
            (
                "different value",
                current,
                "preference",
                "preferred_language",
                "Rust",
                True,
            ),
            ("different key", current, "preference", "language", "Python", True),
            (
                "different kind",
                current,
                "user_fact",
                "preferred_language",
                "Python",
                True,
            ),
            (
                "case difference",
                current,
                "preference",
                "preferred_language",
                "python",
                True,
            ),
            (
                "whitespace difference",
                current,
                "preference",
                "preferred_language",
                " Python ",
                True,
            ),
        )

        for name, candidate, kind, key, value, expected in cases:
            with self.subTest(name=name):
                self.assertIs(
                    should_correct_learned_memory(
                        candidate,
                        kind=kind,
                        key=key,
                        value=value,
                    ),
                    expected,
                )

        self.assertEqual(
            current,
            LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="Python",
            ),
        )

    @patch("memory.LearnedMemoryCorrection.correct_learned_memory")
    def test_constructs_exact_memory_and_preserves_record_identity(
        self,
        correct_learned_memory,
    ) -> None:
        memory_manager = MagicMock(spec=MemoryManager)
        sentinel_record = MemoryRecord(
            memory_id="corrected-record",
            content="content",
        )
        correct_learned_memory.return_value = sentinel_record

        result = correct_learned_memory_value(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="  Rust  ",
        )

        correct_learned_memory.assert_called_once_with(
            memory_manager,
            LearnedMemory(
                kind="preference",
                key="preferred_language",
                value="  Rust  ",
            ),
        )
        self.assertIs(result, sentinel_record)
        memory_manager.add.assert_not_called()
        memory_manager.update.assert_not_called()
        memory_manager.delete.assert_not_called()

    def test_real_store_preserves_history_and_resolves_correction(self) -> None:
        memory_manager = MemoryManager()
        original = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        corrected = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        append_learned_memory(memory_manager, original)

        record = correct_learned_memory_value(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="Rust",
        )

        self.assertEqual(
            load_learned_memories(memory_manager),
            (original, corrected),
        )
        self.assertEqual(
            load_latest_learned_memory(
                memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            corrected,
        )
        self.assertEqual(memory_manager.count(), 2)
        self.assertIs(memory_manager.get(record.memory_id), record)
        self.assertEqual(record.content, "Rust")
        self.assertEqual(record.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            dict(record.metadata),
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Rust",
            },
        )

    def test_real_store_exact_correction_is_a_no_op(self) -> None:
        memory_manager = MemoryManager()
        original = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        original_record = append_learned_memory(memory_manager, original)
        before_snapshot = memory_manager.snapshot()

        result = correct_learned_memory_value_if_changed(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="Python",
        )

        after_snapshot = memory_manager.snapshot()
        self.assertIsNone(result)
        self.assertEqual(len(before_snapshot), 1)
        self.assertEqual(memory_manager.count(), 1)
        self.assertEqual(after_snapshot, before_snapshot)
        self.assertIs(after_snapshot[0], original_record)
        self.assertEqual(load_learned_memories(memory_manager), (original,))
        self.assertEqual(original_record.content, "Python")
        self.assertEqual(
            original_record.tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            dict(original_record.metadata),
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )

    def test_real_store_changed_value_appends_and_becomes_latest(self) -> None:
        memory_manager = MemoryManager()
        original = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        corrected = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Rust",
        )
        original_record = append_learned_memory(memory_manager, original)

        result = correct_learned_memory_value_if_changed(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="Rust",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(memory_manager.count(), 2)
        self.assertEqual(
            load_learned_memories(memory_manager),
            (original, corrected),
        )
        self.assertEqual(
            load_latest_learned_memory(
                memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            corrected,
        )
        snapshot = memory_manager.snapshot()
        self.assertIs(snapshot[0], original_record)
        self.assertIs(snapshot[1], result)
        self.assertEqual(original_record.content, "Python")
        self.assertEqual(
            original_record.tags,
            frozenset({"learned", "preference"}),
        )
        self.assertEqual(
            dict(original_record.metadata),
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertEqual(result.content, "Rust")
        self.assertEqual(result.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            dict(result.metadata),
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Rust",
            },
        )

    def test_real_store_missing_current_creates_first_memory(self) -> None:
        memory_manager = MemoryManager()
        expected = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )

        result = correct_learned_memory_value_if_changed(
            memory_manager,
            kind="preference",
            key="preferred_language",
            value="Python",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(memory_manager.count(), 1)
        self.assertIs(memory_manager.snapshot()[0], result)
        self.assertEqual(result.content, "Python")
        self.assertEqual(result.tags, frozenset({"learned", "preference"}))
        self.assertEqual(
            dict(result.metadata),
            {
                "kind": "preference",
                "key": "preferred_language",
                "value": "Python",
            },
        )
        self.assertEqual(load_learned_memories(memory_manager), (expected,))
        self.assertEqual(
            load_latest_learned_memory(
                memory_manager,
                kind="preference",
                key="preferred_language",
            ),
            expected,
        )
