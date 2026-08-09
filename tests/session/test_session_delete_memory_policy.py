"""Unit tests for the pure session-delete memory policy."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from session.SessionDeleteMemoryPolicy import (
    SessionDeleteMemoryAction,
    SessionDeleteMemoryDecision,
    SessionDeleteMemoryPolicy,
)


class SessionDeleteMemoryPolicyTests(unittest.TestCase):
    def test_empty_memory_ids_produce_a_none_decision(self) -> None:
        decision = SessionDeleteMemoryPolicy.evaluate(())

        self.assertEqual(
            decision,
            SessionDeleteMemoryDecision(
                SessionDeleteMemoryAction.NONE,
                (),
                None,
            ),
        )

    def test_attached_memory_ids_produce_an_ordered_block_decision(self) -> None:
        memory_ids = ("memory-2", "memory-1")

        decision = SessionDeleteMemoryPolicy.evaluate(memory_ids)

        self.assertEqual(decision.action, SessionDeleteMemoryAction.BLOCK)
        self.assertEqual(decision.memory_record_ids, memory_ids)
        self.assertEqual(decision.reason, "session has attached memories")
        self.assertEqual(memory_ids, ("memory-2", "memory-1"))

    def test_decisions_are_frozen_slotted_and_deterministic(self) -> None:
        first = SessionDeleteMemoryPolicy.evaluate(("memory-1",))
        second = SessionDeleteMemoryPolicy.evaluate(("memory-1",))

        self.assertEqual(first, second)
        self.assertEqual(
            tuple(SessionDeleteMemoryDecision.__dataclass_fields__),
            ("action", "memory_record_ids", "reason"),
        )
        with self.assertRaises(FrozenInstanceError):
            first.reason = None  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
