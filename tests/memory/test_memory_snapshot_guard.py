"""Unit tests for MemoryManager's optimistic snapshot guard."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event, Thread

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from memory.MemoryManager import MemoryManager


class MemorySnapshotGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = MemoryManager()

    def test_matching_snapshot_runs_callback_once_and_preserves_its_result(
        self,
    ) -> None:
        snapshot = self.memory.snapshot()
        calls = 0

        def operation() -> str:
            nonlocal calls
            calls += 1
            return "complete"

        self.assertEqual(
            self.memory.run_if_snapshot_current(snapshot, operation), "complete"
        )
        self.assertEqual(calls, 1)
        self.assertEqual(self.memory.snapshot(), snapshot)

    def test_stale_snapshot_raises_without_running_callback(self) -> None:
        snapshot = self.memory.snapshot()
        self.memory.add("new record")
        callback_called = False

        def operation() -> None:
            nonlocal callback_called
            callback_called = True

        with self.assertRaisesRegex(MemoryError, "^Memory snapshot changed\\.$"):
            self.memory.run_if_snapshot_current(snapshot, operation)

        self.assertFalse(callback_called)

    def test_callback_exception_propagates_and_releases_the_lock(self) -> None:
        snapshot = self.memory.snapshot()

        def operation() -> None:
            raise RuntimeError("operation failed")

        with self.assertRaisesRegex(RuntimeError, "^operation failed$"):
            self.memory.run_if_snapshot_current(snapshot, operation)

        self.memory.add("lock is available")
        self.assertEqual(self.memory.count(), 1)

    def test_mutation_from_another_thread_waits_until_callback_completes(self) -> None:
        snapshot = self.memory.snapshot()
        callback_started = Event()
        allow_callback_to_finish = Event()
        mutation_finished = Event()

        def operation() -> str:
            callback_started.set()
            self.assertTrue(allow_callback_to_finish.wait(timeout=1))
            return "complete"

        result: list[str] = []
        guard_thread = Thread(
            target=lambda: result.append(
                self.memory.run_if_snapshot_current(snapshot, operation)
            )
        )

        def mutate_memory() -> None:
            self.memory.add("concurrent record")
            mutation_finished.set()

        mutation_thread = Thread(target=mutate_memory)

        guard_thread.start()
        self.assertTrue(callback_started.wait(timeout=1))
        mutation_thread.start()
        self.assertFalse(mutation_finished.wait(timeout=0.1))

        allow_callback_to_finish.set()
        guard_thread.join(timeout=1)
        mutation_thread.join(timeout=1)

        self.assertFalse(guard_thread.is_alive())
        self.assertFalse(mutation_thread.is_alive())
        self.assertEqual(result, ["complete"])
        self.assertTrue(mutation_finished.is_set())
        self.assertEqual(self.memory.count(), 1)
