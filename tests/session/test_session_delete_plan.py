"""Unit tests for the pure session-delete plan foundation."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from session.SessionDeletePlan import SessionDeletePlan
from session.SessionDeletePolicy import SessionDeleteDecision, SessionDeleteStatus


class SessionDeletePlanTests(unittest.TestCase):
    def test_creates_an_immutable_plan_for_an_allowed_zero_memory_deletion(
        self,
    ) -> None:
        decision = SessionDeleteDecision(SessionDeleteStatus.ALLOW, "")

        plan = SessionDeletePlan.for_decision("work", (), decision)

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.session_id, "work")
        self.assertEqual(plan.memory_record_ids_to_remove, ())
        self.assertEqual(plan.policy_decision, decision)
        with self.assertRaises(FrozenInstanceError):
            plan.session_id = "other"  # type: ignore[misc]

    def test_does_not_create_an_execution_plan_for_denied_decisions(self) -> None:
        for session_id, reason in (
            ("default", "default session cannot be deleted"),
            ("work", "active session cannot be deleted"),
        ):
            with self.subTest(session_id=session_id):
                decision = SessionDeleteDecision(SessionDeleteStatus.DENY, reason)

                plan = SessionDeletePlan.for_decision(session_id, (), decision)

                self.assertIsNone(plan)

    def test_does_not_create_an_execution_plan_when_memory_policy_is_pending(
        self,
    ) -> None:
        decision = SessionDeleteDecision(
            SessionDeleteStatus.PENDING_MEMORY_POLICY,
            "session has attached memories",
        )

        plan = SessionDeletePlan.for_decision(
            "work",
            ("memory-2", "memory-1"),
            decision,
        )

        self.assertIsNone(plan)

    def test_same_inputs_produce_equal_plans_without_mutating_memory_ids(self) -> None:
        decision = SessionDeleteDecision(SessionDeleteStatus.ALLOW, "")
        memory_ids = ("memory-1",)

        first = SessionDeletePlan.for_decision("work", memory_ids, decision)
        second = SessionDeletePlan.for_decision("work", memory_ids, decision)

        self.assertEqual(first, second)
        self.assertEqual(memory_ids, ("memory-1",))


if __name__ == "__main__":
    unittest.main()
