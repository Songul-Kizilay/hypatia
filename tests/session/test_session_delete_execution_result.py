"""Unit tests for the immutable session-delete execution result contract."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult


class SessionDeleteExecutionResultTests(unittest.TestCase):
    def test_zero_memory_success_result_has_the_locked_field_order(self) -> None:
        result = SessionDeleteExecutionResult(
            session_id="work",
            memory_records_removed=0,
            committed=True,
        )

        self.assertEqual(
            tuple(field.name for field in fields(SessionDeleteExecutionResult)),
            ("session_id", "memory_records_removed", "committed"),
        )
        self.assertEqual(result.session_id, "work")
        self.assertEqual(result.memory_records_removed, 0)
        self.assertTrue(result.committed)

    def test_result_is_frozen_and_slotted(self) -> None:
        result = SessionDeleteExecutionResult("work", 0, True)

        self.assertFalse(hasattr(result, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            result.committed = False  # type: ignore[misc]

    def test_same_values_produce_equal_deterministic_results(self) -> None:
        first = SessionDeleteExecutionResult("work", 0, True)
        second = SessionDeleteExecutionResult("work", 0, True)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
