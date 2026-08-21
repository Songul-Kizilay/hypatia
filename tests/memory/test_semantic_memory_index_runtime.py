from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event as ThreadEvent
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from eventbus.EventBus import EventBus
from memory.Embedding import Embedding
from memory.JsonFileSemanticEmbeddingCache import JsonFileSemanticEmbeddingCache
from memory.MemoryManager import MemoryManager
from memory.SemanticMemoryIndexBuilder import SemanticMemoryIndexBuilder
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class ToggleEmbeddingProvider:
    def __init__(self, embedding: Embedding) -> None:
        self.embedding = embedding
        self.should_fail = False
        self.should_crash = False
        self.sources: list[str] = []

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        self.sources.append(source_text)
        if self.should_crash:
            raise RuntimeError("Unexpected provider failure.")
        if self.should_fail:
            raise MemoryError("Embedding provider unavailable.")
        return self.embedding


class BlockingEmbeddingProvider:
    def __init__(
        self,
        embedding: Embedding,
        *,
        blocked_call_count: int = 1,
    ) -> None:
        self.embedding = embedding
        self.sources: list[str] = []
        self.entered = tuple(ThreadEvent() for _ in range(blocked_call_count))
        self.release = tuple(ThreadEvent() for _ in range(blocked_call_count))

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        self.sources.append(source_text)
        call_index = len(self.sources) - 1
        if call_index < len(self.entered):
            self.entered[call_index].set()
            if not self.release[call_index].wait(2):
                raise RuntimeError("Test embedding release timed out.")
        return self.embedding


class RecordingEmbeddingCache:
    def __init__(self) -> None:
        self.replacements: list[tuple[tuple[str, str, Embedding], ...]] = []

    def get(self, memory_id: str, source_text: str) -> Embedding | None:
        return None

    def replace(self, entries: tuple[tuple[str, str, Embedding], ...]) -> None:
        self.replacements.append(entries)

    def upsert(self, memory_id: str, source_text: str, embedding: Embedding) -> None:
        raise AssertionError("No incremental cache write was expected.")

    def remove(self, memory_id: str) -> None:
        raise AssertionError("No incremental cache removal was expected.")


class SemanticMemoryIndexRuntimeTests(unittest.TestCase):
    def test_current_is_none_before_first_successful_refresh(self) -> None:
        runtime = SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(ToggleEmbeddingProvider(Embedding((1, 0))))
        )

        self.assertIsNone(runtime.current())
        self.assertIsNone(runtime.last_rebuild_error())
        self.assertIsNone(runtime.last_update_error())

    def test_refresh_publishes_a_complete_replacement_index(self) -> None:
        memory_manager = MemoryManager()
        first = memory_manager.add("First fact")
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))

        first_index = runtime.refresh(memory_manager)
        second = memory_manager.add("Second fact")
        replacement_index = runtime.refresh(memory_manager)

        self.assertIs(runtime.current(), replacement_index)
        self.assertIsNot(first_index, replacement_index)
        self.assertEqual(first_index.count(), 1)
        self.assertEqual(replacement_index.count(), 2)
        self.assertEqual(
            replacement_index.search(Embedding((1, 0))),
            tuple(
                SemanticMemoryMatch(memory_id=memory_id, score=1.0)
                for memory_id in sorted((first.memory_id, second.memory_id))
            ),
        )

    def test_failed_refresh_preserves_last_successful_index(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("Stable fact")
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        stable_index = runtime.refresh(memory_manager)
        provider.should_fail = True

        with self.assertRaisesRegex(MemoryError, "unavailable"):
            runtime.refresh(memory_manager)

        self.assertIs(runtime.current(), stable_index)
        self.assertEqual(stable_index.count(), 1)
        self.assertEqual(
            runtime.last_rebuild_error(),
            "Semantic index rebuild failed.",
        )
        self.assertIsNone(runtime.last_update_error())

        provider.should_fail = False
        replacement_index = runtime.refresh(memory_manager)

        self.assertIs(runtime.current(), replacement_index)
        self.assertIsNone(runtime.last_rebuild_error())

    def test_rebuild_budget_failure_preserves_last_index_without_provider_work(
        self,
    ) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("Stable fact")
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(
                provider,
                max_rebuild_provider_calls=1,
            )
        )
        stable_index = runtime.refresh(memory_manager)
        memory_manager.add("New fact")

        with self.assertRaisesRegex(MemoryError, "provider-call budget exceeded"):
            runtime.refresh(memory_manager)

        self.assertIs(runtime.current(), stable_index)
        self.assertEqual(stable_index.count(), 1)
        self.assertEqual(provider.sources, ["Stable fact"])
        self.assertEqual(
            runtime.last_rebuild_error(),
            "Semantic index rebuild failed.",
        )
        self.assertIsNone(runtime.last_update_error())

    def test_attached_runtime_tracks_added_updated_and_deleted_records(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        runtime = SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(ToggleEmbeddingProvider(Embedding((1, 0))))
        )
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        record = memory_manager.add("Initial fact")
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(index.count(), 1)
        self.assertEqual(
            index.search(Embedding((1, 0))),
            (SemanticMemoryMatch(memory_id=record.memory_id, score=1.0),),
        )

        memory_manager.update(record.memory_id, content="Updated fact")
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(index.count(), 1)
        self.assertTrue(memory_manager.delete(record.memory_id))
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(index.count(), 0)
        self.assertIsNone(runtime.last_update_error())

    def test_attached_runtime_preserves_last_good_index_when_embedding_fails(
        self,
    ) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)
        provider.should_fail = True

        memory_manager.add("Primary memory write still succeeds")
        self.assertTrue(runtime.wait_for_idle(1))

        self.assertEqual(memory_manager.count(), 1)
        self.assertEqual(index.count(), 0)
        self.assertEqual(runtime.last_update_error(), "Semantic index update failed.")

    def test_attached_runtime_does_not_surface_unexpected_provider_errors(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)
        provider.should_crash = True

        record = memory_manager.add("Primary memory write still succeeds")
        self.assertTrue(runtime.wait_for_idle(1))

        self.assertIsNotNone(memory_manager.get(record.memory_id))
        self.assertEqual(index.count(), 0)
        self.assertEqual(runtime.last_update_error(), "Semantic index update failed.")

    def test_attached_runtime_updates_the_optional_embedding_cache(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache = JsonFileSemanticEmbeddingCache(
                Path(temporary_directory) / "semantic_embeddings.json",
                "provider",
            )
            runtime = SemanticMemoryIndexRuntime(
                SemanticMemoryIndexBuilder(provider, cache)
            )
            runtime.refresh(memory_manager)
            runtime.attach(event_bus)

            record = memory_manager.add("Initial fact")
            self.assertTrue(runtime.wait_for_idle(1))
            self.assertEqual(
                cache.get(record.memory_id, "Initial fact"),
                Embedding((1, 0)),
            )

            memory_manager.update(record.memory_id, content="Updated fact")
            self.assertTrue(runtime.wait_for_idle(1))
            self.assertIsNone(cache.get(record.memory_id, "Initial fact"))
            self.assertEqual(
                cache.get(record.memory_id, "Updated fact"),
                Embedding((1, 0)),
            )

            self.assertTrue(memory_manager.delete(record.memory_id))
            self.assertTrue(runtime.wait_for_idle(1))
            self.assertIsNone(cache.get(record.memory_id, "Updated fact"))

    def test_incremental_limit_failure_preserves_index_and_cache(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        first = memory_manager.add("First fact")
        provider = ToggleEmbeddingProvider(Embedding((1, 0)))

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache = JsonFileSemanticEmbeddingCache(
                Path(temporary_directory) / "semantic_embeddings.json",
                "provider",
            )
            runtime = SemanticMemoryIndexRuntime(
                SemanticMemoryIndexBuilder(provider, cache)
            )
            index = runtime.refresh(memory_manager)
            runtime.attach(event_bus)

            with patch(
                "memory.InMemorySemanticMemoryIndex."
                "MAX_SEMANTIC_MEMORY_INDEX_ENTRIES",
                1,
            ):
                second = memory_manager.add("Second fact")
            self.assertTrue(runtime.wait_for_idle(1))

            self.assertEqual(memory_manager.count(), 2)
            self.assertEqual(index.count(), 1)
            self.assertEqual(
                index.search(Embedding((1, 0))),
                (SemanticMemoryMatch(memory_id=first.memory_id, score=1.0),),
            )
            self.assertIsNone(cache.get(second.memory_id, "Second fact"))
            self.assertEqual(
                runtime.last_update_error(),
                "Semantic index update failed.",
            )

    def test_background_refresh_is_single_flight_and_search_falls_back(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))

        self.assertEqual(runtime.start_refresh(memory_manager), "started")
        self.assertTrue(provider.entered[0].wait(1))
        self.assertTrue(runtime.is_rebuilding())
        self.assertEqual(runtime.start_refresh(memory_manager), "already_running")
        self.assertEqual(runtime.search("query", limit=1), ())
        self.assertEqual(provider.sources, ["First fact"])

        provider.release[0].set()
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertFalse(runtime.is_rebuilding())
        current_index = runtime.current()
        assert current_index is not None
        self.assertEqual(current_index.count(), 1)

    def test_background_refresh_retries_one_dirty_snapshot(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        memory_manager.add("First fact")
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        runtime.attach(event_bus)

        self.assertEqual(runtime.start_refresh(memory_manager), "started")
        self.assertTrue(provider.entered[0].wait(1))
        memory_manager.add("Second fact")
        provider.release[0].set()

        self.assertTrue(runtime.wait_for_idle(1))
        current_index = runtime.current()
        assert current_index is not None
        self.assertEqual(current_index.count(), 2)
        self.assertEqual(provider.sources, ["First fact", "First fact", "Second fact"])
        self.assertIsNone(runtime.last_rebuild_error())

    def test_background_refresh_rejects_a_second_dirty_snapshot(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        memory_manager.add("First fact")
        provider = BlockingEmbeddingProvider(
            Embedding((1, 0)),
            blocked_call_count=2,
        )
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        runtime.attach(event_bus)

        self.assertEqual(runtime.start_refresh(memory_manager), "started")
        self.assertTrue(provider.entered[0].wait(1))
        memory_manager.add("Second fact")
        provider.release[0].set()
        self.assertTrue(provider.entered[1].wait(1))
        memory_manager.add("Third fact")
        provider.release[1].set()

        self.assertTrue(runtime.wait_for_idle(1))
        self.assertIsNone(runtime.current())
        self.assertEqual(
            runtime.last_rebuild_error(),
            "Semantic index rebuild failed.",
        )

    def test_shutdown_cancels_publication_and_rejects_new_work(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        cache = RecordingEmbeddingCache()
        runtime = SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(provider, cache)
        )

        self.assertEqual(runtime.start_refresh(memory_manager), "started")
        self.assertTrue(provider.entered[0].wait(1))
        runtime.shutdown()

        self.assertTrue(runtime.is_stopped())
        self.assertEqual(runtime.start_refresh(memory_manager), "stopped")
        self.assertEqual(runtime.search("query", limit=1), ())
        provider.release[0].set()
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertIsNone(runtime.current())
        self.assertEqual(cache.replacements, [])

    def test_incremental_embedding_runs_in_background_with_search_fallback(
        self,
    ) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        record = memory_manager.add("First fact")

        self.assertTrue(provider.entered[0].wait(1))
        self.assertTrue(runtime.is_updating())
        self.assertEqual(memory_manager.count(), 1)
        self.assertEqual(index.count(), 0)
        self.assertEqual(runtime.search("First", limit=1), ())
        provider.release[0].set()
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertFalse(runtime.is_updating())
        self.assertEqual(
            index.search(Embedding((1, 0))),
            (SemanticMemoryMatch(memory_id=record.memory_id, score=1.0),),
        )

    def test_incremental_events_coalesce_and_discard_stale_embedding(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        record = memory_manager.add("First fact")
        self.assertTrue(provider.entered[0].wait(1))
        memory_manager.update(record.memory_id, content="Second fact")
        memory_manager.update(record.memory_id, content="Final fact")
        provider.release[0].set()

        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(provider.sources, ["First fact", "Final fact"])
        self.assertEqual(index.count(), 1)
        self.assertIsNone(runtime.last_update_error())

    def test_incremental_delete_supersedes_in_flight_upsert(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        record = memory_manager.add("Transient fact")
        self.assertTrue(provider.entered[0].wait(1))
        self.assertTrue(memory_manager.delete(record.memory_id))
        provider.release[0].set()

        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(provider.sources, ["Transient fact"])
        self.assertEqual(index.count(), 0)
        self.assertIsNone(runtime.last_update_error())

    def test_full_refresh_waits_behind_incremental_provider_work(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        memory_manager.add("Current fact")
        self.assertTrue(provider.entered[0].wait(1))
        self.assertEqual(runtime.start_refresh(memory_manager), "started")
        self.assertEqual(provider.sources, ["Current fact"])
        provider.release[0].set()

        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(provider.sources, ["Current fact", "Current fact"])
        current_index = runtime.current()
        assert current_index is not None
        self.assertEqual(current_index.count(), 1)

    def test_incremental_queue_is_bounded_and_retains_failure_diagnostic(
        self,
    ) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        with patch(
            "memory.SemanticMemoryIndexRuntime." "MAX_PENDING_SEMANTIC_MEMORY_UPDATES",
            1,
        ):
            memory_manager.add("In flight")
            self.assertTrue(provider.entered[0].wait(1))
            memory_manager.add("Queued")
            rejected = memory_manager.add("Rejected from semantic queue")
            provider.release[0].set()
            self.assertTrue(runtime.wait_for_idle(1))

        self.assertEqual(index.count(), 2)
        self.assertEqual(
            runtime.last_update_error(),
            "Semantic index update failed.",
        )
        self.assertTrue(memory_manager.delete(rejected.memory_id))
        self.assertTrue(runtime.wait_for_idle(1))
        self.assertIsNone(runtime.last_update_error())

    def test_shutdown_suppresses_in_flight_incremental_publication(self) -> None:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        provider = BlockingEmbeddingProvider(Embedding((1, 0)))
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        index = runtime.refresh(memory_manager)
        runtime.attach(event_bus)

        memory_manager.add("Never published")
        self.assertTrue(provider.entered[0].wait(1))
        runtime.shutdown()
        provider.release[0].set()

        self.assertTrue(runtime.wait_for_idle(1))
        self.assertEqual(index.count(), 0)
        self.assertTrue(runtime.is_stopped())


if __name__ == "__main__":
    unittest.main()
