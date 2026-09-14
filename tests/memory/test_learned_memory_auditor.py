from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from eventbus.EventBus import EventBus
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryAuditor import (
    audit_learned_memories,
    audit_learned_memory_records,
)
from memory.LearnedMemoryAuditReport import MAX_AUDIT_SAMPLES
from memory.LearnedMemoryCorrection import correct_learned_memory_value
from memory.LearnedMemoryStore import append_learned_memory
from memory.MemoryManager import MemoryManager


def memory(kind: str, key: str, value: str) -> LearnedMemory:
    return LearnedMemory(kind=kind, key=key, value=value)  # type: ignore[arg-type]


class LearnedMemoryAuditorTests(unittest.TestCase):
    def test_empty_store_reports_zeroed_metrics(self) -> None:
        report = audit_learned_memories(())

        self.assertEqual(report.total_learned_records, 0)
        self.assertEqual(report.active_memories, 0)
        self.assertEqual(report.superseded_memories, 0)
        self.assertEqual(report.identities, 0)
        self.assertEqual(report.identities_with_multiple_versions, 0)
        self.assertEqual(report.max_versions_for_one_identity, 0)
        self.assertEqual(report.conflicting_history_identities, 0)
        self.assertEqual(report.duplicate_value_candidates, 0)
        self.assertEqual(report.conflicting_history_samples, ())
        self.assertEqual(report.duplicate_value_candidate_samples, ())
        self.assertFalse(report.samples_truncated)
        self.assertEqual(report.superseded_ratio, 0.0)

    def test_active_memories_only_report_no_history(self) -> None:
        report = audit_learned_memories(
            (
                memory("preference", "favorite_planet", "Saturn"),
                memory("project_fact", "active_project", "Hypatia"),
            )
        )

        self.assertEqual(report.total_learned_records, 2)
        self.assertEqual(report.active_memories, 2)
        self.assertEqual(report.superseded_memories, 0)
        self.assertEqual(report.identities, 2)
        self.assertEqual(report.identities_with_multiple_versions, 0)
        self.assertEqual(report.max_versions_for_one_identity, 1)
        self.assertEqual(report.conflicting_history_identities, 0)
        self.assertEqual(report.superseded_ratio, 0.0)

    def test_one_correction_creates_superseded_history(self) -> None:
        report = audit_learned_memories(
            (
                memory("preference", "favorite_planet", "Jupiter"),
                memory("preference", "favorite_planet", "Saturn"),
            )
        )

        self.assertEqual(report.total_learned_records, 2)
        self.assertEqual(report.active_memories, 1)
        self.assertEqual(report.superseded_memories, 1)
        self.assertEqual(report.identities, 1)
        self.assertEqual(report.identities_with_multiple_versions, 1)
        self.assertEqual(report.max_versions_for_one_identity, 2)
        self.assertEqual(report.conflicting_history_identities, 1)
        self.assertEqual(report.superseded_ratio, 0.5)

    def test_multiple_corrections_for_one_identity(self) -> None:
        report = audit_learned_memories(
            (
                memory("preference", "favorite_planet", "Mars"),
                memory("preference", "favorite_planet", "Jupiter"),
                memory("preference", "favorite_planet", "Saturn"),
                memory("preference", "favorite_planet", "Neptune"),
            )
        )

        self.assertEqual(report.total_learned_records, 4)
        self.assertEqual(report.active_memories, 1)
        self.assertEqual(report.superseded_memories, 3)
        self.assertEqual(report.max_versions_for_one_identity, 4)
        self.assertEqual(report.conflicting_history_identities, 1)
        self.assertEqual(
            report.conflicting_history_samples[0].key,
            "favorite_planet",
        )
        self.assertEqual(report.conflicting_history_samples[0].versions, 4)

    def test_repeated_identical_value_is_history_without_conflict(self) -> None:
        report = audit_learned_memories(
            (
                memory("preference", "favorite_planet", "Saturn"),
                memory("preference", "favorite_planet", "Saturn"),
            )
        )

        self.assertEqual(report.identities_with_multiple_versions, 1)
        self.assertEqual(report.max_versions_for_one_identity, 2)
        self.assertEqual(report.conflicting_history_identities, 0)

    def test_same_value_under_different_keys_is_only_a_candidate(self) -> None:
        report = audit_learned_memories(
            (
                memory("preference", "favorite_planet", "Saturn"),
                memory("preference", "preferred_planet", "Saturn"),
            )
        )

        self.assertEqual(report.active_memories, 2)
        self.assertEqual(report.duplicate_value_candidates, 1)
        candidate = report.duplicate_value_candidate_samples[0]
        self.assertEqual(candidate.first_key, "favorite_planet")
        self.assertEqual(candidate.second_key, "preferred_planet")
        self.assertEqual(report.conflicting_history_identities, 0)
        self.assertEqual(report.superseded_memories, 0)

    def test_superseded_value_does_not_create_a_duplicate_candidate(self) -> None:
        report = audit_learned_memories(
            (
                memory("preference", "preferred_planet", "Saturn"),
                memory("preference", "preferred_planet", "Neptune"),
                memory("preference", "favorite_planet", "Saturn"),
            )
        )

        self.assertEqual(report.duplicate_value_candidates, 0)

    def test_samples_are_bounded_and_flagged_when_truncated(self) -> None:
        memories = []
        for index in range(MAX_AUDIT_SAMPLES + 4):
            memories.append(memory("preference", f"key_{index}", "old"))
            memories.append(memory("preference", f"key_{index}", "new"))

        report = audit_learned_memories(tuple(memories))

        self.assertEqual(
            report.conflicting_history_identities,
            MAX_AUDIT_SAMPLES + 4,
        )
        self.assertEqual(len(report.conflicting_history_samples), MAX_AUDIT_SAMPLES)
        self.assertLessEqual(
            len(report.duplicate_value_candidate_samples),
            MAX_AUDIT_SAMPLES,
        )
        self.assertTrue(report.samples_truncated)

    def test_audit_is_deterministic_across_repeated_calls(self) -> None:
        memories = (
            memory("preference", "favorite_planet", "Jupiter"),
            memory("preference", "favorite_planet", "Saturn"),
            memory("preference", "preferred_planet", "Saturn"),
            memory("goal", "current_goal", "Saturn"),
        )

        first = audit_learned_memories(memories)
        second = audit_learned_memories(memories)

        self.assertEqual(first, second)
        self.assertEqual(
            first.duplicate_value_candidate_samples,
            second.duplicate_value_candidate_samples,
        )

    def test_audit_does_not_mutate_its_input(self) -> None:
        memories = (
            memory("preference", "favorite_planet", "Jupiter"),
            memory("preference", "favorite_planet", "Saturn"),
        )
        snapshot = tuple(memories)

        audit_learned_memories(memories)

        self.assertEqual(memories, snapshot)


class LearnedMemoryAuditorRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)

    def test_ordinary_conversation_records_are_ignored(self) -> None:
        self.memory_manager.add(
            "User: hello\nHypatia: hi",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        append_learned_memory(
            self.memory_manager,
            memory("preference", "favorite_planet", "Saturn"),
        )

        report = audit_learned_memory_records(tuple(self.memory_manager.all()))

        self.assertEqual(report.total_learned_records, 1)
        self.assertEqual(report.active_memories, 1)

    def test_audit_performs_no_write_and_emits_no_event(self) -> None:
        append_learned_memory(
            self.memory_manager,
            memory("preference", "favorite_planet", "Jupiter"),
        )
        correct_learned_memory_value(
            self.memory_manager,
            kind="preference",
            key="favorite_planet",
            value="Saturn",
        )
        before = [record.memory_id for record in self.memory_manager.all()]
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        report = audit_learned_memory_records(tuple(self.memory_manager.all()))

        self.assertEqual(
            [record.memory_id for record in self.memory_manager.all()],
            before,
        )
        self.assertEqual(events, [])
        self.assertEqual(report.superseded_memories, 1)
        self.assertEqual(report.active_memories, 1)


if __name__ == "__main__":
    unittest.main()
