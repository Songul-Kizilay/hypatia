"""Unit tests for pure session-delete transaction preparation."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from session.SessionDeletePlan import SessionDeletePlan
from session.SessionDeletePolicy import SessionDeleteDecision, SessionDeleteStatus
from session.SessionDeleteTransactionService import (
    SessionDeleteTransactionContext,
    SessionDeleteTransactionService,
)
from session.SessionManager import SessionManager


class SessionDeleteTransactionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SessionDeleteTransactionService()

    def test_prepare_returns_an_immutable_context_for_an_allowed_plan(self) -> None:
        plan = self._allowed_plan()

        context = self.service.prepare(plan)

        self.assertEqual(
            context,
            SessionDeleteTransactionContext("work", ()),
        )
        with self.assertRaises(FrozenInstanceError):
            context.session_id = "other"  # type: ignore[misc]

    def test_prepare_is_deterministic_and_does_not_mutate_the_plan(self) -> None:
        plan = self._allowed_plan()

        first = self.service.prepare(plan)
        second = self.service.prepare(plan)

        self.assertEqual(first, second)
        self.assertEqual(plan.session_id, "work")
        self.assertEqual(plan.memory_record_ids_to_remove, ())
        self.assertEqual(plan.policy_decision.status, SessionDeleteStatus.ALLOW)

    def test_prepare_does_not_change_runtime_state_or_emit_events(self) -> None:
        event_bus = EventBus()
        sessions = SessionManager(event_bus)
        memories = MemoryManager(event_bus=event_bus)
        sessions.create("work")
        memories.add("Work", metadata={"session_id": "work"})
        sessions_before = sessions.snapshot()
        memories_before = memories.snapshot()
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        context = self.service.prepare(self._allowed_plan())

        self.assertEqual(context.memory_record_ids, ())
        self.assertEqual(sessions.snapshot(), sessions_before)
        self.assertEqual(memories.snapshot(), memories_before)
        self.assertEqual(events, [])

    def test_prepare_rejects_directly_constructed_denied_and_pending_plans(
        self,
    ) -> None:
        for status, reason in (
            (SessionDeleteStatus.DENY, "active session cannot be deleted"),
            (
                SessionDeleteStatus.PENDING_MEMORY_POLICY,
                "session has attached memories",
            ),
        ):
            with self.subTest(status=status):
                plan = SessionDeletePlan(
                    "work",
                    ("memory-1",),
                    SessionDeleteDecision(status, reason),
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "^Session delete plan must be allowed\\.$",
                ):
                    self.service.prepare(plan)

    def test_prepare_rejects_an_allowed_plan_with_memory_records(self) -> None:
        plan = SessionDeletePlan(
            "work",
            ("memory-1",),
            SessionDeleteDecision(SessionDeleteStatus.ALLOW, ""),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^Allowed session delete plan must not contain memory records\\.$",
        ):
            self.service.prepare(plan)

    @staticmethod
    def _allowed_plan() -> SessionDeletePlan:
        plan = SessionDeletePlan.for_decision(
            "work",
            (),
            SessionDeleteDecision(SessionDeleteStatus.ALLOW, ""),
        )
        assert plan is not None
        return plan


if __name__ == "__main__":
    unittest.main()
