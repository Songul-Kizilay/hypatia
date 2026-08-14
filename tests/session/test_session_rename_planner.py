"""Unit tests for pure session rename planning."""

from __future__ import annotations

import sys
import unittest
from collections.abc import Mapping
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import SessionError
from memory.MemoryRecord import MemoryRecord
from session.SessionRenamePlanner import SessionRenamePlanner


class SessionRenamePlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = SessionRenamePlanner()
        self.session_ids = ("default", "work", "research")

    def test_creates_a_plan_without_mutating_its_inputs(self) -> None:
        records = [
            self._record("conversation", {"session_id": "work"}),
            self._record("knowledge", {"session_id": "work"}),
            self._record("other", {"session_id": "research"}),
        ]

        plan = self.planner.create_plan(
            registered_session_ids=self.session_ids,
            active_session_id="work",
            memory_records=records,
            source_session_id="work",
            target_session_id="bug bounty",
        )

        self.assertEqual(plan.source_session_id, "work")
        self.assertEqual(plan.target_session_id, "bug bounty")
        self.assertEqual(
            plan.updated_session_ids, ("default", "bug bounty", "research")
        )
        self.assertEqual(plan.updated_active_session_id, "bug bounty")
        self.assertEqual(
            plan.memory_record_ids_to_update, ("conversation", "knowledge")
        )
        self.assertEqual(self.session_ids, ("default", "work", "research"))
        self.assertEqual(records[0].metadata["session_id"], "work")

    def test_preserves_active_session_when_source_is_inactive(self) -> None:
        plan = self._plan(source="work", target="bug bounty", active="research")

        self.assertEqual(plan.updated_active_session_id, "research")

    def test_normalizes_outer_whitespace_and_preserves_inner_whitespace(self) -> None:
        plan = self._plan(source="  work  ", target="  bug bounty  ")

        self.assertEqual(plan.source_session_id, "work")
        self.assertEqual(plan.target_session_id, "bug bounty")

    def test_accepts_a_case_only_rename(self) -> None:
        plan = self._plan(source="work", target="Work")

        self.assertEqual(plan.updated_session_ids, ("default", "Work", "research"))

    def test_selects_only_explicit_exact_string_session_metadata_in_input_order(
        self,
    ) -> None:
        records = [
            self._record("first", {"session_id": "work"}),
            self._record("missing", {}),
            self._record("none", {"session_id": None}),
            self._record("number", {"session_id": 42}),
            self._record("case", {"session_id": "Work"}),
            self._record("space", {"session_id": "work "}),
            self._record("second", {"session_id": "work"}),
        ]

        plan = self.planner.create_plan(
            registered_session_ids=self.session_ids,
            active_session_id="work",
            memory_records=records,
            source_session_id="work",
            target_session_id="renamed",
        )

        self.assertEqual(plan.memory_record_ids_to_update, ("first", "second"))

    def test_does_not_mutate_memory_metadata_or_the_memory_collection(self) -> None:
        metadata = {"session_id": "work", "kind": "knowledge"}
        records = [self._record("record", metadata)]
        original_records = list(records)
        original_metadata = dict(metadata)

        self.planner.create_plan(
            registered_session_ids=self.session_ids,
            active_session_id="work",
            memory_records=records,
            source_session_id="work",
            target_session_id="renamed",
        )

        self.assertEqual(records, original_records)
        self.assertEqual(metadata, original_metadata)

    def test_rejects_invalid_rename_requests(self) -> None:
        cases = (
            ("   ", "target", "Session source ID cannot be empty."),
            ("work", "   ", "Session target ID cannot be empty."),
            ("unknown", "target", "Unknown session: unknown"),
            ("work", "research", "Session already exists: research"),
            ("work", "work", "Session source and target must be different."),
            ("default", "renamed", "Default session cannot be renamed."),
        )

        for source, target, message in cases:
            with self.subTest(source=source, target=target):
                with self.assertRaisesRegex(SessionError, f"^{message}$"):
                    self._plan(source=source, target=target)

    def test_unknown_source_takes_precedence_over_default_protection(self) -> None:
        with self.assertRaisesRegex(SessionError, "^Unknown session: default$"):
            self.planner.create_plan(
                registered_session_ids=("work",),
                active_session_id="work",
                memory_records=(),
                source_session_id="default",
                target_session_id="renamed",
            )

    def test_rejects_non_string_source_and_target(self) -> None:
        for source, target, message in (
            (123, "target", "Session source ID must be a string."),
            ("work", 123, "Session target ID must be a string."),
        ):
            with self.subTest(source=source, target=target):
                with self.assertRaisesRegex(SessionError, f"^{message}$"):
                    self._plan(source=source, target=target)  # type: ignore[arg-type]

    def test_validation_checks_both_types_before_empty_values(self) -> None:
        with self.assertRaisesRegex(
            SessionError, "^Session target ID must be a string.$"
        ):
            self._plan(source="   ", target=123)  # type: ignore[arg-type]

        with self.assertRaisesRegex(
            SessionError, "^Session source ID cannot be empty.$"
        ):
            self._plan(source="   ", target="   ")

        with self.assertRaisesRegex(
            SessionError, "^Session target ID cannot be empty.$"
        ):
            self._plan(source="work", target="   ")

    def test_default_protection_takes_precedence_over_same_id_validation(self) -> None:
        with self.assertRaisesRegex(
            SessionError, "^Default session cannot be renamed.$"
        ):
            self._plan(source="default", target="default")

    def _plan(
        self,
        *,
        source: str,
        target: str,
        active: str = "work",
    ):
        return self.planner.create_plan(
            registered_session_ids=self.session_ids,
            active_session_id=active,
            memory_records=(),
            source_session_id=source,
            target_session_id=target,
        )

    @staticmethod
    def _record(memory_id: str, metadata: Mapping[str, object]) -> MemoryRecord:
        return MemoryRecord(
            memory_id=memory_id,
            content=memory_id,
            metadata=metadata,
            tags=frozenset(),
        )


if __name__ == "__main__":
    unittest.main()
