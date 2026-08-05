"""Unit tests for pure session rename candidate construction."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from memory.MemoryRecord import MemoryRecord
from session.SessionRecord import SessionRecord
from session.SessionRegistrySnapshot import SessionRegistrySnapshot
from session.SessionRenameCandidateBuilder import SessionRenameCandidateBuilder
from session.SessionRenamePlan import SessionRenamePlan


class SessionRenameCandidateModelTests(unittest.TestCase):
    def test_candidate_is_frozen_and_uses_tuple_memory_records(self) -> None:
        candidate = self._builder().build(
            plan=self._plan(),
            session_snapshot=self._snapshot(),
            memory_records=(),
        )

        self.assertIsInstance(candidate.memory_records, tuple)
        with self.assertRaises(FrozenInstanceError):
            candidate.plan = self._plan()  # type: ignore[misc]

    @staticmethod
    def _builder() -> SessionRenameCandidateBuilder:
        return SessionRenameCandidateBuilder()

    @staticmethod
    def _plan() -> SessionRenamePlan:
        return SessionRenamePlan(
            "work", "renamed", ("default", "renamed"), "renamed", ()
        )

    @staticmethod
    def _snapshot() -> SessionRegistrySnapshot:
        moment = datetime(2026, 1, 1, tzinfo=UTC)
        return SessionRegistrySnapshot(
            "work", (SessionRecord("default", moment), SessionRecord("work", moment))
        )


class SessionRenameCandidateBuilderSuccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = SessionRenameCandidateBuilder()
        self.early = datetime(2026, 1, 1, tzinfo=UTC)
        self.late = datetime(2026, 1, 2, tzinfo=UTC)

    def test_builds_ordered_session_and_memory_candidates_without_mutating_inputs(
        self,
    ) -> None:
        snapshot = self._snapshot(active="work")
        selected = self._record("selected", "work", kind="conversation")
        unchanged = self._record("unchanged", "research", kind="plan")
        records = [unchanged, selected]
        plan = self._plan(memory_ids=("selected",))

        candidate = self.builder.build(
            plan=plan, session_snapshot=snapshot, memory_records=records
        )

        self.assertEqual(
            tuple(item.session_id for item in candidate.session_snapshot.sessions),
            ("default", "renamed work", "research"),
        )
        self.assertEqual(candidate.session_snapshot.active_session_id, "renamed work")
        self.assertEqual(candidate.session_snapshot.sessions[1].created_at, self.late)
        self.assertEqual(candidate.memory_records[0], unchanged)
        self.assertIs(candidate.memory_records[0], unchanged)
        self.assertEqual(
            candidate.memory_records[1].metadata,
            {"session_id": "renamed work", "kind": "conversation"},
        )
        self.assertIsNot(candidate.memory_records[1], selected)
        self.assertIsNot(candidate.memory_records[1].metadata, selected.metadata)
        self.assertEqual(candidate.memory_records[1].memory_id, selected.memory_id)
        self.assertEqual(candidate.memory_records[1].content, selected.content)
        self.assertEqual(candidate.memory_records[1].tags, selected.tags)
        self.assertEqual(candidate.memory_records[1].created_at, selected.created_at)
        self.assertEqual(candidate.memory_records[1].updated_at, selected.updated_at)
        self.assertEqual(candidate.memory_records[1].expires_at, selected.expires_at)
        self.assertEqual(records, [unchanged, selected])
        self.assertEqual(
            selected.metadata, {"session_id": "work", "kind": "conversation"}
        )
        self.assertEqual(snapshot.sessions[1].session_id, "work")

    def test_keeps_an_inactive_active_session_and_ignores_memory_tags(self) -> None:
        record = self._record("anything", "work", kind="internal", tags=frozenset())

        candidate = self.builder.build(
            plan=self._plan(active="research", memory_ids=("anything",)),
            session_snapshot=self._snapshot(active="research"),
            memory_records=(record,),
        )

        self.assertEqual(candidate.session_snapshot.active_session_id, "research")
        self.assertEqual(
            candidate.memory_records[0].metadata["session_id"], "renamed work"
        )

    def test_zero_memory_migration_and_case_only_target_are_valid(self) -> None:
        candidate = self.builder.build(
            plan=SessionRenamePlan(
                "work", "Work", ("default", "Work", "research"), "research", ()
            ),
            session_snapshot=self._snapshot(active="research"),
            memory_records=(),
        )

        self.assertEqual(candidate.memory_records, ())
        self.assertEqual(candidate.session_snapshot.sessions[1].session_id, "Work")

    def _snapshot(self, *, active: str) -> SessionRegistrySnapshot:
        return SessionRegistrySnapshot(
            active,
            (
                SessionRecord("default", self.early),
                SessionRecord("work", self.late),
                SessionRecord("research", self.early),
            ),
        )

    @staticmethod
    def _plan(
        *, active: str = "work", memory_ids: tuple[str, ...] = ()
    ) -> SessionRenamePlan:
        return SessionRenamePlan(
            "work",
            "renamed work",
            ("default", "renamed work", "research"),
            active if active != "work" else "renamed work",
            memory_ids,
        )

    def _record(
        self,
        memory_id: str,
        session_id: str,
        *,
        kind: str,
        tags: frozenset[str] | None = None,
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id,
            "content",
            {"session_id": session_id, "kind": kind},
            tags or frozenset({"brain", "conversation"}),
            self.early,
            self.late,
            self.late,
        )


class SessionRenameCandidateBuilderValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = SessionRenameCandidateBuilder()
        self.moment = datetime(2026, 1, 1, tzinfo=UTC)

    def test_session_validation_is_deterministic_and_precedes_memory_validation(
        self,
    ) -> None:
        plan = self._plan(memory_ids=("unknown",))
        snapshot = SessionRegistrySnapshot(
            "default", (SessionRecord("default", self.moment),)
        )

        self._assert_error(
            "Session rename plan source is missing from the session snapshot: work",
            plan,
            snapshot,
            (),
        )

    def test_rejects_duplicate_source_order_mismatch_and_active_mismatch(self) -> None:
        duplicate = SessionRegistrySnapshot(
            "work",
            (SessionRecord("work", self.moment), SessionRecord("work", self.moment)),
        )
        self._assert_error(
            "Session rename snapshot contains duplicate source session: work",
            self._plan(),
            duplicate,
            (),
        )

        correct = self._snapshot()
        wrong_order = SessionRenamePlan(
            "work", "renamed", ("renamed", "default"), "renamed", ()
        )
        self._assert_error(
            "Session rename plan session order does not match the session snapshot.",
            wrong_order,
            correct,
            (),
        )

        wrong_active = SessionRenamePlan(
            "work", "renamed", ("default", "renamed"), "unknown", ()
        )
        self._assert_error(
            "Session rename plan active session does not match the session snapshot.",
            wrong_active,
            correct,
            (),
        )

    def test_rejects_duplicate_and_unknown_memory_ids_in_required_order(self) -> None:
        snapshot = self._snapshot()
        record = MemoryRecord("known", "content")
        duplicate_plan = self._plan(memory_ids=("unknown", "unknown"))
        self._assert_error(
            "Session rename plan contains duplicate memory record ID: unknown",
            duplicate_plan,
            snapshot,
            (record,),
        )

        duplicate_snapshot = self._plan(memory_ids=("unknown",))
        duplicated = (record, MemoryRecord("known", "another"))
        self._assert_error(
            "Session rename snapshot contains duplicate memory record ID: known",
            duplicate_snapshot,
            snapshot,
            duplicated,
        )

        unknown = self._plan(memory_ids=("missing-first", "missing-second"))
        self._assert_error(
            "Session rename plan references unknown memory record: missing-first",
            unknown,
            snapshot,
            (record,),
        )

    def _assert_error(
        self,
        message: str,
        plan: SessionRenamePlan,
        snapshot: SessionRegistrySnapshot,
        records: tuple[MemoryRecord, ...],
    ) -> None:
        with self.assertRaisesRegex(SessionError, f"^{message}$"):
            self.builder.build(
                plan=plan, session_snapshot=snapshot, memory_records=records
            )

    def _snapshot(self) -> SessionRegistrySnapshot:
        return SessionRegistrySnapshot(
            "work",
            (SessionRecord("default", self.moment), SessionRecord("work", self.moment)),
        )

    @staticmethod
    def _plan(*, memory_ids: tuple[str, ...] = ()) -> SessionRenamePlan:
        return SessionRenamePlan(
            "work", "renamed", ("default", "renamed"), "renamed", memory_ids
        )


if __name__ == "__main__":
    unittest.main()
