"""Tests for the pure session-deletion decision policy."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from session.SessionDeletePolicy import (
    SessionDeleteDecision,
    SessionDeletePolicy,
    SessionDeleteStatus,
)


class SessionDeletePolicyTests(unittest.TestCase):
    def test_default_is_denied_before_active_status(self) -> None:
        decision = SessionDeletePolicy.evaluate("default", "default", ())

        self.assertEqual(decision.status, SessionDeleteStatus.DENY)
        self.assertEqual(decision.reason, "default session cannot be deleted")

    def test_active_session_is_denied(self) -> None:
        decision = SessionDeletePolicy.evaluate("work", "work", ())

        self.assertEqual(decision.status, SessionDeleteStatus.DENY)
        self.assertEqual(decision.reason, "active session cannot be deleted")

    def test_inactive_session_with_memories_is_pending_regardless_of_id_order(
        self,
    ) -> None:
        first = SessionDeletePolicy.evaluate("work", "other", ("memory-2", "memory-1"))
        second = SessionDeletePolicy.evaluate("work", "other", ("memory-1", "memory-2"))

        self.assertEqual(first.status, SessionDeleteStatus.PENDING_MEMORY_POLICY)
        self.assertEqual(first.reason, "session has attached memories")
        self.assertEqual(second, first)

    def test_inactive_session_without_memories_is_allowed(self) -> None:
        decision = SessionDeletePolicy.evaluate("work", "other", ())

        self.assertEqual(decision.status, SessionDeleteStatus.ALLOW)
        self.assertEqual(decision.reason, "")

    def test_decision_is_frozen_and_evaluation_is_deterministic(self) -> None:
        decision = SessionDeletePolicy.evaluate("work", "other", ())

        with self.assertRaises(FrozenInstanceError):
            decision.reason = "changed"  # type: ignore[misc]
        self.assertEqual(decision, SessionDeletePolicy.evaluate("work", "other", ()))
        self.assertIsInstance(decision, SessionDeleteDecision)


if __name__ == "__main__":
    unittest.main()
