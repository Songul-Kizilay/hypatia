"""Unit tests for the in-memory MemoryManager."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from eventbus.EventBus import EventBus
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord


class RecordingMemoryStore:
    """In-memory persistence fake that records every saved snapshot."""

    def __init__(self, records: list[MemoryRecord] | None = None) -> None:
        self.records = list(records or [])
        self.saved_snapshots: list[list[MemoryRecord]] = []
        self.save_completed = False

    def load(self) -> list[MemoryRecord]:
        return list(self.records)

    def save(self, records: list[MemoryRecord]) -> None:
        self.save_completed = True
        self.saved_snapshots.append(records)
        self.records = list(records)


class FailingMemoryStore(RecordingMemoryStore):
    """Persistence fake that can fail independently during reads or writes."""

    def __init__(self, records: list[MemoryRecord] | None = None) -> None:
        super().__init__(records)
        self.fail_load = False
        self.fail_save = False

    def load(self) -> list[MemoryRecord]:
        if self.fail_load:
            raise MemoryError("Memory load failed.")
        return super().load()

    def save(self, records: list[MemoryRecord]) -> None:
        if self.fail_save:
            raise MemoryError("Memory save failed.")
        super().save(records)


class MemoryManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = EventBus()
        self.memory = MemoryManager(self.bus)

    def test_add_creates_retrievable_record(self) -> None:
        record = self.memory.add("A saved fact")

        self.assertEqual(self.memory.get(record.memory_id), record)
        self.assertEqual(self.memory.count(), 1)

    def test_add_rejects_blank_content(self) -> None:
        with self.assertRaises(MemoryError):
            self.memory.add("  ")

    def test_get_returns_none_for_missing_record(self) -> None:
        self.assertIsNone(self.memory.get("missing"))

    def test_update_replaces_selected_fields(self) -> None:
        record = self.memory.add("Old", tags={"draft"})

        updated = self.memory.update(record.memory_id, content="New", tags={"final"})

        self.assertIsNotNone(updated)
        self.assertEqual(updated.content, "New")
        self.assertEqual(updated.tags, frozenset({"final"}))
        self.assertGreaterEqual(updated.updated_at, updated.created_at)

    def test_update_returns_none_for_missing_record(self) -> None:
        self.assertIsNone(self.memory.update("missing", content="New"))

    def test_delete_reports_existence(self) -> None:
        record = self.memory.add("Delete me")

        self.assertTrue(self.memory.delete(record.memory_id))
        self.assertFalse(self.memory.delete(record.memory_id))

    def test_search_filters_by_text_and_tags(self) -> None:
        self.memory.add("Python planner", tags={"code", "planner"})
        self.memory.add("Python memory", tags={"code", "memory"})

        matches = self.memory.search("python", tags={"planner"})

        self.assertEqual([record.content for record in matches], ["Python planner"])

    def test_expired_record_is_not_returned(self) -> None:
        expired_at = datetime.now(UTC) - timedelta(seconds=1)
        record = self.memory.add("Temporary", expires_at=expired_at)

        self.assertIsNone(self.memory.get(record.memory_id))
        self.assertEqual(self.memory.count(), 0)

    def test_clear_removes_records_and_reports_count(self) -> None:
        self.memory.add("One")
        self.memory.add("Two")

        self.assertEqual(self.memory.clear(), 2)
        self.assertEqual(self.memory.count(), 0)

    def test_memory_manager_keeps_ram_only_behavior_without_a_store(self) -> None:
        memory = MemoryManager()

        record = memory.add("RAM only")

        self.assertEqual(memory.get(record.memory_id), record)

    def test_load_replaces_existing_memory_with_store_snapshot(self) -> None:
        stored_record = MemoryRecord(memory_id="stored", content="Stored")
        store = RecordingMemoryStore([stored_record])
        memory = MemoryManager(store=store)
        memory.add("Existing")
        store.records = [stored_record]

        memory.load()

        self.assertEqual(memory.all(), [stored_record])

    def test_load_filters_expired_records(self) -> None:
        expired_record = MemoryRecord(
            memory_id="expired",
            content="Expired",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        active_record = MemoryRecord(memory_id="active", content="Active")
        memory = MemoryManager(
            store=RecordingMemoryStore([expired_record, active_record])
        )

        memory.load()

        self.assertEqual(memory.all(), [active_record])

    def test_load_failure_preserves_existing_memory(self) -> None:
        store = FailingMemoryStore()
        memory = MemoryManager(store=store)
        existing_record = memory.add("Existing")
        store.fail_load = True

        with self.assertRaises(MemoryError):
            memory.load()

        self.assertEqual(memory.all(), [existing_record])

    def test_load_does_not_publish_events(self) -> None:
        bus = EventBus()
        events: list[str] = []
        bus.subscribe("*", lambda event: events.append(event.name))
        memory = MemoryManager(
            bus,
            RecordingMemoryStore([MemoryRecord(memory_id="stored", content="Stored")]),
        )

        memory.load()

        self.assertEqual(events, [])

    def test_add_persists_before_publishing_event(self) -> None:
        bus = EventBus()
        store = RecordingMemoryStore()
        memory = MemoryManager(bus, store)
        save_completed_at_event: list[bool] = []
        bus.subscribe(
            "memory.record.added",
            lambda event: save_completed_at_event.append(store.save_completed),
        )

        record = memory.add("Persistent")

        self.assertEqual(memory.all(), [record])
        self.assertEqual(store.records, [record])
        self.assertEqual(save_completed_at_event, [True])

    def test_add_save_failure_keeps_memory_and_events_unchanged(self) -> None:
        bus = EventBus()
        store = FailingMemoryStore()
        store.fail_save = True
        memory = MemoryManager(bus, store)
        events: list[str] = []
        bus.subscribe("*", lambda event: events.append(event.name))

        with self.assertRaises(MemoryError):
            memory.add("Not persisted")

        self.assertEqual(memory.all(), [])
        self.assertEqual(store.records, [])
        self.assertEqual(events, [])

    def test_update_delete_and_clear_events_follow_persistence(self) -> None:
        bus = EventBus()
        store = RecordingMemoryStore(
            [MemoryRecord(memory_id="stored", content="Stored")]
        )
        memory = MemoryManager(bus, store)
        memory.load()
        event_states: list[bool] = []
        bus.subscribe("*", lambda event: event_states.append(store.save_completed))

        store.save_completed = False
        memory.update("stored", content="Updated")
        self.assertEqual(event_states, [True])

        event_states.clear()
        store.save_completed = False
        self.assertTrue(memory.delete("stored"))
        self.assertEqual(event_states, [True])

        memory.add("Again")
        event_states.clear()
        store.save_completed = False
        memory.clear()
        self.assertEqual(event_states, [True, True])

    def test_update_save_failure_preserves_the_original_record(self) -> None:
        original_record = MemoryRecord(
            memory_id="stored",
            content="Original",
            metadata={"version": 1},
            tags=frozenset({"original"}),
            created_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
            updated_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
            expires_at=datetime(2027, 8, 4, 12, 0, tzinfo=UTC),
        )
        store = FailingMemoryStore([original_record])
        memory = MemoryManager(store=store)
        memory.load()
        store.fail_save = True

        with self.assertRaises(MemoryError):
            memory.update("stored", content="Updated")

        self.assertEqual(memory.get("stored"), original_record)

    def test_delete_save_failure_preserves_the_record(self) -> None:
        record = MemoryRecord(memory_id="stored", content="Stored")
        store = FailingMemoryStore([record])
        memory = MemoryManager(store=store)
        memory.load()
        store.fail_save = True

        with self.assertRaises(MemoryError):
            memory.delete("stored")

        self.assertEqual(memory.get("stored"), record)

    def test_clear_save_failure_preserves_records(self) -> None:
        records = [
            MemoryRecord(memory_id="first", content="First"),
            MemoryRecord(memory_id="second", content="Second"),
        ]
        store = FailingMemoryStore(records)
        memory = MemoryManager(store=store)
        memory.load()
        store.fail_save = True

        with self.assertRaises(MemoryError):
            memory.clear()

        self.assertEqual(memory.all(), records)

    def test_store_snapshots_do_not_share_a_mutable_list(self) -> None:
        store = RecordingMemoryStore()
        memory = MemoryManager(store=store)

        memory.add("First")
        first_snapshot = store.saved_snapshots[0]
        memory.add("Second")

        self.assertEqual(len(first_snapshot), 1)
        self.assertIsNot(first_snapshot, store.saved_snapshots[1])

    def test_persistent_memory_loads_records_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "memory.json"
            first_memory = MemoryManager(store=JsonFileMemoryStore(path))
            record = first_memory.add("Persistent conversation")
            restarted_memory = MemoryManager(store=JsonFileMemoryStore(path))

            restarted_memory.load()

        self.assertEqual(restarted_memory.all(), [record])

    def test_persistent_update_delete_and_clear_survive_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "memory.json"
            first_memory = MemoryManager(store=JsonFileMemoryStore(path))
            record = first_memory.add("Original")
            first_memory.update(record.memory_id, content="Updated")

            after_update = MemoryManager(store=JsonFileMemoryStore(path))
            after_update.load()
            self.assertEqual(after_update.get(record.memory_id).content, "Updated")

            after_update.delete(record.memory_id)
            after_delete = MemoryManager(store=JsonFileMemoryStore(path))
            after_delete.load()
            self.assertEqual(after_delete.all(), [])

            after_delete.add("First")
            after_delete.add("Second")
            after_delete.clear()
            after_clear = MemoryManager(store=JsonFileMemoryStore(path))
            after_clear.load()

        self.assertEqual(after_clear.all(), [])

    def test_expired_persistent_records_are_not_loaded_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "memory.json"
            first_memory = MemoryManager(store=JsonFileMemoryStore(path))
            first_memory.add(
                "Expired",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            restarted_memory = MemoryManager(store=JsonFileMemoryStore(path))

            restarted_memory.load()

        self.assertEqual(restarted_memory.all(), [])

    def test_snapshot_is_side_effect_free_and_does_not_purge_expired_records(
        self,
    ) -> None:
        expired = MemoryRecord(
            memory_id="expired",
            content="Expired",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        memory = MemoryManager(self.bus, RecordingMemoryStore([expired]))
        memory.commit_snapshot((expired,))
        events: list[str] = []
        self.bus.subscribe("*", lambda event: events.append(event.name))

        snapshot = memory.snapshot()

        self.assertEqual(snapshot, (expired,))
        self.assertIs(snapshot[0], expired)
        self.assertEqual(events, [])

    def test_persist_snapshot_writes_once_without_changing_ram_or_events(self) -> None:
        store = RecordingMemoryStore()
        memory = MemoryManager(self.bus, store)
        original = memory.add("Original")
        candidate = (MemoryRecord(memory_id="candidate", content="Candidate"),)
        events: list[str] = []
        self.bus.subscribe("*", lambda event: events.append(event.name))

        self.assertIsNone(memory.persist_snapshot(candidate))

        self.assertEqual(store.saved_snapshots[-1], list(candidate))
        self.assertEqual(memory.snapshot(), (original,))
        self.assertEqual(events, [])

    def test_persist_snapshot_store_none_and_store_failure_leave_ram_unchanged(
        self,
    ) -> None:
        candidate = (MemoryRecord(memory_id="candidate", content="Candidate"),)
        self.assertIsNone(self.memory.persist_snapshot(candidate))
        self.assertEqual(self.memory.snapshot(), ())

        store = FailingMemoryStore()
        store.fail_save = True
        memory = MemoryManager(self.bus, store)
        original = MemoryRecord("original", "Original")
        memory.commit_snapshot((original,))
        with self.assertRaisesRegex(MemoryError, "^Memory save failed\\.$"):
            memory.persist_snapshot(candidate)
        self.assertEqual(memory.snapshot(), (original,))

    def test_commit_snapshot_replaces_ram_in_order_without_store_or_events(
        self,
    ) -> None:
        store = RecordingMemoryStore()
        memory = MemoryManager(self.bus, store)
        first = MemoryRecord(memory_id="first", content="First")
        second = MemoryRecord(memory_id="second", content="Second")
        events: list[str] = []
        self.bus.subscribe("*", lambda event: events.append(event.name))

        self.assertIsNone(memory.commit_snapshot((second, first)))

        self.assertEqual(memory.snapshot(), (second, first))
        self.assertEqual(store.saved_snapshots, [])
        self.assertEqual(events, [])
        memory.commit_snapshot(())
        self.assertEqual(memory.snapshot(), ())

    def test_snapshot_record_validation_is_exact_and_side_effect_free(self) -> None:
        cases = (
            (object(), "Memory snapshot must be a sequence of MemoryRecord values."),
            ("records", "Memory snapshot must be a sequence of MemoryRecord values."),
            (("bad",), "Memory snapshot contains an invalid memory record."),
            (
                (MemoryRecord(" bad ", "content"),),
                "Memory snapshot contains an invalid memory ID.",
            ),
            (
                (MemoryRecord("same", "one"), MemoryRecord("same", "two")),
                "Memory snapshot contains duplicate memory IDs.",
            ),
        )
        before = self.memory.snapshot()
        for records, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(MemoryError, re.escape(message)):
                    self.memory.commit_snapshot(records)  # type: ignore[arg-type]
        self.assertEqual(self.memory.snapshot(), before)
