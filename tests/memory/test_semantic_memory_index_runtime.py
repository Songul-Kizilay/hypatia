from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
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

    def embed(self, source_text: str) -> Embedding:
        self.sources.append(source_text)
        if self.should_crash:
            raise RuntimeError("Unexpected provider failure.")
        if self.should_fail:
            raise MemoryError("Embedding provider unavailable.")
        return self.embedding


class SemanticMemoryIndexRuntimeTests(unittest.TestCase):
    def test_current_is_none_before_first_successful_refresh(self) -> None:
        runtime = SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(ToggleEmbeddingProvider(Embedding((1, 0))))
        )

        self.assertIsNone(runtime.current())
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
        self.assertIsNone(runtime.last_update_error())

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
        self.assertEqual(index.count(), 1)
        self.assertEqual(
            index.search(Embedding((1, 0))),
            (SemanticMemoryMatch(memory_id=record.memory_id, score=1.0),),
        )

        memory_manager.update(record.memory_id, content="Updated fact")
        self.assertEqual(index.count(), 1)
        self.assertTrue(memory_manager.delete(record.memory_id))
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
            self.assertEqual(
                cache.get(record.memory_id, "Initial fact"),
                Embedding((1, 0)),
            )

            memory_manager.update(record.memory_id, content="Updated fact")
            self.assertIsNone(cache.get(record.memory_id, "Initial fact"))
            self.assertEqual(
                cache.get(record.memory_id, "Updated fact"),
                Embedding((1, 0)),
            )

            self.assertTrue(memory_manager.delete(record.memory_id))
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


if __name__ == "__main__":
    unittest.main()
