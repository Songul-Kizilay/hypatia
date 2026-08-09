"""Unit tests for pure session-delete transaction preparation."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from eventbus.EventBus import EventBus
from memory.MemoryManager import MemoryManager
from session.SessionDeletePlan import SessionDeletePlan
from session.SessionDeletePolicy import SessionDeleteDecision, SessionDeleteStatus
from session.SessionDeleteTransactionService import (
    SessionDeleteTransactionContext,
    SessionDeleteTransactionService,
)
from session.SessionManager import SessionManager
from session.SessionRegistrySnapshot import SessionRegistrySnapshot


class RecordingSessionStore:
    """Test persistence boundary that observes save ordering without mutation."""

    def __init__(self, *, fail_on_save: bool = False) -> None:
        self.fail_on_save = fail_on_save
        self.manager: SessionManager | None = None
        self.saved: list[SessionRegistrySnapshot] = []
        self.manager_snapshots_when_saved: list[SessionRegistrySnapshot] = []

    def load(self) -> SessionRegistrySnapshot | None:
        return None

    def save(self, snapshot: SessionRegistrySnapshot) -> None:
        if self.manager is not None:
            self.manager_snapshots_when_saved.append(self.manager.snapshot())
        if self.fail_on_save:
            raise RuntimeError("session store unavailable")
        self.saved.append(snapshot)


class SnapshotMutatingSessionManager(SessionManager):
    """Simulate a registry write after policy evaluation and before atomic apply."""

    def __init__(self, event_bus: EventBus, store: RecordingSessionStore) -> None:
        super().__init__(event_bus, store)
        self._mutate_before_next_atomic_apply = False

    def mutate_before_next_atomic_apply(self) -> None:
        """Schedule one independent registry mutation before the atomic apply."""
        self._mutate_before_next_atomic_apply = True

    def apply_snapshot_if_current(
        self,
        expected: SessionRegistrySnapshot,
        candidate: SessionRegistrySnapshot,
    ) -> None:
        """Apply only after a simulated post-policy registry write."""
        if self._mutate_before_next_atomic_apply:
            self._mutate_before_next_atomic_apply = False
            self.create("research")
        super().apply_snapshot_if_current(expected, candidate)


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

    def test_build_candidate_removes_only_the_target_without_mutating_inputs(
        self,
    ) -> None:
        event_bus = EventBus()
        sessions = SessionManager(event_bus)
        sessions.create("work")
        sessions.create("research")
        snapshot = sessions.snapshot()
        context = self.service.prepare(self._allowed_plan())
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        candidate = self.service.build_candidate(context, snapshot)

        self.assertEqual(
            tuple(session.session_id for session in candidate.sessions),
            ("default", "research"),
        )
        self.assertEqual(candidate.active_session_id, "default")
        self.assertEqual(sessions.snapshot(), snapshot)
        self.assertEqual(context, SessionDeleteTransactionContext("work", ()))
        self.assertEqual(events, [])

    def test_build_candidate_is_deterministic_for_the_same_snapshot_and_context(
        self,
    ) -> None:
        sessions = SessionManager()
        sessions.create("work")
        snapshot = sessions.snapshot()
        context = self.service.prepare(self._allowed_plan())

        first = self.service.build_candidate(context, snapshot)
        second = self.service.build_candidate(context, snapshot)

        self.assertEqual(first, second)
        self.assertEqual(snapshot, sessions.snapshot())

    def test_build_candidate_rejects_a_stale_context_with_an_exact_error(self) -> None:
        context = self.service.prepare(self._allowed_plan())
        snapshot = SessionManager().snapshot()

        with self.assertRaisesRegex(
            ValueError,
            "^Session delete target is not present in snapshot\\.$",
        ):
            self.service.build_candidate(context, snapshot)

    def test_execute_persists_before_committing_a_zero_memory_candidate(self) -> None:
        event_bus = EventBus()
        store = RecordingSessionStore()
        sessions = SessionManager(event_bus, store)
        store.manager = sessions
        sessions.create("work")
        original = sessions.snapshot()
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        result = self.service.execute(
            SessionDeleteTransactionContext("work", ()),
            sessions,
        )

        expected_candidate = self.service.build_candidate(
            SessionDeleteTransactionContext("work", ()),
            original,
        )
        self.assertEqual(store.saved[-1], expected_candidate)
        self.assertEqual(store.manager_snapshots_when_saved[-1], original)
        self.assertEqual(sessions.snapshot(), expected_candidate)
        self.assertEqual(result.session_id, "work")
        self.assertEqual(result.memory_records_removed, 0)
        self.assertTrue(result.committed)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "session.deleted")
        self.assertEqual(
            events[0].payload,
            {
                "session_id": "work",
                "created_at": original.sessions[1].created_at.isoformat(),
            },
        )
        self.assertEqual(events[0].source, "session_manager")

    def test_commit_persists_and_returns_the_original_record_without_events(
        self,
    ) -> None:
        event_bus = EventBus()
        store = RecordingSessionStore()
        sessions = SessionManager(event_bus, store)
        store.manager = sessions
        sessions.create("work")
        original = sessions.snapshot()
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        result, deleted_session = self.service.commit(
            SessionDeleteTransactionContext("work", ()),
            sessions,
        )

        self.assertEqual(deleted_session, original.sessions[1])
        self.assertEqual(result.session_id, "work")
        self.assertEqual(result.memory_records_removed, 0)
        self.assertTrue(result.committed)
        self.assertEqual(
            tuple(session.session_id for session in sessions.list()),
            ("default",),
        )
        self.assertEqual(events, [])

    def test_commit_revalidates_and_rejects_the_default_target(self) -> None:
        event_bus = EventBus()
        store = RecordingSessionStore()
        sessions = SessionManager(event_bus, store)
        store.manager = sessions
        original = sessions.snapshot()
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        with self.assertRaisesRegex(
            ValueError,
            "^Session delete transaction is no longer allowed: "
            "default session cannot be deleted\\.$",
        ):
            self.service.commit(
                SessionDeleteTransactionContext("default", ()),
                sessions,
            )

        self.assertEqual(sessions.snapshot(), original)
        self.assertEqual(store.saved, [])
        self.assertEqual(events, [])

    def test_commit_revalidates_and_rejects_a_newly_active_target(self) -> None:
        event_bus = EventBus()
        store = RecordingSessionStore()
        sessions = SessionManager(event_bus, store)
        store.manager = sessions
        sessions.create("work")
        context = self.service.prepare(self._allowed_plan())
        sessions.set_active("work")
        original = sessions.snapshot()
        saves_before = len(store.saved)
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        with self.assertRaisesRegex(
            ValueError,
            "^Session delete transaction is no longer allowed: "
            "active session cannot be deleted\\.$",
        ):
            self.service.commit(context, sessions)

        self.assertEqual(sessions.snapshot(), original)
        self.assertEqual(len(store.saved), saves_before)
        self.assertEqual(events, [])

    def test_execute_keeps_ram_unchanged_when_persistence_fails(self) -> None:
        store = RecordingSessionStore()
        event_bus = EventBus()
        sessions = SessionManager(event_bus, store)
        store.manager = sessions
        sessions.create("work")
        original = sessions.snapshot()
        store.fail_on_save = True
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        with self.assertRaisesRegex(RuntimeError, "^session store unavailable$"):
            self.service.commit(SessionDeleteTransactionContext("work", ()), sessions)

        self.assertEqual(sessions.snapshot(), original)
        self.assertEqual(events, [])

    def test_execute_rejects_an_intervening_registry_mutation_without_delete_event(
        self,
    ) -> None:
        event_bus = EventBus()
        store = RecordingSessionStore()
        sessions = SnapshotMutatingSessionManager(event_bus, store)
        store.manager = sessions
        sessions.create("work")
        events: list[object] = []
        event_bus.subscribe("*", events.append)
        saves_before = len(store.saved)
        sessions.mutate_before_next_atomic_apply()

        with self.assertRaisesRegex(
            SessionError,
            "^Session snapshot changed\\.$",
        ):
            self.service.commit(SessionDeleteTransactionContext("work", ()), sessions)

        self.assertEqual(
            tuple(session.session_id for session in sessions.list()),
            ("default", "work", "research"),
        )
        self.assertEqual(len(store.saved), saves_before + 1)
        self.assertEqual([event.name for event in events], ["session.created"])

    def test_execute_rejects_stale_and_memory_contexts_without_mutation(self) -> None:
        store = RecordingSessionStore()
        event_bus = EventBus()
        sessions = SessionManager(event_bus, store)
        store.manager = sessions
        sessions.create("work")
        original = sessions.snapshot()
        events: list[object] = []
        event_bus.subscribe("*", events.append)

        for context, message in (
            (
                SessionDeleteTransactionContext("missing", ()),
                "^Session delete target is not present in snapshot\\.$",
            ),
            (
                SessionDeleteTransactionContext("work", ("memory-1",)),
                "^Session delete transaction must not contain memory records\\.$",
            ),
        ):
            with self.subTest(context=context):
                saves_before = len(store.saved)

                with self.assertRaisesRegex(ValueError, message):
                    self.service.execute(context, sessions)

                self.assertEqual(sessions.snapshot(), original)
                self.assertEqual(len(store.saved), saves_before)
                self.assertEqual(events, [])

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
