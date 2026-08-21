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
from memory.Embedding import Embedding
from memory.JsonFileSemanticEmbeddingCache import JsonFileSemanticEmbeddingCache
from memory.MemoryManager import MemoryManager
from memory.SemanticMemoryIndexBuilder import SemanticMemoryIndexBuilder
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class StubEmbeddingProvider:
    def __init__(
        self,
        embeddings_by_text: dict[str, Embedding],
        *,
        clock: ManualClock | None = None,
        durations: list[float] | None = None,
    ) -> None:
        self._embeddings_by_text = embeddings_by_text
        self._clock = clock
        self._durations = list(durations or [])
        self.requests: list[str] = []
        self.timeouts: list[float | None] = []

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        self.requests.append(source_text)
        self.timeouts.append(timeout_seconds)
        if self._durations:
            assert self._clock is not None
            self._clock.advance(self._durations.pop(0))
        return self._embeddings_by_text[source_text]


class CancellingEmbeddingProvider:
    def __init__(self, embedding: Embedding) -> None:
        self.embedding = embedding
        self.cancelled = False

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        self.cancelled = True
        return self.embedding


class FailingEmbeddingCache:
    def __init__(self) -> None:
        self.get_calls = 0

    def get(self, memory_id: str, source_text: str) -> Embedding | None:
        self.get_calls += 1
        raise OSError("cache unavailable")

    def replace(self, entries: tuple[tuple[str, str, Embedding], ...]) -> None:
        raise OSError("cache unavailable")

    def upsert(self, memory_id: str, source_text: str, embedding: Embedding) -> None:
        raise OSError("cache unavailable")

    def remove(self, memory_id: str) -> None:
        raise OSError("cache unavailable")


class RecordingEmbeddingCache:
    def __init__(
        self,
        cached_by_text: dict[str, Embedding] | None = None,
        *,
        clock: ManualClock | None = None,
        get_duration: float = 0.0,
    ) -> None:
        self._cached_by_text = cached_by_text or {}
        self._clock = clock
        self._get_duration = get_duration
        self.get_requests: list[tuple[str, str]] = []
        self.replacements: list[tuple[tuple[str, str, Embedding], ...]] = []

    def get(self, memory_id: str, source_text: str) -> Embedding | None:
        self.get_requests.append((memory_id, source_text))
        if self._clock is not None:
            self._clock.advance(self._get_duration)
        return self._cached_by_text.get(source_text)

    def replace(self, entries: tuple[tuple[str, str, Embedding], ...]) -> None:
        self.replacements.append(entries)

    def upsert(self, memory_id: str, source_text: str, embedding: Embedding) -> None:
        raise AssertionError("Full builds use atomic cache replacement only.")

    def remove(self, memory_id: str) -> None:
        raise AssertionError("Full builds never remove individual cache entries.")


class SemanticMemoryIndexBuilderTests(unittest.TestCase):
    def test_rejects_invalid_rebuild_budgets(self) -> None:
        provider = StubEmbeddingProvider({})

        for budget in (True, -1, 20_001):
            with self.subTest(budget=budget):
                with self.assertRaisesRegex(ValueError, "between 0 and 20,000"):
                    SemanticMemoryIndexBuilder(
                        provider,
                        max_rebuild_provider_calls=budget,
                    )

        for timeout in (True, 0, -1, float("inf"), 3_601):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(
                    ValueError,
                    "positive number no greater than 3600",
                ):
                    SemanticMemoryIndexBuilder(
                        provider,
                        max_rebuild_seconds=timeout,
                    )

    def test_build_uses_exact_active_memory_content_in_creation_order(self) -> None:
        memory_manager = MemoryManager()
        first = memory_manager.add("First fact")
        second = memory_manager.add("Second fact")
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((0, 1)),
            }
        )

        index = SemanticMemoryIndexBuilder(provider).build(memory_manager)

        self.assertEqual(index.dimension, 2)
        self.assertEqual(index.count(), 2)
        self.assertEqual(
            index.search(Embedding((1, 0))),
            (
                SemanticMemoryMatch(memory_id=first.memory_id, score=1.0),
                SemanticMemoryMatch(memory_id=second.memory_id, score=0.0),
            ),
        )
        self.assertEqual(provider.requests, ["First fact", "Second fact"])

    def test_build_returns_empty_index_when_memory_is_empty(self) -> None:
        provider = StubEmbeddingProvider({})

        index = SemanticMemoryIndexBuilder(provider).build(MemoryManager())

        self.assertIsNone(index.dimension)
        self.assertEqual(index.count(), 0)

    def test_rebuild_creates_a_replacement_index_without_stale_entries(self) -> None:
        memory_manager = MemoryManager()
        original = memory_manager.add("Original fact")
        provider = StubEmbeddingProvider(
            {
                "Original fact": Embedding((1, 0)),
                "Replacement fact": Embedding((0, 1)),
            }
        )
        builder = SemanticMemoryIndexBuilder(provider)

        first_index = builder.build(memory_manager)
        self.assertTrue(memory_manager.delete(original.memory_id))
        replacement = memory_manager.add("Replacement fact")

        rebuilt_index = builder.build(memory_manager)

        self.assertEqual(first_index.count(), 1)
        self.assertEqual(rebuilt_index.count(), 1)
        self.assertEqual(
            rebuilt_index.search(Embedding((0, 1))),
            (SemanticMemoryMatch(memory_id=replacement.memory_id, score=1.0),),
        )

    def test_build_rejects_a_provider_embedding_with_wrong_dimension(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        memory_manager.add("Second fact")
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((1, 0, 0)),
            }
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            SemanticMemoryIndexBuilder(provider).build(memory_manager)

    def test_build_reuses_a_matching_persisted_embedding_and_replaces_stale_content(
        self,
    ) -> None:
        memory_manager = MemoryManager()
        record = memory_manager.add("Original fact")
        provider = StubEmbeddingProvider({"Changed fact": Embedding((0, 1))})

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "semantic_embeddings.json"
            cache = JsonFileSemanticEmbeddingCache(cache_path, "provider")
            cache.upsert(record.memory_id, record.content, Embedding((1, 0)))
            builder = SemanticMemoryIndexBuilder(provider, cache)

            first_index = builder.build(memory_manager)
            memory_manager.update(record.memory_id, content="Changed fact")
            second_index = builder.build(memory_manager)

            self.assertEqual(first_index.search(Embedding((1, 0)))[0].score, 1.0)
            self.assertEqual(second_index.search(Embedding((0, 1)))[0].score, 1.0)
            self.assertEqual(provider.requests, ["Changed fact"])
            self.assertEqual(
                JsonFileSemanticEmbeddingCache(cache_path, "provider").get(
                    record.memory_id,
                    "Changed fact",
                ),
                Embedding((0, 1)),
            )

    def test_build_ignores_an_optional_cache_failure(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("Stable fact")
        provider = StubEmbeddingProvider({"Stable fact": Embedding((1, 0))})

        index = SemanticMemoryIndexBuilder(
            provider,
            FailingEmbeddingCache(),
        ).build(memory_manager)

        self.assertEqual(index.count(), 1)
        self.assertEqual(provider.requests, ["Stable fact"])

    def test_build_preflights_entry_and_aggregate_limits_before_publication(
        self,
    ) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        memory_manager.add("Second fact")
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((0, 1)),
            }
        )
        cache = RecordingEmbeddingCache()
        builder = SemanticMemoryIndexBuilder(provider, cache)

        with patch(
            "memory.InMemorySemanticMemoryIndex." "MAX_SEMANTIC_MEMORY_INDEX_ENTRIES",
            1,
        ):
            with self.assertRaisesRegex(ValueError, "too many entries"):
                builder.build(memory_manager)
        self.assertEqual(provider.requests, [])
        self.assertEqual(cache.replacements, [])

        with patch(
            "memory.InMemorySemanticMemoryIndex." "MAX_SEMANTIC_MEMORY_INDEX_VALUES",
            3,
        ):
            with self.assertRaisesRegex(ValueError, "too many embedding values"):
                builder.build(memory_manager)
        self.assertEqual(provider.requests, ["First fact"])
        self.assertEqual(cache.replacements, [])

    def test_source_text_limit_is_preflighted_before_provider_and_cache(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("abcde")
        memory_manager.add("abcdef")
        provider = StubEmbeddingProvider(
            {
                "abcde": Embedding((1, 0)),
                "abcdef": Embedding((0, 1)),
            }
        )
        cache = RecordingEmbeddingCache()
        builder = SemanticMemoryIndexBuilder(provider, cache)

        with patch(
            "memory.EmbeddingProvider.MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS",
            5,
        ):
            with self.assertRaisesRegex(MemoryError, "source text invalid"):
                builder.build(memory_manager)
            with self.assertRaisesRegex(MemoryError, "source text invalid"):
                builder.embed("abcdef")

        self.assertEqual(provider.requests, [])
        self.assertEqual(cache.replacements, [])

    def test_rebuild_budget_counts_cache_misses_before_provider_work(self) -> None:
        memory_manager = MemoryManager()
        first = memory_manager.add("Cached fact")
        second = memory_manager.add("Second fact")
        third = memory_manager.add("Third fact")
        cached_embedding = Embedding((1, 0))
        provider = StubEmbeddingProvider(
            {
                "Second fact": Embedding((0, 1)),
                "Third fact": Embedding((1, 1)),
            }
        )
        cache = RecordingEmbeddingCache({"Cached fact": cached_embedding})

        with self.assertRaisesRegex(MemoryError, "provider-call budget exceeded"):
            SemanticMemoryIndexBuilder(
                provider,
                cache,
                max_rebuild_provider_calls=1,
            ).build(memory_manager)

        self.assertEqual(provider.requests, [])
        self.assertEqual(
            cache.get_requests,
            [
                (first.memory_id, "Cached fact"),
                (second.memory_id, "Second fact"),
                (third.memory_id, "Third fact"),
            ],
        )
        self.assertEqual(cache.replacements, [])

        cache.get_requests.clear()
        index = SemanticMemoryIndexBuilder(
            provider,
            cache,
            max_rebuild_provider_calls=2,
        ).build(memory_manager)

        self.assertEqual(index.count(), 3)
        self.assertEqual(provider.requests, ["Second fact", "Third fact"])
        self.assertEqual(len(cache.replacements), 1)
        self.assertEqual(
            cache.replacements[0],
            (
                (first.memory_id, "Cached fact", cached_embedding),
                (second.memory_id, "Second fact", Embedding((0, 1))),
                (third.memory_id, "Third fact", Embedding((1, 1))),
            ),
        )

    def test_zero_rebuild_budget_allows_empty_or_fully_cached_indexes(self) -> None:
        provider = StubEmbeddingProvider({})
        empty_index = SemanticMemoryIndexBuilder(
            provider,
            max_rebuild_provider_calls=0,
        ).build(MemoryManager())
        self.assertEqual(empty_index.count(), 0)

        memory_manager = MemoryManager()
        record = memory_manager.add("Cached fact")
        cached_embedding = Embedding((1, 0))
        cache = RecordingEmbeddingCache({"Cached fact": cached_embedding})
        cached_index = SemanticMemoryIndexBuilder(
            provider,
            cache,
            max_rebuild_provider_calls=0,
        ).build(memory_manager)

        self.assertEqual(cached_index.count(), 1)
        self.assertEqual(provider.requests, [])
        self.assertEqual(
            cache.replacements,
            [((record.memory_id, "Cached fact", cached_embedding),)],
        )

    def test_cache_failure_becomes_one_bounded_all_miss_preflight(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        memory_manager.add("Second fact")
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((0, 1)),
            }
        )
        cache = FailingEmbeddingCache()

        with self.assertRaisesRegex(MemoryError, "provider-call budget exceeded"):
            SemanticMemoryIndexBuilder(
                provider,
                cache,
                max_rebuild_provider_calls=1,
            ).build(memory_manager)

        self.assertEqual(cache.get_calls, 1)
        self.assertEqual(provider.requests, [])

    def test_shared_rebuild_deadline_caps_calls_and_preserves_cache_on_overrun(
        self,
    ) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        memory_manager.add("Second fact")
        memory_manager.add("Third fact")
        clock = ManualClock()
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((0, 1)),
                "Third fact": Embedding((1, 1)),
            },
            clock=clock,
            durations=[3, 3],
        )
        cache = RecordingEmbeddingCache()

        with self.assertRaisesRegex(MemoryError, "time budget exceeded"):
            SemanticMemoryIndexBuilder(
                provider,
                cache,
                max_rebuild_seconds=5,
                clock=clock,
            ).build(memory_manager)

        self.assertEqual(provider.requests, ["First fact", "Second fact"])
        self.assertEqual(provider.timeouts, [5.0, 2.0])
        self.assertEqual(cache.replacements, [])

    def test_exact_shared_rebuild_deadline_publishes_complete_cache(self) -> None:
        memory_manager = MemoryManager()
        first = memory_manager.add("First fact")
        second = memory_manager.add("Second fact")
        clock = ManualClock()
        provider = StubEmbeddingProvider(
            {
                "First fact": Embedding((1, 0)),
                "Second fact": Embedding((0, 1)),
            },
            clock=clock,
            durations=[2, 2],
        )
        cache = RecordingEmbeddingCache()

        index = SemanticMemoryIndexBuilder(
            provider,
            cache,
            max_rebuild_seconds=4,
            clock=clock,
        ).build(memory_manager)

        self.assertEqual(index.count(), 2)
        self.assertEqual(provider.timeouts, [4.0, 2.0])
        self.assertEqual(
            cache.replacements,
            [
                (
                    (first.memory_id, "First fact", Embedding((1, 0))),
                    (second.memory_id, "Second fact", Embedding((0, 1))),
                )
            ],
        )

    def test_cache_preflight_time_overrun_skips_provider_and_cache_replacement(
        self,
    ) -> None:
        memory_manager = MemoryManager()
        record = memory_manager.add("Cached fact")
        embedding = Embedding((1, 0))
        clock = ManualClock()
        provider = StubEmbeddingProvider({})
        cache = RecordingEmbeddingCache(
            {"Cached fact": embedding},
            clock=clock,
            get_duration=2,
        )

        with self.assertRaisesRegex(MemoryError, "time budget exceeded"):
            SemanticMemoryIndexBuilder(
                provider,
                cache,
                max_rebuild_seconds=1,
                clock=clock,
            ).build(memory_manager)

        self.assertEqual(cache.get_requests, [(record.memory_id, "Cached fact")])
        self.assertEqual(provider.requests, [])
        self.assertEqual(cache.replacements, [])

    def test_time_budget_failure_preserves_runtime_last_complete_index(self) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("Stable fact")
        clock = ManualClock()
        provider = StubEmbeddingProvider(
            {
                "Stable fact": Embedding((1, 0)),
                "New fact": Embedding((0, 1)),
            },
            clock=clock,
            durations=[0, 2],
        )
        runtime = SemanticMemoryIndexRuntime(
            SemanticMemoryIndexBuilder(
                provider,
                max_rebuild_seconds=1,
                clock=clock,
            )
        )
        stable_index = runtime.refresh(memory_manager)
        memory_manager.add("New fact")

        with self.assertRaisesRegex(MemoryError, "time budget exceeded"):
            runtime.refresh(memory_manager)

        self.assertIs(runtime.current(), stable_index)
        self.assertEqual(stable_index.count(), 1)
        self.assertEqual(
            runtime.last_rebuild_error(),
            "Semantic index rebuild failed.",
        )

    def test_cancelled_build_skips_cache_replacement_and_index_publication(
        self,
    ) -> None:
        memory_manager = MemoryManager()
        memory_manager.add("First fact")
        provider = CancellingEmbeddingProvider(Embedding((1, 0)))
        cache = RecordingEmbeddingCache()

        with self.assertRaisesRegex(MemoryError, "rebuild cancelled"):
            SemanticMemoryIndexBuilder(provider, cache).build(
                memory_manager,
                cancelled=lambda: provider.cancelled,
            )

        self.assertEqual(cache.replacements, [])


if __name__ == "__main__":
    unittest.main()
